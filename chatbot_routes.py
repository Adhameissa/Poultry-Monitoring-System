"""
Gemini-powered assistant for the Poultry Monitoring System.
API key: set environment variable GEMINI_API_KEY (never commit the key).
Optional: GEMINI_MODEL (default gemini-flash-latest — use GET /api/chat/models to list IDs for your key).
Optional: GEMINI_MODEL_FALLBACKS=comma-separated extra models (tried after errors; use only Flash models — Pro is not supported for all API keys).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import Blueprint, jsonify, request

chatbot_bp = Blueprint("chatbot", __name__)

PLATFORM_SYSTEM_PROMPT = """You are the official assistant for the "Poultry Monitoring System" web app for poultry farmers in Egypt and similar regions.

## Platform modules (high level)
1. **Home** – Overview and navigation.
2. **Dashboard** – Farm overview: chicken counts, health summaries, quick stats (varies by implementation).
3. **Disease Detection** – Upload images; AI (YOLO) classifies conditions (e.g. Healthy, Coryza, CRD, Fowlpox, Bumblefoot). Outputs may include class name and confidence.
4. **Weight Estimation** – Upload images; model estimates broiler weight (kg) for planning sales and feed.
5. **Financial Startup Planner** (`/financial/startup`) – Farmer enters budget or detailed costs (chicks, feed phases, electricity, labor, medicine, water, farm rent, expected days to sell, expected average weight, mortality %, selling price). The app computes total cost, revenue, profit, cost breakdown, sensitivity to selling price, mortality impact, weather-based windows, Prophet price forecast, and decision charts (profit vs sell day, etc.). Currency is typically **EGP**.
6. **Farm Financial Dashboard** (`/financial/dashboard`) – For an existing flock: costs so far, live birds, current weight, market price, profit projections.

## Language (Arabic / English) — CRITICAL
- If **page_context.lang** is **"ar"** OR the user writes in **Arabic**, you MUST answer **fully in Modern Standard Arabic** (فصحى مبسطة) that farmers understand. Use Arabic numerals (١٢٣) optionally; EGP can be written as جنيه or EGP.
- If the user writes in English, reply in English.
- If mixed, prefer the language of the last user message.
- Never reply only in English when the UI is Arabic and the user asked in Arabic.

## Your behaviour
- Explain inputs and outputs in **plain language** for farmers. Avoid jargon; define terms (e.g. mortality %, cost/kg, profit/kg).
- If the user asks about a **specific number or field** on the current page, use the JSON **page_context** provided in the request. Reference actual values when present.
- **Charts & graphs:** If **page_context.charts** is present and the user asks about a chart, curve, graph, or “the line going up/down”, explain using that data. Describe what each axis means (e.g. days from today vs total profit EGP), point out trends, peaks, break-even or best-day markers (**highlights**), and scenario bars. Use numbers from the JSON only; do not invent plot points.
- If something is not in page_context, say you don't have that value on this screen and suggest where they might find it or what to enter.
- Do not invent precise financial numbers that are not in the context.
- You may give general poultry best-practice advice but clarify it is general, not a substitute for a vet or accountant.
- Keep answers concise unless the user asks for detail.
"""


def _json_safe(obj: Any, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int,)):
        return obj
    if isinstance(obj, float):
        return round(obj, 6) if abs(obj) < 1e12 else float(obj)
    if isinstance(obj, str):
        return obj[:8000]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in list(obj.items())[:80]}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x, depth + 1) for x in obj[:200]]
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)[:2000]


def _downsample_xy(
    xs: list | None,
    ys: list | None,
    *,
    max_points: int = 36,
    x_key: str = "x",
    y_key: str = "y",
) -> list[dict[str, Any]]:
    if not xs or not ys or len(xs) != len(ys):
        return []
    n = len(xs)
    if n <= max_points:
        return [{x_key: _json_safe(xs[i]), y_key: _json_safe(ys[i])} for i in range(n)]
    # ~ceil(n / max_points) so we keep at most about max_points samples
    step = max(1, (n + max_points - 1) // max_points)
    out: list[dict[str, Any]] = []
    for i in range(0, n, step):
        out.append({x_key: _json_safe(xs[i]), y_key: _json_safe(ys[i])})
    if out[-1][x_key] != _json_safe(xs[-1]):
        out.append({x_key: _json_safe(xs[-1]), y_key: _json_safe(ys[-1])})
    return out[:max_points]


def _peak_xy(xs: list | None, ys: list | None) -> dict[str, Any] | None:
    if not xs or not ys or len(xs) != len(ys):
        return None
    try:
        fi = max(range(len(ys)), key=lambda i: float(ys[i]))
        return {"at_x": _json_safe(xs[fi]), "y": _json_safe(ys[fi])}
    except Exception:
        return None


def _startup_charts_payload(
    *,
    cost_labels: list | None,
    cost_values: list | None,
    sensitivity_prices: list | None,
    sensitivity_profits: list | None,
    mortality_rates: list | None,
    mortality_revenues: list | None,
    price_forecast_rows: list | None,
    forecast_mae,
    forecast_rmse,
    decision_curve_day_offsets: list | None,
    decision_curve_profits: list | None,
    decision_curve_prices: list | None,
    decision_curve_weights: list | None,
    decision_curve_cumulative_costs: list | None,
    decision_curve_cost_per_kg: list | None,
    decision_best_profit_day_offset,
    decision_break_even_day_offset,
    decision_max_profit,
    weight_curve_day_offsets: list | None,
    weight_curve_weights: list | None,
    cost_curve_day_offsets: list | None,
    cost_curve_cumulative_costs: list | None,
    decision_scenarios: list | None,
    top_cost_label: str | None,
    top_cost_pct,
) -> dict[str, Any] | None:
    """Structured chart data + glossary for the financial startup page."""
    out: dict[str, Any] = {
        "glossary": {
            "cost_breakdown": "Shares of total cost by category (labels vs EGP).",
            "sensitivity": "X: hypothetical selling price (EGP/kg). Y: estimated total profit (EGP) at that price.",
            "mortality_impact": "X: mortality rate (%). Y: estimated total revenue (EGP) under that mortality.",
            "price_forecast": "Prophet model: forecast broiler price over future dates (EGP/kg).",
            "decision_curves": "For each day offset (days from today to sale): projected total profit, price/kg, avg weight, cumulative cost, cost/kg.",
            "weight_curve": "Broiler avg weight (kg) vs day offset.",
            "cost_curve": "Cumulative farm cost (EGP) vs day offset.",
            "scenarios": "Compare selling at different delay offsets (e.g. start now vs +14d).",
        }
    }
    has = False

    if cost_labels and cost_values and len(cost_labels) == len(cost_values):
        out["cost_breakdown"] = {
            "labels": [_json_safe(x) for x in cost_labels[:40]],
            "values_egp": [_json_safe(x) for x in cost_values[:40]],
        }
        if top_cost_label:
            out["cost_breakdown"]["top_category"] = str(top_cost_label)
        if top_cost_pct is not None:
            out["cost_breakdown"]["top_category_share_percent"] = _json_safe(top_cost_pct)
        has = True

    if sensitivity_prices and sensitivity_profits and len(sensitivity_prices) == len(sensitivity_profits):
        out["sensitivity"] = {
            "points": _downsample_xy(sensitivity_prices, sensitivity_profits, x_key="price_egp_per_kg", y_key="total_profit_egp"),
            "peak_profit": _peak_xy(sensitivity_prices, sensitivity_profits),
        }
        has = True

    if mortality_rates and mortality_revenues and len(mortality_rates) == len(mortality_revenues):
        out["mortality_impact"] = {
            "points": _downsample_xy(mortality_rates, mortality_revenues, x_key="mortality_percent", y_key="total_revenue_egp"),
        }
        has = True

    if price_forecast_rows:
        rows = list(price_forecast_rows)
        if len(rows) > 40:
            rows = rows[:25] + rows[-12:]
        out["price_forecast"] = {
            "rows": _json_safe(rows),
            "mae": _json_safe(forecast_mae) if forecast_mae is not None else None,
            "rmse": _json_safe(forecast_rmse) if forecast_rmse is not None else None,
        }
        has = True

    off = decision_curve_day_offsets
    if off and decision_curve_profits and len(off) == len(decision_curve_profits):
        dc: dict[str, Any] = {
            "x_axis": "days_from_today_to_sale",
            "series": {
                "total_profit_egp": _downsample_xy(off, decision_curve_profits, y_key="total_profit_egp"),
                "forecast_price_egp_per_kg": _downsample_xy(off, decision_curve_prices, y_key="price_egp_per_kg")
                if decision_curve_prices and len(off) == len(decision_curve_prices)
                else [],
                "avg_weight_kg": _downsample_xy(off, decision_curve_weights, y_key="avg_weight_kg")
                if decision_curve_weights and len(off) == len(decision_curve_weights)
                else [],
                "cumulative_cost_egp": _downsample_xy(off, decision_curve_cumulative_costs, y_key="cumulative_cost_egp")
                if decision_curve_cumulative_costs and len(off) == len(decision_curve_cumulative_costs)
                else [],
                "cost_per_kg_egp": _downsample_xy(off, decision_curve_cost_per_kg, y_key="cost_per_kg_egp")
                if decision_curve_cost_per_kg and len(off) == len(decision_curve_cost_per_kg)
                else [],
            },
            "highlights": {},
        }
        hi = dc["highlights"]
        if decision_best_profit_day_offset is not None:
            hi["best_profit_day_offset"] = _json_safe(decision_best_profit_day_offset)
        if decision_break_even_day_offset is not None:
            hi["break_even_day_offset"] = _json_safe(decision_break_even_day_offset)
        if decision_max_profit is not None:
            hi["max_total_profit_egp"] = _json_safe(decision_max_profit)
        hi["peak_profit_on_curve"] = _peak_xy(off, decision_curve_profits)
        out["decision_curves"] = dc
        has = True

    if weight_curve_day_offsets and weight_curve_weights and len(weight_curve_day_offsets) == len(weight_curve_weights):
        out["weight_vs_day"] = {
            "points": _downsample_xy(weight_curve_day_offsets, weight_curve_weights, x_key="day_offset", y_key="avg_weight_kg"),
        }
        has = True

    if cost_curve_day_offsets and cost_curve_cumulative_costs and len(cost_curve_day_offsets) == len(cost_curve_cumulative_costs):
        out["cumulative_cost_vs_day"] = {
            "points": _downsample_xy(cost_curve_day_offsets, cost_curve_cumulative_costs, x_key="day_offset", y_key="cumulative_cost_egp"),
        }
        has = True

    if decision_scenarios:
        out["scenarios"] = _json_safe(list(decision_scenarios)[:20])
        has = True

    return out if has else None


def _dashboard_charts_payload(
    *,
    cost_vs_value_labels: list | None,
    cost_vs_value_values: list | None,
    projection_days: list | None,
    projection_profits: list | None,
    best_sell_day_offset,
    best_sell_absolute_day,
    decision_curve_day_offsets: list | None,
    decision_curve_profits: list | None,
    decision_curve_prices: list | None,
    decision_curve_avg_weights: list | None,
    decision_curve_cumulative_costs: list | None,
    decision_curve_cost_per_kg: list | None,
    decision_best_profit_day_offset,
    decision_break_even_day_offset,
    decision_max_profit,
    decision_scenarios: list | None,
) -> dict[str, Any] | None:
    out: dict[str, Any] = {
        "glossary": {
            "cost_vs_value": "Bar chart: accumulated cost vs current flock value (EGP).",
            "projection": "Next days vs projected total profit if selling then.",
            "decision_curves": "Per day offset: profit, price, weight, cumulative cost, cost/kg (same meaning as startup).",
            "scenarios": "Selling at different delay offsets with forecast price and profit.",
        }
    }
    has = False

    if cost_vs_value_labels and cost_vs_value_values and len(cost_vs_value_labels) == len(cost_vs_value_values):
        out["cost_vs_value"] = {
            "labels": [_json_safe(x) for x in cost_vs_value_labels[:10]],
            "values_egp": [_json_safe(x) for x in cost_vs_value_values[:10]],
        }
        has = True

    if projection_days and projection_profits and len(projection_days) == len(projection_profits):
        out["profit_projection"] = {
            "points": _downsample_xy(projection_days, projection_profits, x_key="day_offset", y_key="projected_profit_egp"),
            "best_day_offset": _json_safe(best_sell_day_offset) if best_sell_day_offset is not None else None,
            "best_flock_day_number": _json_safe(best_sell_absolute_day) if best_sell_absolute_day is not None else None,
        }
        has = True

    off = decision_curve_day_offsets
    if off and decision_curve_profits and len(off) == len(decision_curve_profits):
        dc: dict[str, Any] = {
            "x_axis": "days_from_today_to_sale",
            "series": {
                "total_profit_egp": _downsample_xy(off, decision_curve_profits, y_key="total_profit_egp"),
                "forecast_price_egp_per_kg": _downsample_xy(off, decision_curve_prices, y_key="price_egp_per_kg")
                if decision_curve_prices and len(off) == len(decision_curve_prices)
                else [],
                "avg_weight_kg": _downsample_xy(off, decision_curve_avg_weights, y_key="avg_weight_kg")
                if decision_curve_avg_weights and len(off) == len(decision_curve_avg_weights)
                else [],
                "cumulative_cost_egp": _downsample_xy(off, decision_curve_cumulative_costs, y_key="cumulative_cost_egp")
                if decision_curve_cumulative_costs and len(off) == len(decision_curve_cumulative_costs)
                else [],
                "cost_per_kg_egp": _downsample_xy(off, decision_curve_cost_per_kg, y_key="cost_per_kg_egp")
                if decision_curve_cost_per_kg and len(off) == len(decision_curve_cost_per_kg)
                else [],
            },
            "highlights": {},
        }
        hi = dc["highlights"]
        if decision_best_profit_day_offset is not None:
            hi["best_profit_day_offset"] = _json_safe(decision_best_profit_day_offset)
        if decision_break_even_day_offset is not None:
            hi["break_even_day_offset"] = _json_safe(decision_break_even_day_offset)
        if decision_max_profit is not None:
            hi["max_total_profit_egp"] = _json_safe(decision_max_profit)
        hi["peak_profit_on_curve"] = _peak_xy(off, decision_curve_profits)
        out["decision_curves"] = dc
        has = True

    if decision_scenarios:
        out["scenarios"] = _json_safe(list(decision_scenarios)[:20])
        has = True

    return out if has else None


def build_startup_chatbot_context(
    form_values: dict | None,
    results: dict | None,
    lang: str,
    *,
    mode: str | None = None,
    recommended_sale_date=None,
    recommended_sale_price=None,
    decision_profit_per_kg=None,
    decision_total_profit=None,
    decision_label_key=None,
    weather_location_label=None,
    cost_labels: list | None = None,
    cost_values: list | None = None,
    sensitivity_prices: list | None = None,
    sensitivity_profits: list | None = None,
    mortality_rates: list | None = None,
    mortality_revenues: list | None = None,
    price_forecast_rows: list | None = None,
    forecast_mae=None,
    forecast_rmse=None,
    decision_curve_day_offsets: list | None = None,
    decision_curve_profits: list | None = None,
    decision_curve_prices: list | None = None,
    decision_curve_weights: list | None = None,
    decision_curve_cumulative_costs: list | None = None,
    decision_curve_cost_per_kg: list | None = None,
    decision_best_profit_day_offset=None,
    decision_break_even_day_offset=None,
    decision_max_profit=None,
    weight_curve_day_offsets: list | None = None,
    weight_curve_weights: list | None = None,
    cost_curve_day_offsets: list | None = None,
    cost_curve_cumulative_costs: list | None = None,
    decision_scenarios: list | None = None,
    top_cost_label: str | None = None,
    top_cost_pct=None,
) -> dict:
    ctx: dict[str, Any] = {
        "page": "financial_startup",
        "lang": lang,
        "mode": mode,
        "weather_location": weather_location_label,
    }
    if form_values:
        ctx["inputs"] = _json_safe(dict(form_values))
    if results:
        keys = (
            "total_cost",
            "total_weight",
            "revenue",
            "profit",
            "net_profit",
            "roi",
            "break_even_price",
            "live_chickens",
            "cost_per_kg",
            "mortality_rate_percent",
        )
        out: dict[str, Any] = {}
        for k in keys:
            if k in results and results[k] is not None:
                out[k] = _json_safe(results[k])
        if results.get("cost_breakdown"):
            out["cost_breakdown"] = _json_safe(results["cost_breakdown"])
        ctx["outputs"] = out
    if recommended_sale_date is not None:
        try:
            ctx["recommended_sale_date"] = recommended_sale_date.isoformat()
        except Exception:
            ctx["recommended_sale_date"] = str(recommended_sale_date)
    if recommended_sale_price is not None:
        ctx["recommended_sale_price_egp_per_kg"] = _json_safe(recommended_sale_price)
    if decision_profit_per_kg is not None:
        ctx["decision_profit_per_kg"] = _json_safe(decision_profit_per_kg)
    if decision_total_profit is not None:
        ctx["decision_total_profit_egp"] = _json_safe(decision_total_profit)
    if decision_label_key:
        ctx["decision_label_key"] = str(decision_label_key)

    charts = _startup_charts_payload(
        cost_labels=cost_labels,
        cost_values=cost_values,
        sensitivity_prices=sensitivity_prices,
        sensitivity_profits=sensitivity_profits,
        mortality_rates=mortality_rates,
        mortality_revenues=mortality_revenues,
        price_forecast_rows=price_forecast_rows,
        forecast_mae=forecast_mae,
        forecast_rmse=forecast_rmse,
        decision_curve_day_offsets=decision_curve_day_offsets,
        decision_curve_profits=decision_curve_profits,
        decision_curve_prices=decision_curve_prices,
        decision_curve_weights=decision_curve_weights,
        decision_curve_cumulative_costs=decision_curve_cumulative_costs,
        decision_curve_cost_per_kg=decision_curve_cost_per_kg,
        decision_best_profit_day_offset=decision_best_profit_day_offset,
        decision_break_even_day_offset=decision_break_even_day_offset,
        decision_max_profit=decision_max_profit,
        weight_curve_day_offsets=weight_curve_day_offsets,
        weight_curve_weights=weight_curve_weights,
        cost_curve_day_offsets=cost_curve_day_offsets,
        cost_curve_cumulative_costs=cost_curve_cumulative_costs,
        decision_scenarios=decision_scenarios,
        top_cost_label=top_cost_label,
        top_cost_pct=top_cost_pct,
    )
    if charts:
        ctx["charts"] = charts

    return ctx


def build_dashboard_chatbot_context(
    form_values: dict | None,
    results: dict | None,
    lang: str,
    *,
    cost_vs_value_labels: list | None = None,
    cost_vs_value_values: list | None = None,
    projection_days: list | None = None,
    projection_profits: list | None = None,
    best_sell_day_offset=None,
    best_sell_absolute_day=None,
    decision_curve_day_offsets: list | None = None,
    decision_curve_profits: list | None = None,
    decision_curve_prices: list | None = None,
    decision_curve_avg_weights: list | None = None,
    decision_curve_cumulative_costs: list | None = None,
    decision_curve_cost_per_kg: list | None = None,
    decision_best_profit_day_offset=None,
    decision_break_even_day_offset=None,
    decision_max_profit=None,
    decision_scenarios: list | None = None,
) -> dict:
    ctx: dict[str, Any] = {"page": "financial_dashboard", "lang": lang}
    if form_values:
        ctx["inputs"] = _json_safe(dict(form_values))
    if results:
        ctx["outputs"] = _json_safe({k: results[k] for k in results if k != "cost_breakdown"}) if isinstance(results, dict) else _json_safe(results)

    charts = _dashboard_charts_payload(
        cost_vs_value_labels=cost_vs_value_labels,
        cost_vs_value_values=cost_vs_value_values,
        projection_days=projection_days,
        projection_profits=projection_profits,
        best_sell_day_offset=best_sell_day_offset,
        best_sell_absolute_day=best_sell_absolute_day,
        decision_curve_day_offsets=decision_curve_day_offsets,
        decision_curve_profits=decision_curve_profits,
        decision_curve_prices=decision_curve_prices,
        decision_curve_avg_weights=decision_curve_avg_weights,
        decision_curve_cumulative_costs=decision_curve_cumulative_costs,
        decision_curve_cost_per_kg=decision_curve_cost_per_kg,
        decision_best_profit_day_offset=decision_best_profit_day_offset,
        decision_break_even_day_offset=decision_break_even_day_offset,
        decision_max_profit=decision_max_profit,
        decision_scenarios=decision_scenarios,
    )
    if charts:
        ctx["charts"] = charts

    return ctx


def fetch_gemini_models_catalog(api_key: str) -> tuple[list[dict[str, Any]], str | None]:
    """
    Calls GET v1beta/models (ListModels). Returns one dict per model with id, methods, etc.
    On failure returns ([], error_message).
    """
    if not api_key.strip():
        return [], "Missing API key."
    base = "https://generativelanguage.googleapis.com/v1beta/models"
    rows: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(50):
        params: dict[str, str] = {"key": api_key.strip()}
        if page_token:
            params["pageToken"] = page_token
        url = f"{base}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = str(e)
            return [], f"ListModels error ({e.code}): {err_body[:600]}"
        except Exception as e:
            return [], str(e)

        for m in body.get("models") or []:
            if not isinstance(m, dict):
                continue
            name = str(m.get("name") or "")
            short = name.rsplit("/", 1)[-1] if name else ""
            methods = list(m.get("supportedGenerationMethods") or [])
            rows.append(
                {
                    "id": short,
                    "name": name,
                    "displayName": m.get("displayName"),
                    "description": (m.get("description") or "")[:300] or None,
                    "supportedGenerationMethods": methods,
                    "supports_generate_content": "generateContent" in methods,
                }
            )
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return rows, None


def _resolve_model_chain() -> list[str]:
    """Primary model first, then fallbacks; deduplicated. IDs vary by API key — see GET /api/chat/models."""
    primary = (os.environ.get("GEMINI_MODEL") or "gemini-flash-latest").strip()
    extra = [
        m.strip()
        for m in (os.environ.get("GEMINI_MODEL_FALLBACKS") or "").split(",")
        if m.strip()
    ]
    # Separate quota pools per model; order tries newer/lighter Flash variants before 2.0-flash.
    builtin = [
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for m in [primary] + extra + builtin:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _call_gemini(
    api_key: str,
    model: str,
    system_instruction: str,
    contents: list[dict],
) -> tuple[str | None, str | None, int | None]:
    """Returns (reply_text, error_message, http_status_if_http_error)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return None, f"Gemini API error ({e.code}): {err_body[:800]}", e.code
    except Exception as e:
        return None, str(e), None

    try:
        candidates = body.get("candidates") or []
        if not candidates:
            return None, "No response from model.", None
        parts = candidates[0].get("content", {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        return "".join(texts).strip() or None, None, None
    except Exception as e:
        return None, f"Parse error: {e}", None


@chatbot_bp.route("/chat/models", methods=["GET"])
def chat_models_list():
    """List models visible to your API key (useful to pick GEMINI_MODEL)."""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return jsonify(
            {
                "ok": False,
                "error": "GEMINI_API_KEY is not set on the server.",
            }
        ), 503

    rows, err = fetch_gemini_models_catalog(api_key)
    if err:
        return jsonify({"ok": False, "error": err}), 502

    gc_ids = [r["id"] for r in rows if r.get("supports_generate_content")]
    return jsonify(
        {
            "ok": True,
            "count": len(rows),
            "generate_content_model_ids": gc_ids,
            "models": rows,
            "hint": "Set GEMINI_MODEL to one of generate_content_model_ids. Quota limit:0 on free tier means no requests until billing or daily reset.",
        }
    )


@chatbot_bp.route("/chat", methods=["POST"])
def chat():
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return jsonify(
            {
                "ok": False,
                "error": "GEMINI_API_KEY is not set on the server. Add it to your environment or .env file.",
            }
        ), 503

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"ok": False, "error": "Empty message."}), 400

    page_context = data.get("page_context") or {}
    history = data.get("history") or []

    context_block = ""
    if page_context:
        try:
            context_block = "\n\n## Current page context (JSON)\n```json\n" + json.dumps(
                _json_safe(page_context), ensure_ascii=False, indent=2
            )[:28000] + "\n```\n"

        except Exception:
            context_block = ""

    lang_hint = ""
    if str(page_context.get("lang", "")).lower().startswith("ar"):
        lang_hint = (
            "\n\n[تعليمات اللغة: واجهة المستخدم بالعربية — أجب بالعربية الفصحى المبسطة بالكامل.]\n"
        )

    full_user = user_message + lang_hint + context_block

    contents: list[dict] = []
    if isinstance(history, list):
        for turn in history[-12:]:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            text = (turn.get("text") or "").strip()
            if role not in ("user", "model") or not text:
                continue
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": full_user}]})

    last_err: str | None = None
    models_tried: list[str] = []
    for model in _resolve_model_chain():
        models_tried.append(model)
        reply, err, status = _call_gemini(api_key, model, PLATFORM_SYSTEM_PROMPT, contents)
        if err is None:
            return jsonify({"ok": True, "reply": reply or "", "model_used": model})
        last_err = err
        # Retry on rate limit / overload; same key may have separate quotas per model.
        if status not in (429, 503, 500, 502, 404):
            break

    hint = (
        " If quota errors persist: enable billing, wait for reset, or try another model id from "
        "GET /api/chat/models (generate_content_model_ids). See "
        "https://ai.google.dev/gemini-api/docs/rate-limits"
    )
    return jsonify(
        {
            "ok": False,
            "error": (last_err or "Unknown error") + hint,
            "models_tried": models_tried,
        }
    ), 502
