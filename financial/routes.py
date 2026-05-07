from flask import Blueprint, render_template, request, Response
from datetime import timedelta, date
import math

from .calculations import (
    calculate_startup_plan,
    analyze_existing_farm,
    build_profit_sensitivity_series,
    build_mortality_impact_series,
    simulate_best_selling_time,
    simulate_decision_curves,
    build_startup_plan_from_budget,
)
from .translations import get_translation, translations, DEFAULT_LANG
from .market_price import get_today_price, get_today_chick_price, get_today_feed_prices
from .market_price import get_today_prices_snapshot
from .weather import build_weather_based_recommendations
from poultry_price_forecasting_prophet import (  # type: ignore
    train_and_forecast_prophet,
)
from chatbot_routes import build_dashboard_chatbot_context, build_startup_chatbot_context

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None

financial_bp = Blueprint("financial", __name__)


def _get_lang_from_request() -> str:
    """Return a safe language code based on query param or form field."""
    lang = request.args.get("lang") or request.form.get("lang") or DEFAULT_LANG
    lang = lang.lower()
    if lang not in translations:
        lang = DEFAULT_LANG
    return lang


def _parse_float(name: str, default: float) -> float:
    """Safely parse a float from request.form with a default fallback."""
    raw = request.form.get(name, "")
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return float(default)


def _build_phase_feed_defaults(feed_prices: dict | None) -> dict:
    feed_prices = feed_prices or {}
    return {
        "starter_feed_kg_per_chick": DEFAULT_FEED_PHASE_KG["starter"],
        "grower_feed_kg_per_chick": DEFAULT_FEED_PHASE_KG["grower"],
        "finisher_feed_kg_per_chick": DEFAULT_FEED_PHASE_KG["finisher"],
        "starter_feed_price_per_kg": float(
            feed_prices.get("starter_price_per_kg", 0.0) or 0.0
        ),
        "grower_feed_price_per_kg": float(
            feed_prices.get("grower_price_per_kg", 0.0) or 0.0
        ),
        "finisher_feed_price_per_kg": float(
            feed_prices.get("finisher_price_per_kg", 0.0) or 0.0
        ),
    }


def _compute_feed_cost_per_chick_per_day(values: dict) -> float:
    days = max(1.0, float(values.get("expected_days_to_sell", 35.0)))
    total_feed_cost_per_chick = (
        max(0.0, float(values.get("starter_feed_kg_per_chick", 0.0)))
        * max(0.0, float(values.get("starter_feed_price_per_kg", 0.0)))
        + max(0.0, float(values.get("grower_feed_kg_per_chick", 0.0)))
        * max(0.0, float(values.get("grower_feed_price_per_kg", 0.0)))
        + max(0.0, float(values.get("finisher_feed_kg_per_chick", 0.0)))
        * max(0.0, float(values.get("finisher_feed_price_per_kg", 0.0)))
    )
    return total_feed_cost_per_chick / days


# Sample default values for quick testing in Egypt (EGP)
DEFAULT_STARTUP_VALUES = {
    "number_of_chickens": 1000,
    "chick_price": 15.0,
    "starter_feed_kg_per_chick": 0.55,
    "grower_feed_kg_per_chick": 1.30,
    "finisher_feed_kg_per_chick": 1.55,
    "starter_feed_price_per_kg": 0.0,
    "grower_feed_price_per_kg": 0.0,
    "finisher_feed_price_per_kg": 0.0,
    "electricity_cost_per_day": 120.0,
    "labor_cost_per_day": 250.0,
    "medicine_cost_total": 4500.0,  # 4.5 EGP/chicken × 1000 (typical 35-day cycle; range 3–6 EGP)
    "water_cost_total": 300.0,
    "annual_farm_rent": 15000.0,
    "expected_days_to_sell": 35,
    "expected_avg_weight_kg": 2.0,
    "mortality_rate_percent": 5.0,
    "selling_price_per_kg": 70.0,
}

DEFAULT_FEED_PHASE_KG = {
    "starter": 0.55,  # day 1-10
    "grower": 1.30,  # day 11-24
    "finisher": 1.55,  # day 25-35
}

DEFAULT_DASHBOARD_VALUES = {
    # Detailed mode defaults
    "initial_chickens": 1000,
    "current_day_number": 25,
    "daily_feed_cost_total": 1800.0,
    "electricity_cost_daily": 120.0,
    "labor_cost_daily": 250.0,
    "medicine_cost_to_date": 4500.0,
    "deaths_to_date": 40,
    "avg_weight_now": 1.6,
    "current_market_price_per_kg": 68.0,
    # Simplified mode defaults
    "total_cost_so_far": 90000.0,
    "total_weight_current": 1500.0,
    "chickens_alive": 960.0,
}


@financial_bp.route("/startup", methods=["GET", "POST"])
def startup():
    """
    Render the Startup Planner page.

    The page loads with sample defaults so that it is useful even
    before the user submits any data.
    """
    lang = _get_lang_from_request()
    t, lang = get_translation(lang)

    feed_prices = get_today_feed_prices() or {}
    form_values = DEFAULT_STARTUP_VALUES.copy()
    form_values.update(_build_phase_feed_defaults(feed_prices))
    results = None
    cost_labels: list[str] = []
    cost_values: list[float] = []
    sensitivity_prices: list[float] = []
    sensitivity_profits: list[float] = []
    mortality_rates: list[float] = []
    mortality_revenues: list[float] = []
    excel_preview_headers: list[str] = []
    excel_preview_rows: list[dict] = []
    errors: list[str] = []
    weather_best_option = None
    weather_all_options: list = []
    weather_location_label: str | None = None
    price_forecast_rows: list[dict] = []
    forecast_mae: float | None = None
    forecast_rmse: float | None = None
    recommended_sale_date = None
    recommended_sale_price = None
    decision_profit_per_kg = None
    decision_total_profit = None
    decision_label_key = None
    decision_curve_day_offsets: list[int] = []
    decision_curve_profits: list[float] = []
    decision_curve_prices: list[float] = []
    decision_curve_weights: list[float] = []
    decision_curve_cumulative_costs: list[float] = []
    decision_curve_cost_per_kg: list[float] = []
    decision_best_profit_day_offset = None
    decision_break_even_day_offset = None
    decision_max_profit = None
    # Weight/cost curves over time (for charts)
    weight_curve_day_offsets: list[int] = []
    weight_curve_weights: list[float] = []
    cost_curve_day_offsets: list[int] = []
    cost_curve_cumulative_costs: list[float] = []
    decision_scenarios: list[dict] = []

    mode = "simple"

    # Try to auto-fill chick and broiler prices from market data
    try:
        auto_chick = get_today_chick_price(form_values["chick_price"])
        form_values["chick_price"] = auto_chick
    except Exception:
        pass
    try:
        form_values["selling_price_per_kg"] = get_today_price()
    except Exception:
        pass

    # Handle optional Excel / CSV upload (advanced use-case)
    if request.method == "POST":
        excel_file = request.files.get("excel_file")
        if excel_file and excel_file.filename:
            if pd is None:
                errors.append(t["excel_error_no_pandas"])
            else:
                filename = excel_file.filename.lower()
                try:
                    if filename.endswith(".csv"):
                        df = pd.read_csv(excel_file)
                    else:
                        df = pd.read_excel(excel_file)
                except Exception:
                    df = None
                    errors.append(t["excel_error_read_failed"])

                required_cols = list(DEFAULT_STARTUP_VALUES.keys())
                if df is not None:
                    missing = [c for c in required_cols if c not in df.columns]
                    if missing:
                        errors.append(t["excel_error_missing_columns"])
                    else:
                        # Use first row to populate form & calculation
                        first_row = df.iloc[0]
                        for col in required_cols:
                            try:
                                form_values[col] = float(first_row[col])
                            except Exception:
                                # Keep default if value cannot be parsed
                                pass

                        # Build preview
                        excel_preview_headers = list(df.columns)
                        excel_preview_rows = df.head(10).to_dict(orient="records")
                        # When user uploads a sheet, show full advanced inputs
                        mode = "advanced"

    # Only run main calculation when we have explicit values (GET with defaults
    # or POST after Excel filled them). This keeps the page useful even if
    # the user has not submitted anything yet.
    if request.method == "GET" or (request.method == "POST" and not errors):
        feed_cost_per_day = _compute_feed_cost_per_chick_per_day(form_values)
        farm_rent_for_cycle = max(
            0.0,
            float(form_values["number_of_chickens"]) * float(form_values["chick_price"]),
        )
        form_values["feed_cost_per_chicken_per_day"] = feed_cost_per_day
        form_values["annual_farm_rent"] = farm_rent_for_cycle
        form_values["farm_rent"] = farm_rent_for_cycle

        results = calculate_startup_plan(
            number_of_chickens=form_values["number_of_chickens"],
            chick_price=form_values["chick_price"],
            feed_cost_per_chicken_per_day=feed_cost_per_day,
            electricity_cost_per_day=form_values["electricity_cost_per_day"],
            labor_cost_per_day=form_values["labor_cost_per_day"],
            medicine_cost_total=form_values["medicine_cost_total"],
            water_cost_total=form_values["water_cost_total"],
            farm_rent=farm_rent_for_cycle,
            expected_days_to_sell=form_values["expected_days_to_sell"],
            expected_avg_weight_kg=form_values["expected_avg_weight_kg"],
            mortality_rate_percent=form_values["mortality_rate_percent"],
            selling_price_per_kg=form_values["selling_price_per_kg"],
        )

        cost_breakdown = results.get("cost_breakdown", {})
        cost_labels = list(cost_breakdown.keys())
        cost_values = list(cost_breakdown.values())

        # Build extra chart series
        sensitivity_prices, sensitivity_profits = build_profit_sensitivity_series(
            form_values
        )
        mortality_rates, mortality_revenues = build_mortality_impact_series(
            form_values
        )

    top_cost_label = None
    top_cost_pct = None
    if results and cost_labels and cost_values and results.get("total_cost"):
        max_idx = cost_values.index(max(cost_values))
        top_cost_label = cost_labels[max_idx]
        top_cost_pct = 100 * cost_values[max_idx] / results["total_cost"]

    # Weather-aware mortality / start-date recommendations (best-effort).
    if results:
        try:
            base_mortality = float(form_values.get("mortality_rate_percent", 0.0))
            weather_data = build_weather_based_recommendations(
                base_mortality_percent=base_mortality
            )
        except Exception:
            weather_data = None
        if weather_data:
            weather_location_label = str(weather_data.get("location") or "") or None
            candidates = weather_data.get("candidates") or []
            best_index = int(weather_data.get("best_index", 0) or 0)
            if candidates:
                best_index = max(0, min(best_index, len(candidates) - 1))
                weather_best_option = candidates[best_index]
                weather_all_options = candidates

    # Price forecasting (35-day range) – best-effort, small dataset so quick.
    if results:
        try:
            _, forecast_df, forecast_mae, forecast_rmse = train_and_forecast_prophet()
            price_forecast_rows = forecast_df.to_dict(orient="records")

            # Profit-based optimization: pick the candidate window with MAX total profit
            # (not the lowest weather-adjusted mortality).
            if price_forecast_rows and weather_all_options:
                price_by_date = {
                    row["date"]: row["expected_price"] for row in price_forecast_rows
                }

                # cost_per_kg is the user's current cost basis (from calculated plan)
                cost_per_kg = None
                try:
                    if results.get("total_weight", 0):
                        cost_per_kg = results["total_cost"] / results["total_weight"]
                except Exception:
                    cost_per_kg = None

                if cost_per_kg is not None:
                    chicks = float(form_values.get("number_of_chickens", 0.0) or 0.0)
                    avg_weight = float(form_values.get("expected_avg_weight_kg", 0.0) or 0.0)
                    days_to_sell = int(form_values.get("expected_days_to_sell", 35))

                    def _get_forecast_price_for_date(target_date):
                        if target_date in price_by_date:
                            return float(price_by_date[target_date])
                        forecast_dates = sorted(price_by_date.keys())
                        if not forecast_dates:
                            return None
                        closest = min(
                            forecast_dates,
                            key=lambda d: abs((d - target_date).days),
                        )
                        return float(price_by_date[closest])

                    best = None  # (total_profit, candidate, sell_date, forecast_price, profit_per_kg)
                    for cand in weather_all_options:
                        sell_date = cand.start_date + timedelta(days=days_to_sell)
                        forecast_price = _get_forecast_price_for_date(sell_date)
                        if forecast_price is None:
                            continue

                        live_chickens = max(
                            0.0,
                            chicks * (1.0 - float(cand.adjusted_mortality_percent) / 100.0),
                        )
                        total_weight = live_chickens * max(0.0, avg_weight)
                        total_cost = float(results.get("total_cost", 0.0) or 0.0)
                        total_profit = float(forecast_price) * float(total_weight) - total_cost
                        profit_per_kg = (total_profit / total_weight) if total_weight > 0 else 0.0

                        if best is None or total_profit > best[0]:
                            best = (total_profit, cand, sell_date, forecast_price, profit_per_kg)

                    if best is not None:
                        decision_total_profit, weather_best_option, recommended_sale_date, recommended_sale_price, decision_profit_per_kg = best
                        if decision_profit_per_kg < 0:
                            decision_label_key = "decision_label_do_not_start"
                        elif decision_profit_per_kg < 5:
                            decision_label_key = "decision_label_low_profit"
                        else:
                            decision_label_key = "decision_label_good_to_start"

                        # --- Decision charts data (startup page) ---
                        try:
                            curve_offsets = list(range(30, 46))
                            best_start_date = weather_best_option.start_date

                            def _forecast_price_for_target_date(target_date):
                                if target_date in price_by_date:
                                    return float(price_by_date[target_date])
                                forecast_dates = sorted(price_by_date.keys())
                                if not forecast_dates:
                                    return 0.0
                                closest = min(
                                    forecast_dates,
                                    key=lambda d: abs((d - target_date).days),
                                )
                                return float(price_by_date[closest])

                            target_w = avg_weight
                            base_w = max(0.04, target_w * 0.04)
                            k = 0.12
                            denom = 1.0 - math.exp(-k * max(1, days_to_sell))
                            if denom <= 0:
                                denom = 1.0
                            weight_cap = target_w * 1.12

                            def _weight_at_day(d):
                                d = max(0.0, float(d))
                                w = base_w + (target_w - base_w) * (
                                    (1.0 - math.exp(-k * d)) / denom
                                )
                                return float(min(weight_cap, max(0.0, w)))

                            chicks_count = float(form_values.get("number_of_chickens", 0.0) or 0.0)
                            daily_operating_cost_total = (
                                feed_cost_per_day * chicks_count
                                + float(form_values.get("electricity_cost_per_day", 0.0) or 0.0)
                                + float(form_values.get("labor_cost_per_day", 0.0) or 0.0)
                            )
                            start_cost = (
                                float(form_values.get("chick_price", 0.0) or 0.0) * chicks_count
                                + float(form_values.get("farm_rent", 0.0) or 0.0)
                            )
                            medicine_total = float(form_values.get("medicine_cost_total", 0.0) or 0.0)
                            water_total = float(form_values.get("water_cost_total", 0.0) or 0.0)

                            def _medicine_factor(d):
                                d_eff = min(float(d), float(days_to_sell))
                                return d_eff / float(days_to_sell) if days_to_sell > 0 else 0.0

                            def _cumulative_cost_at_day(d):
                                d = float(d)
                                return (
                                    start_cost
                                    + daily_operating_cost_total * d
                                    + medicine_total * _medicine_factor(d)
                                    + water_total * _medicine_factor(d)
                                )

                            live_chickens_best = max(
                                0.0,
                                chicks_count * (1.0 - float(weather_best_option.adjusted_mortality_percent) / 100.0),
                            )

                            decision_curve_day_offsets = curve_offsets
                            decision_curve_prices = []
                            decision_curve_profits = []
                            decision_curve_weights = []
                            decision_curve_cumulative_costs = []
                            decision_curve_cost_per_kg = []

                            for off in curve_offsets:
                                sell_date = best_start_date + timedelta(days=off)
                                price = _forecast_price_for_target_date(sell_date)
                                w_day = _weight_at_day(off)
                                total_weight_day = live_chickens_best * w_day
                                cumulative_cost = _cumulative_cost_at_day(off)
                                profit = total_weight_day * price - cumulative_cost
                                cost_per_kg_day = (
                                    cumulative_cost / total_weight_day if total_weight_day > 0 else 0.0
                                )

                                decision_curve_prices.append(price)
                                decision_curve_weights.append(w_day)
                                decision_curve_cumulative_costs.append(cumulative_cost)
                                decision_curve_cost_per_kg.append(cost_per_kg_day)
                                decision_curve_profits.append(profit)

                            best_idx = max(
                                range(len(decision_curve_profits)),
                                key=lambda i: decision_curve_profits[i],
                            )
                            decision_best_profit_day_offset = decision_curve_day_offsets[best_idx]
                            decision_max_profit = decision_curve_profits[best_idx]

                            diffs = [
                                abs(decision_curve_prices[i] - decision_curve_cost_per_kg[i])
                                for i in range(len(curve_offsets))
                            ]
                            be_idx = min(range(len(diffs)), key=lambda i: diffs[i])
                            decision_break_even_day_offset = decision_curve_day_offsets[be_idx]

                            weight_curve_day_offsets = list(range(0, 46))
                            weight_curve_weights = [_weight_at_day(d) for d in weight_curve_day_offsets]
                            cost_curve_day_offsets = list(range(0, 46))
                            cost_curve_cumulative_costs = [
                                _cumulative_cost_at_day(d) for d in cost_curve_day_offsets
                            ]
                        except Exception:
                            pass

                        # Scenario comparison table (start now, +14d, +30d)
                        try:
                            today = date.today()
                            scenario_offsets = [0, 14, 30]
                            label_map = {0: "Start now", 14: "+14d", 30: "+30d"}

                            decision_scenarios = []
                            for cand in weather_all_options:
                                off_from_today = (cand.start_date - today).days
                                if off_from_today not in scenario_offsets:
                                    continue
                                sell_date = cand.start_date + timedelta(days=days_to_sell)
                                forecast_price = _forecast_price_for_target_date(sell_date)

                                live_chickens = max(
                                    0.0,
                                    chicks_count * (1.0 - float(cand.adjusted_mortality_percent) / 100.0),
                                )
                                total_weight = live_chickens * max(0.0, avg_weight)
                                total_profit = float(forecast_price) * float(total_weight) - total_cost
                                profit_per_kg = (total_profit / total_weight) if total_weight > 0 else 0.0

                                decision_scenarios.append(
                                    {
                                        "label": label_map.get(off_from_today, f"+{off_from_today}d"),
                                        "sell_in_days": days_to_sell,
                                        "forecast_price_per_kg": float(forecast_price),
                                        "profit_per_kg": float(profit_per_kg),
                                        "total_profit": float(total_profit),
                                    }
                                )
                            # If no weather candidate matched 0/14/30 days, add synthetic rows
                            if not decision_scenarios and price_by_date:
                                try:
                                    est_sell = today + timedelta(days=days_to_sell)
                                    fp = float(price_by_date.get(est_sell) or 0)
                                    if fp <= 0 and price_by_date:
                                        closest_d = min(price_by_date.keys(), key=lambda d: abs((d - est_sell).days))
                                        fp = float(price_by_date[closest_d] or 70)
                                    if fp <= 0:
                                        fp = 70.0
                                    cycle_cost = float(total_cost)
                                    live_ch = max(0.0, chicks_count * 0.955)
                                    tw = live_ch * max(0.0, avg_weight)
                                    tp = tw * fp - cycle_cost
                                    ppk = (tp / tw) if tw > 0 else 0.0
                                    for off in scenario_offsets:
                                        decision_scenarios.append({
                                            "label": label_map.get(off, f"+{off}d"),
                                            "sell_in_days": days_to_sell,
                                            "forecast_price_per_kg": fp,
                                            "profit_per_kg": ppk,
                                            "total_profit": tp,
                                        })
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # --- Decision charts data (startup page) ---
                        try:
                            # Curve days: sell options 30..45 days from the chosen start.
                            curve_offsets = list(range(30, 46))
                            best_start_date = weather_best_option.start_date

                            def _forecast_price_for_target_date(target_date):
                                if target_date in price_by_date:
                                    return float(price_by_date[target_date])
                                forecast_dates = sorted(price_by_date.keys())
                                if not forecast_dates:
                                    return 0.0
                                closest = min(
                                    forecast_dates,
                                    key=lambda d: abs((d - target_date).days),
                                )
                                return float(price_by_date[closest])

                            # Weight growth curve (0..45 days)
                            weight_curve_day_offsets = list(range(0, 46))
                            target_w = avg_weight
                            base_w = max(0.04, target_w * 0.04)
                            k = 0.12  # taper growth to plateau
                            denom = 1.0 - math.exp(-k * max(1, days_to_sell))
                            if denom <= 0:
                                denom = 1.0
                            weight_cap = target_w * 1.12

                            def _weight_at_day(d):
                                d = max(0.0, float(d))
                                w = base_w + (target_w - base_w) * (
                                    (1.0 - math.exp(-k * d)) / denom
                                )
                                return float(min(weight_cap, max(0.0, w)))

                            # Daily operating costs for cumulative cost curve
                            chicks = float(form_values.get("number_of_chickens", 0.0) or 0.0)
                            daily_feed_cost_total = feed_cost_per_day * chicks
                            daily_operating_cost_total = (
                                daily_feed_cost_total
                                + float(form_values.get("electricity_cost_per_day", form_values.get("electricity_cost_per_day", 0.0)) or 0.0)
                                + float(form_values.get("labor_cost_per_day", form_values.get("labor_cost_per_day", 0.0)) or 0.0)
                            )
                            # In this function `values[...]` should already hold electricity/labor per day.
                            daily_operating_cost_total = (
                                feed_cost_per_day * chicks
                                + float(form_values.get("electricity_cost_per_day", 0.0) or 0.0)
                                + float(form_values.get("labor_cost_per_day", 0.0) or 0.0)
                            )

                            farm_rent_cost = float(form_values.get("farm_rent", 0.0) or 0.0)
                            chick_purchase_cost = float(form_values.get("chick_price", 0.0) or 0.0) * chicks

                            start_cost = chick_purchase_cost + farm_rent_cost
                            medicine_total = float(form_values.get("medicine_cost_total", 0.0) or 0.0)
                            water_total = float(form_values.get("water_cost_total", 0.0) or 0.0)

                            def _medicine_factor(d):
                                # Medicine & water assumed spread over the expected cycle length.
                                d_eff = min(float(d), float(days_to_sell))
                                return d_eff / float(days_to_sell) if days_to_sell > 0 else 0.0

                            def _cumulative_cost_at_day(d):
                                d = float(d)
                                return (
                                    start_cost
                                    + daily_operating_cost_total * d
                                    + medicine_total * _medicine_factor(d)
                                    + water_total * _medicine_factor(d)
                                )

                            # Live chickens for the best start scenario
                            live_chickens_best = max(
                                0.0,
                                chicks * (1.0 - float(weather_best_option.adjusted_mortality_percent) / 100.0),
                            )

                            # Profit / price / cost curves for 30..45
                            decision_curve_day_offsets = curve_offsets
                            decision_curve_prices = []
                            decision_curve_profits = []
                            decision_curve_weights = []
                            decision_curve_cumulative_costs = []
                            decision_curve_cost_per_kg = []

                            for off in curve_offsets:
                                sell_date = best_start_date + timedelta(days=off)
                                price = _forecast_price_for_target_date(sell_date)
                                w_day = _weight_at_day(off)
                                total_weight_day = live_chickens_best * w_day
                                cumulative_cost = _cumulative_cost_at_day(off)
                                profit = total_weight_day * price - cumulative_cost
                                cost_per_kg = (
                                    cumulative_cost / total_weight_day if total_weight_day > 0 else 0.0
                                )

                                decision_curve_prices.append(price)
                                decision_curve_weights.append(w_day)
                                decision_curve_cumulative_costs.append(cumulative_cost)
                                decision_curve_cost_per_kg.append(cost_per_kg)
                                decision_curve_profits.append(profit)

                            # Best profit day in the curve
                            best_idx = max(range(len(decision_curve_profits)), key=lambda i: decision_curve_profits[i])
                            decision_best_profit_day_offset = decision_curve_day_offsets[best_idx]
                            decision_max_profit = decision_curve_profits[best_idx]

                            # Break-even day: closest between price and cost/kg (or profit closest to 0)
                            diffs = [abs(decision_curve_prices[i] - decision_curve_cost_per_kg[i]) for i in range(len(curve_offsets))]
                            be_idx = min(range(len(diffs)), key=lambda i: diffs[i])
                            decision_break_even_day_offset = decision_curve_day_offsets[be_idx]

                            # Weight growth & cumulative cost curves for charts (0..45)
                            weight_curve_day_offsets = list(range(0, 46))
                            weight_curve_weights = [_weight_at_day(d) for d in weight_curve_day_offsets]
                            cost_curve_day_offsets = list(range(0, 46))
                            cost_curve_cumulative_costs = [
                                _cumulative_cost_at_day(d) for d in cost_curve_day_offsets
                            ]
                        except Exception:
                            # If chart computation fails, keep arrays empty so page still works.
                            pass

                        # Scenario comparison table (start now, +14d, +30d)
                        try:
                            today = date.today()
                            days_to_sell_scenario = days_to_sell
                            scenario_offsets = [0, 14, 30]
                            label_map = {0: "Start now", 14: "+14d", 30: "+30d"}

                            decision_scenarios = []
                            for cand in weather_all_options:
                                off_from_today = (cand.start_date - today).days
                                if off_from_today not in scenario_offsets:
                                    continue
                                sell_date = cand.start_date + timedelta(days=days_to_sell_scenario)
                                forecast_price = _forecast_price_for_target_date(sell_date)

                                live_chickens = max(
                                    0.0,
                                    chicks * (1.0 - float(cand.adjusted_mortality_percent) / 100.0),
                                )
                                total_weight = live_chickens * max(0.0, avg_weight)
                                total_profit = float(forecast_price) * float(total_weight) - total_cost
                                profit_per_kg = (total_profit / total_weight) if total_weight > 0 else 0.0

                                decision_scenarios.append(
                                    {
                                        "label": label_map.get(off_from_today, f"+{off_from_today}d"),
                                        "sell_in_days": days_to_sell_scenario,
                                        "forecast_price_per_kg": float(forecast_price),
                                        "profit_per_kg": float(profit_per_kg),
                                        "total_profit": float(total_profit),
                                    }
                                )
                            # If no weather candidate matched 0/14/30 days, add synthetic rows
                            if not decision_scenarios and decision_curve_prices and decision_curve_profits:
                                mid = min(14, len(decision_curve_day_offsets) - 1)
                                fp = float(decision_curve_prices[mid]) if mid >= 0 else 70.0
                                cycle_cost = results["total_cost"] if results else 0.0
                                live_ch = max(0.0, chicks * 0.955)
                                tw = live_ch * max(0.0, avg_weight)
                                tp = tw * fp - cycle_cost
                                ppk = (tp / tw) if tw > 0 else 0.0
                                for off in scenario_offsets:
                                    decision_scenarios.append({
                                        "label": label_map.get(off, f"+{off}d"),
                                        "sell_in_days": days_to_sell_scenario,
                                        "forecast_price_per_kg": fp,
                                        "profit_per_kg": ppk,
                                        "total_profit": tp,
                                    })
                        except Exception:
                            pass

            # Fallback: if profit optimization fails, keep the original weather-based sell date.
            if (recommended_sale_date is None) and weather_best_option and price_forecast_rows:
                price_by_date = {
                    row["date"]: row["expected_price"] for row in price_forecast_rows
                }
                days_to_sell = int(form_values.get("expected_days_to_sell", 35))
                est_sell_date = weather_best_option.start_date + timedelta(days=days_to_sell)
                recommended_sale_date = est_sell_date
                if est_sell_date in price_by_date:
                    recommended_sale_price = float(price_by_date[est_sell_date])
                else:
                    forecast_dates = sorted(price_by_date.keys())
                    if forecast_dates:
                        closest = min(
                            forecast_dates,
                            key=lambda d: abs((d - est_sell_date).days),
                        )
                        recommended_sale_price = float(price_by_date[closest])

                # Derive decision label from profit_per_kg using cost basis.
                try:
                    if results.get("total_weight", 0):
                        cost_per_kg = results["total_cost"] / results["total_weight"]
                        if recommended_sale_price is not None:
                            decision_profit_per_kg = float(recommended_sale_price - cost_per_kg)
                            live_chickens = max(
                                0.0,
                                float(form_values.get("number_of_chickens", 0.0) or 0.0)
                                * (1.0 - float(weather_best_option.adjusted_mortality_percent) / 100.0),
                            )
                            avg_weight = float(form_values.get("expected_avg_weight_kg", 0.0) or 0.0)
                            decision_total_profit = decision_profit_per_kg * (live_chickens * max(0.0, avg_weight))
                            if decision_profit_per_kg < 0:
                                decision_label_key = "decision_label_do_not_start"
                            elif decision_profit_per_kg < 5:
                                decision_label_key = "decision_label_low_profit"
                            else:
                                decision_label_key = "decision_label_good_to_start"
                except Exception:
                    pass
        except Exception:
            price_forecast_rows = []
            forecast_mae = None
            forecast_rmse = None

    # --- Ensure decision charts always have data when results exist ---
    # Run chart data generation whenever we have results but chart arrays are empty/incomplete.
    # This handles: Prophet failure, weather API failure, or scenario dates not matching.
    _need_chart_data = (
        results
        and (
            (not decision_curve_day_offsets)
            or (not decision_curve_prices)
            or (not decision_curve_profits)
            or (not decision_curve_cost_per_kg)
            or len(decision_curve_day_offsets) != len(decision_curve_prices)
            or (not decision_scenarios)
        )
    )
    if _need_chart_data:
        try:
            curve_offsets = list(range(30, 46))
            decision_curve_day_offsets = curve_offsets

            avg_weight = max(0.01, float(form_values.get("expected_avg_weight_kg", 2.0) or 2.0))
            chicks = max(1.0, float(form_values.get("number_of_chickens", 100.0) or 100.0))
            days_to_sell = max(30, min(45, int(form_values.get("expected_days_to_sell", 35) or 35)))

            # Selling price for charts (defensive)
            chart_price = 70.0
            try:
                if recommended_sale_price is not None and float(recommended_sale_price) > 0:
                    chart_price = float(recommended_sale_price)
                elif float(form_values.get("selling_price_per_kg", 0) or 0) > 0:
                    chart_price = float(form_values.get("selling_price_per_kg") or 70)
                else:
                    p = get_today_price()
                    if p is not None and float(p) > 0:
                        chart_price = float(p)
            except (TypeError, ValueError):
                pass

            target_w = max(0.5, avg_weight)
            base_w = max(0.04, target_w * 0.04)
            k = 0.12  # taper growth to plateau
            denom = 1.0 - math.exp(-k * max(1, days_to_sell))
            if denom <= 0:
                denom = 1.0
            weight_cap = target_w * 1.12

            def _weight_at_day(d: int) -> float:
                d = max(0.0, float(d))
                w = base_w + (target_w - base_w) * ((1.0 - math.exp(-k * d)) / denom)
                return float(min(weight_cap, max(0.0, w)))

            mortality_percent = None
            if weather_best_option is not None:
                try:
                    mortality_percent = float(weather_best_option.adjusted_mortality_percent)
                except Exception:
                    mortality_percent = None
            if mortality_percent is None:
                mortality_percent = float(form_values.get("mortality_rate_percent", 0.0) or 0.0)
            mortality_percent = max(0.0, float(mortality_percent))

            live_chickens_best = max(0.0, chicks * (1.0 - mortality_percent / 100.0))

            daily_feed_cost_total = feed_cost_per_day * chicks
            daily_operating_cost_total = (
                daily_feed_cost_total
                + float(form_values.get("electricity_cost_per_day", 0.0) or 0.0)
                + float(form_values.get("labor_cost_per_day", 0.0) or 0.0)
            )

            farm_rent_cost = float(form_values.get("farm_rent", 0.0) or 0.0)
            chick_purchase_cost = float(form_values.get("chick_price", 0.0) or 0.0) * chicks
            start_cost = chick_purchase_cost + farm_rent_cost

            medicine_total = float(form_values.get("medicine_cost_total", 0.0) or 0.0)
            water_total = float(form_values.get("water_cost_total", 0.0) or 0.0)

            def _medicine_factor(d: float) -> float:
                if days_to_sell <= 0:
                    return 0.0
                return min(float(d), float(days_to_sell)) / float(days_to_sell)

            def _cumulative_cost_at_day(d: float) -> float:
                d = float(d)
                return (
                    start_cost
                    + daily_operating_cost_total * d
                    + medicine_total * _medicine_factor(d)
                    + water_total * _medicine_factor(d)
                )

            decision_curve_prices = [float(chart_price)] * len(curve_offsets)
            decision_curve_profits = []
            decision_curve_weights = []
            decision_curve_cumulative_costs = []
            decision_curve_cost_per_kg = []

            for off in curve_offsets:
                w_day = _weight_at_day(off)
                total_weight_day = live_chickens_best * max(0.0, w_day)
                cumulative_cost = _cumulative_cost_at_day(off)
                profit = total_weight_day * float(chart_price) - cumulative_cost
                cost_per_kg_day = (
                    cumulative_cost / total_weight_day if total_weight_day > 0 else 0.0
                )
                decision_curve_weights.append(float(w_day))
                decision_curve_cumulative_costs.append(float(cumulative_cost))
                decision_curve_cost_per_kg.append(float(cost_per_kg_day))
                decision_curve_profits.append(float(profit))

            best_idx = max(range(len(decision_curve_profits)), key=lambda i: decision_curve_profits[i])
            decision_best_profit_day_offset = decision_curve_day_offsets[best_idx]
            decision_max_profit = decision_curve_profits[best_idx]

            diffs = [
                abs(decision_curve_prices[i] - decision_curve_cost_per_kg[i])
                for i in range(len(curve_offsets))
            ]
            be_idx = min(range(len(diffs)), key=lambda i: diffs[i])
            decision_break_even_day_offset = decision_curve_day_offsets[be_idx]

            # Weight and cumulative cost curves for the other charts
            weight_curve_day_offsets = list(range(0, 46))
            weight_curve_weights = [_weight_at_day(d) for d in weight_curve_day_offsets]
            cost_curve_day_offsets = list(range(0, 46))
            cost_curve_cumulative_costs = [_cumulative_cost_at_day(d) for d in cost_curve_day_offsets]

            # Scenario table: use same price/cost and mortality baseline for simplicity
            scenario_offsets = [0, 14, 30]
            label_map = {0: "Start now", 14: "+14d", 30: "+30d"}
            # Scenario profit uses cycle cost at day `days_to_sell`
            cycle_cost = _cumulative_cost_at_day(float(days_to_sell))
            scenario_total_weight = live_chickens_best * max(0.0, avg_weight)
            scenario_total_profit = scenario_total_weight * float(chart_price) - cycle_cost
            scenario_profit_per_kg = (
                scenario_total_profit / scenario_total_weight if scenario_total_weight > 0 else 0.0
            )

            decision_scenarios = []
            for off in scenario_offsets:
                decision_scenarios.append(
                    {
                        "label": label_map.get(off, f"+{off}d"),
                        "sell_in_days": days_to_sell,
                        "forecast_price_per_kg": float(chart_price),
                        "profit_per_kg": float(scenario_profit_per_kg),
                        "total_profit": float(scenario_total_profit),
                    }
                )

        except Exception:
            # Keep whatever we have; template will show fallback-only if created.
            pass

    # If weather/Prophet branches did not set a sale date, still show "Your decision" using plan + forecast/form price.
    if results and recommended_sale_date is None:
        try:
            days_to_sell = max(1, int(form_values.get("expected_days_to_sell", 35) or 35))
            est_sell = date.today() + timedelta(days=days_to_sell)
            recommended_sale_date = est_sell
            if price_forecast_rows:
                price_by_date: dict = {}
                for row in price_forecast_rows:
                    d = row.get("date")
                    if d is not None:
                        price_by_date[d] = float(row.get("expected_price", 0) or 0)
                if price_by_date:
                    if est_sell in price_by_date:
                        recommended_sale_price = float(price_by_date[est_sell])
                    else:
                        closest_d = min(
                            price_by_date.keys(),
                            key=lambda d: abs((d - est_sell).days),
                        )
                        recommended_sale_price = float(price_by_date[closest_d])
            if recommended_sale_price is None:
                sp = float(form_values.get("selling_price_per_kg", 0) or 0)
                if sp > 0:
                    recommended_sale_price = sp
                else:
                    try:
                        tp = get_today_price()
                        if tp is not None and float(tp) > 0:
                            recommended_sale_price = float(tp)
                    except Exception:
                        pass
            if decision_profit_per_kg is None and recommended_sale_price is not None and results.get("total_weight"):
                cost_per_kg = float(results["total_cost"]) / float(results["total_weight"])
                decision_profit_per_kg = float(recommended_sale_price) - cost_per_kg
                live_chickens = max(
                    0.0,
                    float(form_values.get("number_of_chickens", 0) or 0)
                    * (1.0 - float(form_values.get("mortality_rate_percent", 0) or 0) / 100.0),
                )
                avg_weight = float(form_values.get("expected_avg_weight_kg", 0) or 0)
                decision_total_profit = decision_profit_per_kg * (live_chickens * max(0.0, avg_weight))
                if decision_label_key is None:
                    if decision_profit_per_kg < 0:
                        decision_label_key = "decision_label_do_not_start"
                    elif decision_profit_per_kg < 5:
                        decision_label_key = "decision_label_low_profit"
                    else:
                        decision_label_key = "decision_label_good_to_start"
        except Exception:
            pass

    market = get_today_prices_snapshot()

    return render_template(
        "financial_startup.html",
        lang=lang,
        t=t,
        form_values=form_values,
        results=results,
        cost_labels=cost_labels,
        cost_values=cost_values,
        sensitivity_prices=sensitivity_prices,
        sensitivity_profits=sensitivity_profits,
        mortality_rates=mortality_rates,
        mortality_revenues=mortality_revenues,
        excel_preview_headers=excel_preview_headers,
        excel_preview_rows=excel_preview_rows,
        errors=errors,
        mode=mode,
        top_cost_label=top_cost_label,
        top_cost_pct=top_cost_pct,
        weather_best_option=weather_best_option,
        weather_all_options=weather_all_options,
        weather_location_label=weather_location_label,
        price_forecast=price_forecast_rows,
        forecast_mae=forecast_mae,
        forecast_rmse=forecast_rmse,
        recommended_sale_date=recommended_sale_date,
        recommended_sale_price=recommended_sale_price,
        decision_profit_per_kg=decision_profit_per_kg,
        decision_total_profit=decision_total_profit,
        decision_label_key=decision_label_key,
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
        today_broiler_price=market["broiler_price"],
        today_broiler_min=market["broiler_min"],
        today_broiler_max=market["broiler_max"],
        today_chick_price=market["chick_price"],
        today_chick_min=market["chick_min"],
        today_chick_max=market["chick_max"],
        today_feed=market["feed"],
        chatbot_page_context=build_startup_chatbot_context(
            form_values,
            results,
            lang,
            mode=mode,
            recommended_sale_date=recommended_sale_date,
            recommended_sale_price=recommended_sale_price,
            decision_profit_per_kg=decision_profit_per_kg,
            decision_total_profit=decision_total_profit,
            decision_label_key=decision_label_key,
            weather_location_label=weather_location_label,
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
        ),
    )


@financial_bp.route("/startup/calculate", methods=["POST"])
def startup_calculate():
    """Handle startup planner form submission."""
    lang = _get_lang_from_request()
    t, lang = get_translation(lang)

    mode = request.form.get("mode", "advanced")

    if mode == "simple":
        # Budget-only mode: farmer provides total money, chick price, selling price.
        # Defaults from scraped altkia data; user can override.
        total_budget = _parse_float("total_budget", 0.0)
        chick_price = _parse_float(
            "chick_price", get_today_chick_price(DEFAULT_STARTUP_VALUES["chick_price"])
        )
        selling_price_input = _parse_float("selling_price_per_kg", 0.0)
        selling_price_per_kg = selling_price_input if selling_price_input > 0 else get_today_price()

        feed_prices = get_today_feed_prices() or {}
        phase_defaults = _build_phase_feed_defaults(feed_prices)
        temp_feed_values = {
            **phase_defaults,
            "expected_days_to_sell": DEFAULT_STARTUP_VALUES["expected_days_to_sell"],
        }
        feed_cost_per_day = _compute_feed_cost_per_chick_per_day(temp_feed_values)

        values = build_startup_plan_from_budget(
            total_budget=total_budget,
            chick_price=chick_price,
            selling_price_per_kg=selling_price_per_kg,
            feed_cost_per_chicken_per_day=feed_cost_per_day,
            water_cost_total=DEFAULT_STARTUP_VALUES["water_cost_total"],
        )
        values["total_budget"] = total_budget
        values.update(phase_defaults)
        values["water_cost_total"] = DEFAULT_STARTUP_VALUES["water_cost_total"]
    else:
        # Advanced mode: explicit expert inputs
        values = DEFAULT_STARTUP_VALUES.copy()
        values.update(_build_phase_feed_defaults(get_today_feed_prices() or {}))
        for key, default_val in DEFAULT_STARTUP_VALUES.items():
            values[key] = _parse_float(key, default_val)
        for key in (
            "starter_feed_kg_per_chick",
            "grower_feed_kg_per_chick",
            "finisher_feed_kg_per_chick",
            "starter_feed_price_per_kg",
            "grower_feed_price_per_kg",
            "finisher_feed_price_per_kg",
        ):
            values[key] = _parse_float(key, values[key])

    feed_cost_per_day = _compute_feed_cost_per_chick_per_day(values)
    farm_rent_default = max(
        0.0, float(values["number_of_chickens"]) * float(values["chick_price"])
    )
    if mode == "simple":
        # Simplified mode: farm rent = number of chicks × chick price (not from form).
        farm_rent_for_cycle = float(values.get("farm_rent", farm_rent_default))
    else:
        farm_rent_for_cycle = max(0.0, _parse_float("annual_farm_rent", farm_rent_default))
    values["feed_cost_per_chicken_per_day"] = feed_cost_per_day
    values["annual_farm_rent"] = farm_rent_for_cycle
    values["farm_rent"] = farm_rent_for_cycle

    results = calculate_startup_plan(
        number_of_chickens=values["number_of_chickens"],
        chick_price=values["chick_price"],
        feed_cost_per_chicken_per_day=feed_cost_per_day,
        electricity_cost_per_day=values["electricity_cost_per_day"],
        labor_cost_per_day=values["labor_cost_per_day"],
        medicine_cost_total=values["medicine_cost_total"],
        water_cost_total=values["water_cost_total"],
        farm_rent=farm_rent_for_cycle,
        expected_days_to_sell=values["expected_days_to_sell"],
        expected_avg_weight_kg=values["expected_avg_weight_kg"],
        mortality_rate_percent=values["mortality_rate_percent"],
        selling_price_per_kg=values["selling_price_per_kg"],
    )

    cost_breakdown = results.get("cost_breakdown", {})
    cost_labels = list(cost_breakdown.keys())
    cost_values = list(cost_breakdown.values())

    sensitivity_prices, sensitivity_profits = build_profit_sensitivity_series(values)
    mortality_rates, mortality_revenues = build_mortality_impact_series(values)

    top_cost_label = None
    top_cost_pct = None
    if results and cost_labels and cost_values and results.get("total_cost"):
        max_idx = cost_values.index(max(cost_values))
        top_cost_label = cost_labels[max_idx]
        top_cost_pct = 100 * cost_values[max_idx] / results["total_cost"]

    weather_best_option = None
    weather_all_options: list = []
    weather_location_label: str | None = None
    price_forecast_rows: list[dict] = []
    forecast_mae: float | None = None
    forecast_rmse: float | None = None
    recommended_sale_date = None
    recommended_sale_price = None
    decision_profit_per_kg = None
    decision_total_profit = None
    decision_label_key = None
    decision_curve_day_offsets: list[int] = []
    decision_curve_profits: list[float] = []
    decision_curve_prices: list[float] = []
    decision_curve_weights: list[float] = []
    decision_curve_cumulative_costs: list[float] = []
    decision_curve_cost_per_kg: list[float] = []
    decision_best_profit_day_offset = None
    decision_break_even_day_offset = None
    decision_max_profit = None
    weight_curve_day_offsets: list[int] = []
    weight_curve_weights: list[float] = []
    cost_curve_day_offsets: list[int] = []
    cost_curve_cumulative_costs: list[float] = []
    decision_scenarios: list[dict] = []
    if results:
        try:
            base_mortality = float(values.get("mortality_rate_percent", 0.0))
            weather_data = build_weather_based_recommendations(
                base_mortality_percent=base_mortality
            )
        except Exception:
            weather_data = None
        if weather_data:
            weather_location_label = str(weather_data.get("location") or "") or None
            candidates = weather_data.get("candidates") or []
            best_index = int(weather_data.get("best_index", 0) or 0)
            if candidates:
                best_index = max(0, min(best_index, len(candidates) - 1))
                weather_best_option = candidates[best_index]
                weather_all_options = candidates

    if results:
        try:
            _, forecast_df, forecast_mae, forecast_rmse = train_and_forecast_prophet()
            price_forecast_rows = forecast_df.to_dict(orient="records")

            if price_forecast_rows and weather_all_options:
                price_by_date = {
                    row["date"]: row["expected_price"] for row in price_forecast_rows
                }

                cost_per_kg = None
                try:
                    if results.get("total_weight", 0):
                        cost_per_kg = results["total_cost"] / results["total_weight"]
                except Exception:
                    cost_per_kg = None

                if cost_per_kg is not None:
                    chicks = float(values.get("number_of_chickens", 0.0) or 0.0)
                    avg_weight = float(values.get("expected_avg_weight_kg", 0.0) or 0.0)
                    days_to_sell = int(values.get("expected_days_to_sell", 35))
                    total_cost = float(results.get("total_cost", 0.0) or 0.0)

                    def _get_forecast_price_for_date(target_date):
                        if target_date in price_by_date:
                            return float(price_by_date[target_date])
                        forecast_dates = sorted(price_by_date.keys())
                        if not forecast_dates:
                            return None
                        closest = min(
                            forecast_dates,
                            key=lambda d: abs((d - target_date).days),
                        )
                        return float(price_by_date[closest])

                    best = None  # (total_profit, candidate, sell_date, forecast_price, profit_per_kg)
                    for cand in weather_all_options:
                        sell_date = cand.start_date + timedelta(days=days_to_sell)
                        forecast_price = _get_forecast_price_for_date(sell_date)
                        if forecast_price is None:
                            continue

                        live_chickens = max(
                            0.0,
                            chicks * (1.0 - float(cand.adjusted_mortality_percent) / 100.0),
                        )
                        total_weight = live_chickens * max(0.0, avg_weight)
                        # Costs are based on initial chicks and cycle assumptions,
                        # so they do not change with weather-adjusted mortality.
                        # Only revenue (weight) changes with mortality.
                        total_profit = float(forecast_price) * float(total_weight) - total_cost
                        profit_per_kg = (total_profit / total_weight) if total_weight > 0 else 0.0

                        if best is None or total_profit > best[0]:
                            best = (
                                total_profit,
                                cand,
                                sell_date,
                                forecast_price,
                                profit_per_kg,
                            )

                    if best is not None:
                        decision_total_profit, weather_best_option, recommended_sale_date, recommended_sale_price, decision_profit_per_kg = best
                        if decision_profit_per_kg < 0:
                            decision_label_key = "decision_label_do_not_start"
                        elif decision_profit_per_kg < 5:
                            decision_label_key = "decision_label_low_profit"
                        else:
                            decision_label_key = "decision_label_good_to_start"

            # Fallback to weather-based recommendation if profit optimization fails.
            if (recommended_sale_date is None) and weather_best_option and price_forecast_rows:
                price_by_date = {
                    row["date"]: row["expected_price"] for row in price_forecast_rows
                }
                days_to_sell = int(values.get("expected_days_to_sell", 35))
                est_sell_date = weather_best_option.start_date + timedelta(days=days_to_sell)
                recommended_sale_date = est_sell_date
                if est_sell_date in price_by_date:
                    recommended_sale_price = float(price_by_date[est_sell_date])
                else:
                    forecast_dates = sorted(price_by_date.keys())
                    if forecast_dates:
                        closest = min(
                            forecast_dates,
                            key=lambda d: abs((d - est_sell_date).days),
                        )
                        recommended_sale_price = float(price_by_date[closest])

                try:
                    if results.get("total_weight", 0) and recommended_sale_price is not None:
                        live_chickens = max(
                            0.0,
                            float(values.get("number_of_chickens", 0.0) or 0.0)
                            * (1.0 - float(weather_best_option.adjusted_mortality_percent) / 100.0),
                        )
                        avg_weight = float(values.get("expected_avg_weight_kg", 0.0) or 0.0)
                        total_weight_scenario = live_chickens * max(0.0, avg_weight)
                        total_cost = float(results.get("total_cost", 0.0) or 0.0)
                        total_profit = float(recommended_sale_price) * float(total_weight_scenario) - total_cost
                        decision_profit_per_kg = (total_profit / total_weight_scenario) if total_weight_scenario > 0 else 0.0
                        decision_total_profit = total_profit
                        if decision_profit_per_kg < 0:
                            decision_label_key = "decision_label_do_not_start"
                        elif decision_profit_per_kg < 5:
                            decision_label_key = "decision_label_low_profit"
                        else:
                            decision_label_key = "decision_label_good_to_start"
                except Exception:
                    pass
        except Exception:
            price_forecast_rows = []
            forecast_mae = None
            forecast_rmse = None

    # --- startup_calculate: ensure decision charts have data when results exist ---
    if results and (not decision_curve_day_offsets or not decision_curve_prices or not decision_scenarios):
        try:
            curve_offsets = list(range(30, 46))
            decision_curve_day_offsets = curve_offsets
            avg_weight = max(0.5, float(values.get("expected_avg_weight_kg", 2.0) or 2.0))
            chicks = max(1.0, float(values.get("number_of_chickens", 100.0) or 100.0))
            days_to_sell = max(30, min(45, int(values.get("expected_days_to_sell", 35) or 35)))
            chart_price = 70.0
            try:
                if recommended_sale_price is not None and float(recommended_sale_price) > 0:
                    chart_price = float(recommended_sale_price)
                elif float(values.get("selling_price_per_kg", 0) or 0) > 0:
                    chart_price = float(values.get("selling_price_per_kg") or 70)
                else:
                    p = get_today_price()
                    if p is not None and float(p) > 0:
                        chart_price = float(p)
            except (TypeError, ValueError):
                pass
            target_w = max(0.5, avg_weight)
            base_w = max(0.04, target_w * 0.04)
            k = 0.12
            denom = max(0.01, 1.0 - math.exp(-k * days_to_sell))
            def _w(d): return float(min(target_w * 1.12, max(0.0, base_w + (target_w - base_w) * (1.0 - math.exp(-k * max(0, d))) / denom)))
            mortality_pct = float(values.get("mortality_rate_percent", 5.0) or 5.0)
            live_ch = max(1.0, chicks * (1.0 - mortality_pct / 100.0))
            daily_op = feed_cost_per_day * chicks + float(values.get("electricity_cost_per_day", 0) or 0) + float(values.get("labor_cost_per_day", 0) or 0)
            start_cost = float(values.get("chick_price", 0) or 0) * chicks + float(values.get("farm_rent", 0) or 0)
            med = float(values.get("medicine_cost_total", 0) or 0)
            wat = float(values.get("water_cost_total", 0) or 0)
            def _cost(d): return start_cost + daily_op * d + (med + wat) * min(1.0, d / max(1, days_to_sell))
            decision_curve_prices = [float(chart_price)] * 16
            decision_curve_profits = []
            decision_curve_cost_per_kg = []
            for off in curve_offsets:
                w = _w(off)
                tw = live_ch * w
                c = _cost(off)
                profit = tw * chart_price - c
                ckg = c / tw if tw > 0 else 0.0
                decision_curve_profits.append(float(profit))
                decision_curve_cost_per_kg.append(float(ckg))
            best_i = max(range(16), key=lambda i: decision_curve_profits[i])
            decision_best_profit_day_offset = curve_offsets[best_i]
            decision_max_profit = decision_curve_profits[best_i]
            be_i = min(range(16), key=lambda i: abs(decision_curve_prices[i] - decision_curve_cost_per_kg[i]))
            decision_break_even_day_offset = curve_offsets[be_i]
            weight_curve_day_offsets = list(range(0, 46))
            weight_curve_weights = [_w(d) for d in weight_curve_day_offsets]
            cost_curve_day_offsets = list(range(0, 46))
            cost_curve_cumulative_costs = [_cost(d) for d in cost_curve_day_offsets]
            decision_curve_weights = [_w(off) for off in curve_offsets]
            decision_curve_cumulative_costs = [_cost(off) for off in curve_offsets]
            cycle_cost = _cost(days_to_sell)
            sc_tw = live_ch * avg_weight
            sc_profit = sc_tw * chart_price - cycle_cost
            sc_ppk = sc_profit / sc_tw if sc_tw > 0 else 0.0
            decision_scenarios = [
                {"label": "Start now", "sell_in_days": days_to_sell, "forecast_price_per_kg": float(chart_price), "profit_per_kg": float(sc_ppk), "total_profit": float(sc_profit)},
                {"label": "+14d", "sell_in_days": days_to_sell, "forecast_price_per_kg": float(chart_price), "profit_per_kg": float(sc_ppk), "total_profit": float(sc_profit)},
                {"label": "+30d", "sell_in_days": days_to_sell, "forecast_price_per_kg": float(chart_price), "profit_per_kg": float(sc_ppk), "total_profit": float(sc_profit)},
            ]
        except Exception:
            pass

    market = get_today_prices_snapshot()

    return render_template(
        "financial_startup.html",
        lang=lang,
        t=t,
        form_values=values,
        results=results,
        cost_labels=cost_labels,
        cost_values=cost_values,
        sensitivity_prices=sensitivity_prices,
        sensitivity_profits=sensitivity_profits,
        mortality_rates=mortality_rates,
        mortality_revenues=mortality_revenues,
        excel_preview_headers=[],
        excel_preview_rows=[],
        errors=[],
        mode=mode,
        top_cost_label=top_cost_label,
        top_cost_pct=top_cost_pct,
        weather_best_option=weather_best_option,
        weather_all_options=weather_all_options,
        weather_location_label=weather_location_label,
        price_forecast=price_forecast_rows,
        forecast_mae=forecast_mae,
        forecast_rmse=forecast_rmse,
        recommended_sale_date=recommended_sale_date,
        recommended_sale_price=recommended_sale_price,
        decision_profit_per_kg=decision_profit_per_kg,
        decision_total_profit=decision_total_profit,
        decision_label_key=decision_label_key,
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
        today_broiler_price=market["broiler_price"],
        today_broiler_min=market["broiler_min"],
        today_broiler_max=market["broiler_max"],
        today_chick_price=market["chick_price"],
        today_chick_min=market["chick_min"],
        today_chick_max=market["chick_max"],
        today_feed=market["feed"],
        chatbot_page_context=build_startup_chatbot_context(
            values,
            results,
            lang,
            mode=mode,
            recommended_sale_date=recommended_sale_date,
            recommended_sale_price=recommended_sale_price,
            decision_profit_per_kg=decision_profit_per_kg,
            decision_total_profit=decision_total_profit,
            decision_label_key=decision_label_key,
            weather_location_label=weather_location_label,
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
        ),
    )


@financial_bp.route("/startup/template", methods=["GET"])
def startup_template() -> Response:
    """
    Provide a simple CSV template that matches the expected columns
    for Excel/CSV upload in the startup planner.
    """
    headers = list(DEFAULT_STARTUP_VALUES.keys())
    csv_content = ",".join(headers) + "\n"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=startup_template.csv"},
    )


@financial_bp.route("/dashboard", methods=["GET"])
def dashboard_financial():
    """
    Render the Existing Farm Dashboard.

    The page shows KPI layout and charts even before analysis,
    populated with sample defaults in the form.
    """
    lang = _get_lang_from_request()
    t, lang = get_translation(lang)

    market = get_today_prices_snapshot()
    today_market_price = market["broiler_price"] or get_today_price()
    initial_values = DEFAULT_DASHBOARD_VALUES.copy()
    initial_values["current_market_price_per_kg"] = today_market_price

    return render_template(
        "financial_dashboard.html",
        lang=lang,
        t=t,
        form_values=initial_values,
        results=None,
        cost_vs_value_labels=[],
        cost_vs_value_values=[],
        today_market_price=today_market_price,
        today_broiler_price=market["broiler_price"],
        today_broiler_min=market["broiler_min"],
        today_broiler_max=market["broiler_max"],
        today_chick_price=market["chick_price"],
        today_chick_min=market["chick_min"],
        today_chick_max=market["chick_max"],
        today_feed=market["feed"],
        mode="advanced",
        projection_days=[],
        projection_profits=[],
        best_sell_day_offset=None,
        best_sell_absolute_day=None,
        decision_curve_day_offsets=[],
        decision_curve_profits=[],
        decision_curve_prices=[],
        decision_curve_avg_weights=[],
        decision_curve_cumulative_costs=[],
        decision_curve_cost_per_kg=[],
        decision_best_profit_day_offset=None,
        decision_break_even_day_offset=None,
        decision_max_profit=None,
        decision_scenarios=[],
        chatbot_page_context=build_dashboard_chatbot_context(initial_values, None, lang),
    )


@financial_bp.route("/dashboard/analyze", methods=["POST"])
def dashboard_analyze():
    """Handle Existing Farm Dashboard analysis POST."""
    lang = _get_lang_from_request()
    t, lang = get_translation(lang)

    mode = request.form.get("mode", "advanced")

    values = DEFAULT_DASHBOARD_VALUES.copy()
    for key, default_val in DEFAULT_DASHBOARD_VALUES.items():
        values[key] = _parse_float(key, default_val)

    market = get_today_prices_snapshot()
    today_market_price = market["broiler_price"] or get_today_price()

    # Decision-focused charts (profit optimization + forecast-informed prices)
    decision_curve_day_offsets: list[int] = []
    decision_curve_profits: list[float] = []
    decision_curve_prices: list[float] = []
    decision_curve_avg_weights: list[float] = []
    decision_curve_cumulative_costs: list[float] = []
    decision_curve_cost_per_kg: list[float] = []
    decision_best_profit_day_offset = None
    decision_break_even_day_offset = None
    decision_max_profit = None
    decision_scenarios: list[dict] = []

    if mode == "simple":
        # Simplified farm finance mode
        total_cost_so_far = _parse_float(
            "total_cost_so_far", values["total_cost_so_far"]
        )
        total_weight_current = _parse_float(
            "total_weight_current", values["total_weight_current"]
        )
        chickens_alive = _parse_float("chickens_alive", values["chickens_alive"])
        selling_price_per_kg = _parse_float(
            "selling_price_per_kg", values["current_market_price_per_kg"]
        )

        values["total_cost_so_far"] = total_cost_so_far
        values["total_weight_current"] = total_weight_current
        values["chickens_alive"] = chickens_alive
        values["current_market_price_per_kg"] = selling_price_per_kg

        current_value = max(
            0.0, total_weight_current * max(0.0, selling_price_per_kg)
        )
        profit = current_value - total_cost_so_far
        profit_per_chicken = (
            profit / chickens_alive if chickens_alive > 0 else 0.0
        )
        cost_per_kg = (
            total_cost_so_far / total_weight_current
            if total_weight_current > 0
            else 0.0
        )

        results = {
            "live_chickens": chickens_alive,
            "accumulated_cost": total_cost_so_far,
            "current_value": current_value,
            "profit_today": profit,
            "mortality_rate_actual": 0.0,
            "operating_cost_to_date": total_cost_so_far,
            "cost_breakdown": {"total": total_cost_so_far},
            "profit_per_chicken": profit_per_chicken,
            "cost_per_kg": cost_per_kg,
        }

        cost_vs_value_labels = [t["total_cost"], t["kpi_current_value"]]
        cost_vs_value_values = [total_cost_so_far, current_value]

        projection_days: list[int] = []
        projection_profits: list[float] = []
        best_sell_day_offset = None
        best_sell_absolute_day = None

    else:
        # Detailed mode using full inputs
        results = analyze_existing_farm(
            initial_chickens=values["initial_chickens"],
            current_day_number=values["current_day_number"],
            daily_feed_cost_total=values["daily_feed_cost_total"],
            electricity_cost_daily=values["electricity_cost_daily"],
            labor_cost_daily=values["labor_cost_daily"],
            medicine_cost_to_date=values["medicine_cost_to_date"],
            deaths_to_date=values["deaths_to_date"],
            avg_weight_now=values["avg_weight_now"],
            current_market_price_per_kg=values["current_market_price_per_kg"],
        )

        accumulated_cost = results.get("accumulated_cost", 0.0)
        current_value = results.get("current_value", 0.0)

        # Derived metrics
        live_chickens = results.get("live_chickens", 0.0)
        profit_today = results.get("profit_today", 0.0)
        profit_per_chicken = (
            profit_today / live_chickens if live_chickens > 0 else 0.0
        )
        results["profit_per_chicken"] = profit_per_chicken

        # Best selling time simulation (next 7–10 days)
        daily_operating_cost = (
            values["daily_feed_cost_total"]
            + values["electricity_cost_daily"]
            + values["labor_cost_daily"]
        )

        # Decision curves: use Prophet forecast prices to recommend the best selling day
        # within 30–45 days, plus scenario comparison (start now, +14d, +30d).
        try:
            curve_offsets = list(range(30, 46))  # 30–45 days
            scenario_offsets = [0, 14, 30]  # start now, +14d, +30d

            _, forecast_df, _, _ = train_and_forecast_prophet()
            price_forecast_rows = (
                forecast_df.to_dict(orient="records") if forecast_df is not None else []
            )
            price_by_date = {
                row["date"]: float(row["expected_price"])
                for row in price_forecast_rows
            }

            today = date.today()

            def _price_for_target_date(target_date):
                # Exact match first
                if target_date in price_by_date:
                    return float(price_by_date[target_date])
                forecast_dates = sorted(price_by_date.keys())
                if not forecast_dates:
                    return float(values.get("current_market_price_per_kg", 0.0) or 0.0)
                closest = min(
                    forecast_dates,
                    key=lambda d: abs((d - target_date).days),
                )
                return float(price_by_date[closest])

            needed_offsets = sorted(set(curve_offsets + scenario_offsets))
            price_by_offset = {}
            for off in needed_offsets:
                target_date = today + timedelta(days=int(off))
                price_by_offset[int(off)] = _price_for_target_date(target_date)

            sim_decision = simulate_decision_curves(
                live_chickens=live_chickens,
                avg_weight_now_kg=values["avg_weight_now"],
                accumulated_cost_egp=accumulated_cost,
                daily_operating_cost_egp=daily_operating_cost,
                medicine_cost_to_date_egp=values["medicine_cost_to_date"],
                current_day_number=values["current_day_number"],
                price_per_kg_by_offset=price_by_offset,
                curve_day_offsets=curve_offsets,
                scenario_day_offsets=scenario_offsets,
                daily_weight_gain_kg=0.05,
            )

            decision_curve_day_offsets = sim_decision["curve_day_offsets"]
            decision_curve_profits = sim_decision["curve_profits"]
            decision_curve_prices = sim_decision["curve_prices"]
            decision_curve_avg_weights = sim_decision["curve_avg_weights"]
            decision_curve_cumulative_costs = sim_decision["curve_cumulative_costs"]
            decision_curve_cost_per_kg = sim_decision["curve_cost_per_kg"]
            decision_best_profit_day_offset = sim_decision["best_profit_day_offset"]
            decision_break_even_day_offset = sim_decision["break_even_day_offset"]
            decision_max_profit = sim_decision["max_profit"]

            label_map = {0: "Start now", 14: "+14d", 30: "+30d"}
            decision_scenarios = []
            for i, off in enumerate(sim_decision["scenario_day_offsets"]):
                scenario_price = sim_decision["scenario_prices"][i]
                scenario_cost_per_kg = sim_decision["scenario_cost_per_kg"][i]
                decision_scenarios.append(
                    {
                        "label": label_map.get(off, f"+{off}d"),
                        "sell_in_days": off,
                        "forecast_price_per_kg": scenario_price,
                        "profit_per_kg": scenario_price - scenario_cost_per_kg,
                        "total_profit": sim_decision["scenario_profits"][i],
                    }
                )
        except Exception:
            # Keep decision_* empty if forecast fails.
            pass

        sim = simulate_best_selling_time(
            live_chickens=live_chickens,
            avg_weight_now=values["avg_weight_now"],
            current_market_price_per_kg=values["current_market_price_per_kg"],
            accumulated_cost=accumulated_cost,
            daily_operating_cost=daily_operating_cost,
            days_ahead=10,
            daily_weight_gain_kg=0.05,
        )

        projection_days = sim["days"]
        projection_profits = sim["projected_profits"]
        best_sell_day_offset = sim["best_day_offset"]
        best_sell_absolute_day = (
            values["current_day_number"] + best_sell_day_offset
        )

        cost_vs_value_labels = [t["total_cost"], t["kpi_current_value"]]
        cost_vs_value_values = [accumulated_cost, current_value]

    return render_template(
        "financial_dashboard.html",
        lang=lang,
        t=t,
        form_values=values,
        results=results,
        cost_vs_value_labels=cost_vs_value_labels,
        cost_vs_value_values=cost_vs_value_values,
        today_market_price=today_market_price,
        today_broiler_price=market["broiler_price"],
        today_broiler_min=market["broiler_min"],
        today_broiler_max=market["broiler_max"],
        today_chick_price=market["chick_price"],
        today_chick_min=market["chick_min"],
        today_chick_max=market["chick_max"],
        today_feed=market["feed"],
        mode=mode,
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
        chatbot_page_context=build_dashboard_chatbot_context(
            values,
            results,
            lang,
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
        ),
    )

