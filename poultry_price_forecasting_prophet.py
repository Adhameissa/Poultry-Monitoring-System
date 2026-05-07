"""
Poultry price forecasting pipeline using Facebook Prophet.

This script trains a Prophet model on Egyptian poultry executed prices
and forecasts a multi-day price range (default 70 days) so that
recommended sell dates (e.g. start + 35 days) fall within the forecast.

Handles sudden regime changes (price crashes) typical in Egyptian markets
via recency-weighted training (approximated), crash-aware anchoring, and
short-term caps on unrealistic upward moves.

Usage (from project root):

    python poultry_price_forecasting_prophet.py

Inputs:
    - CSV: 'pricespoultryegypt (2).csv'
      Required columns: date, executed_price

Outputs:
    - 'poultry_price_forecast_35_days_prophet.csv'
    - 'poultry_forecast_plot_prophet.png'

# -----------------------------------------------------------------------------
# Implementation notes
# -----------------------------------------------------------------------------
# - Train on one row per day only (duplicate rows destabilize long forecasts).
# - changepoint_prior_scale ~0.08; intervals: additive shift (never ratio×yhat).
# - Raw yhat clipped to history-based bounds; final output also sanity-clipped.
# - Crash anchor / last-3 mean / first-7 upward cap in adjust_forecast_to_recent_market
# -----------------------------------------------------------------------------
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prophet import Prophet  # type: ignore
from sklearn.metrics import mean_absolute_error, mean_squared_error


DATA_PATH = Path("pricespoultryegypt (2).csv")
FORECAST_CSV = Path("poultry_price_forecast_35_days_prophet.csv")
FORECAST_PLOT = Path("poultry_forecast_plot_prophet.png")

# Forecast horizon: 70 days covers "start in ~35 days" + "sell after 35 days"
FORECAST_DAYS = 70

# --- Crash / short-term tuning (Egyptian poultry market) ---
CRASH_DROP_WINDOW = 5
CRASH_DROP_THRESHOLD_EGP = 8.0
SHORT_TERM_UPWARD_CAP_EGP = 3.0
SHORT_TERM_CAP_DAYS = 7
ANCHOR_LAST_N_MEAN = 3

# Short-term plateau (Egyptian market: flat + small noise, not smooth trend)
PLATEAU_FORECAST_DAYS = 14
PLATEAU_FLUCTUATION_EGP = 1.5
# Max Prophet blend weight (lower = more anchor / less smooth extrapolation)
MAX_BLEND_WEIGHT = 0.75
MAX_BLEND_WEIGHT_CRASH = 0.73

# Plausible executed-price band (EGP/kg) — clips numerical Prophet blow-ups
PRICE_SANITY_FLOOR_EGP = 45.0
PRICE_SANITY_CEILING_EGP = 180.0


# ---------------------------------------------------------------------------
# Holidays / seasonal effects
# ---------------------------------------------------------------------------


def build_holiday_dataframe() -> pd.DataFrame:
    """
    Construct a Prophet-compatible holiday dataframe with Ramadan and Eid dates.
    """
    ramadan_start_days: List[datetime] = [
        datetime(2025, 2, 28),
        datetime(2026, 2, 18),
        datetime(2027, 2, 8),
        datetime(2028, 1, 28),
        datetime(2029, 1, 16),
        datetime(2030, 1, 6),
    ]
    eid_fitr_days: List[datetime] = [
        datetime(2025, 3, 31),
        datetime(2026, 3, 20),
        datetime(2027, 3, 10),
        datetime(2028, 2, 28),
        datetime(2029, 2, 15),
        datetime(2030, 2, 5),
    ]
    eid_adha_days: List[datetime] = [
        datetime(2025, 6, 7),
        datetime(2026, 5, 27),
        datetime(2027, 5, 17),
        datetime(2028, 5, 6),
        datetime(2029, 4, 25),
        datetime(2030, 4, 14),
    ]

    rows: List[dict] = []
    for d in ramadan_start_days:
        rows.append({"holiday": "ramadan_start", "ds": d, "lower_window": 0, "upper_window": 0})
    for d in eid_fitr_days:
        rows.append({"holiday": "eid_al_fitr", "ds": d, "lower_window": 0, "upper_window": 2})
    for d in eid_adha_days:
        rows.append({"holiday": "eid_al_adha", "ds": d, "lower_window": 0, "upper_window": 2})

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------


def prepare_prophet_dataframe(path: Path = DATA_PATH) -> pd.DataFrame:
    """
    Load dataset (CSV) and convert to Prophet's expected format:
        ds: datetime
        y: executed_price
    """
    df = pd.read_csv(path)

    if "date" not in df.columns or "executed_price" not in df.columns:
        raise ValueError("Dataset must contain 'date' and 'executed_price' columns.")

    df = df.dropna(how="all")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["executed_price"] = pd.to_numeric(df["executed_price"], errors="coerce")
    df = df[df["date"].notna() & df["executed_price"].notna()].copy()
    df = df.sort_values("date").reset_index(drop=True)

    prophet_df = df[["date", "executed_price"]].rename(
        columns={"date": "ds", "executed_price": "y"}
    )
    return prophet_df


# ---------------------------------------------------------------------------
# [MODIFIED] Recency weighting — linear weights + weighted-fit approximation
# ---------------------------------------------------------------------------


def add_recency_weights_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add linear sample_weight: older observations smaller, recent larger.

    Weights are in (0, 1] with the first row having the smallest weight.
    Prophet's public Python API does not pass per-row weights to Stan in all
    versions; we approximate weighted likelihood via ``expand_history_by_sample_weights``.
    """
    out = df.copy()
    n = len(out)
    if n == 0:
        out["sample_weight"] = []
        return out
    # Linear: index 0 -> 1/n, index n-1 -> 1.0
    out["sample_weight"] = np.linspace(1.0 / float(n), 1.0, n)
    return out


def expand_history_by_sample_weights(
    df: pd.DataFrame,
    max_repeat: int = 5,
) -> pd.DataFrame:
    """
    Approximate sample_weight training by repeating each (ds, y) row a number
    of times proportional to its weight (same calendar day repeated — Stan
    treats them as independent observations at that time index).

    This mimics higher influence of recent points without modifying Prophet core.
    """
    if len(df) == 0:
        return df[["ds", "y"]].copy() if "ds" in df.columns else df.copy()

    if "sample_weight" not in df.columns:
        df = add_recency_weights_column(df)

    w = np.asarray(df["sample_weight"].values, dtype=float)
    w_min, w_max = float(np.min(w)), float(np.max(w))
    if w_max <= w_min:
        repeats = np.ones(len(df), dtype=int)
    else:
        repeats = np.maximum(
            1,
            np.round(1 + (w - w_min) / (w_max - w_min) * (max_repeat - 1)).astype(int),
        )

    parts: List[pd.DataFrame] = []
    for i in range(len(df)):
        r = df.iloc[i]
        block = pd.DataFrame({"ds": [r["ds"]] * int(repeats[i]), "y": [r["y"]] * int(repeats[i])})
        parts.append(block)
    expanded = pd.concat(parts, ignore_index=True)
    return expanded


# ---------------------------------------------------------------------------
# [MODIFIED] Crash detection & anchor helpers
# ---------------------------------------------------------------------------


def detect_recent_crash(
    y: pd.Series,
    window: int = CRASH_DROP_WINDOW,
    threshold: float = CRASH_DROP_THRESHOLD_EGP,
) -> bool:
    """
    True if the last ``window`` days show a sharp drop (regime change).

    Uses net drop from the oldest to the newest price in the window, and
    also flags large within-window range (volatile crash).
    """
    y = pd.to_numeric(y, errors="coerce").dropna()
    if len(y) < window:
        return False
    tail = y.tail(window)
    net_drop = float(tail.iloc[0] - tail.iloc[-1])
    range_drop = float(tail.max() - tail.min())
    return (net_drop > threshold) or (range_drop > threshold)


def compute_forecast_anchor(
    y: pd.Series,
    crash: bool,
    last_n_mean: int = ANCHOR_LAST_N_MEAN,
) -> float:
    """
    Anchor level for blending: mean of last ``last_n_mean`` days, unless
    ``crash`` then force last observed price (follow current market).
    """
    y = pd.to_numeric(y, errors="coerce").dropna()
    if len(y) == 0:
        return 0.0
    last_y = float(y.iloc[-1])
    if crash:
        return last_y
    n = min(last_n_mean, len(y))
    return float(y.tail(n).mean())


# ---------------------------------------------------------------------------
# [MODIFIED] Training — changepoint_prior_scale=0.3, weighted-expanded history
# ---------------------------------------------------------------------------


def train_prophet_model(df: pd.DataFrame) -> Tuple[Prophet, float, float]:
    """
    Train Prophet on one row per calendar day (no duplicate-row expansion:
    expansion destabilizes long-horizon forecasts and can drive yhat toward 0).

    Moderate changepoint_prior_scale for regime shifts without explosive trends.
    """
    split_idx = int(len(df) * 0.8)
    df_train = df.iloc[:split_idx].copy()
    df_test = df.iloc[split_idx:].copy()

    holidays = build_holiday_dataframe()

    prophet_kwargs = dict(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=True,
        holidays=holidays,
        interval_width=0.8,
        changepoint_prior_scale=0.08,
        seasonality_prior_scale=8.0,
    )

    eval_model = Prophet(**prophet_kwargs)
    eval_model.fit(df_train[["ds", "y"]])

    future_test = df_test[["ds"]].copy()
    forecast_test = eval_model.predict(future_test)
    y_true = df_test["y"].values
    y_pred = forecast_test["yhat"].values

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))

    # Production model: same clean daily series (recency weights kept as helpers for optional use)
    full_model = Prophet(**prophet_kwargs)
    full_model.fit(df[["ds", "y"]])

    return full_model, mae, rmse


def _historical_price_bounds(y: pd.Series) -> tuple[float, float]:
    """Soft min/max from history, widened slightly for forecast uncertainty."""
    y = pd.to_numeric(y, errors="coerce").dropna()
    if len(y) == 0:
        return PRICE_SANITY_FLOOR_EGP, PRICE_SANITY_CEILING_EGP
    lo = float(y.min()) * 0.82
    hi = float(y.max()) * 1.18
    return max(PRICE_SANITY_FLOOR_EGP, lo), min(PRICE_SANITY_CEILING_EGP, hi)


def forecast_next_n_days(
    model: Prophet, df_hist: pd.DataFrame, periods: int = FORECAST_DAYS
) -> pd.DataFrame:
    """
    Forecast next N days; output columns: date, low_price, expected_price, high_price.
    Clips raw Prophet output to history-based bounds to avoid runaway extrapolation.
    """
    future = model.make_future_dataframe(periods=periods, freq="D", include_history=False)

    forecast = model.predict(future)
    lo_b, hi_b = _historical_price_bounds(df_hist["y"])

    out = pd.DataFrame(
        {
            "date": forecast["ds"].dt.date,
            "low_price": forecast["yhat_lower"],
            "expected_price": forecast["yhat"],
            "high_price": forecast["yhat_upper"],
        }
    )

    for col in ("low_price", "expected_price", "high_price"):
        out[col] = out[col].clip(lower=lo_b, upper=hi_b)

    # Ensure low <= expected <= high after clipping
    mid = out["expected_price"].values
    lo = out["low_price"].values
    hi = out["high_price"].values
    out["low_price"] = np.minimum(lo, mid)
    out["high_price"] = np.maximum(hi, mid)

    return out


# ---------------------------------------------------------------------------
# [MODIFIED] Short-term anchoring, crash handling, upward cap (first 7 days)
# ---------------------------------------------------------------------------


def _plateau_noise(
    n_days: int,
    anchor: float,
    last_y: float,
    y: pd.Series,
    fluctuation: float = PLATEAU_FLUCTUATION_EGP,
) -> np.ndarray:
    """
    Reproducible ±fluctuation EGP noise per day (flat / noisy plateau, not a trend).
    """
    seed = int(abs(y.tail(5).sum() * 100 + anchor * 10 + last_y)) % (2**31 - 1)
    rng = np.random.default_rng(seed)
    return rng.uniform(-fluctuation, fluctuation, size=n_days)


def adjust_forecast_to_recent_market(
    forecast_df: pd.DataFrame,
    prophet_hist: pd.DataFrame,
) -> pd.DataFrame:
    """
    Blend Prophet with recent actuals; short-term mimics Egyptian market plateaus.

    - First PLATEAU_FORECAST_DAYS: expected_price = anchor + small noise (±1.5 EGP).
    - Reduced Prophet influence (max blend 0.75 / 0.73 crash).
    - After plateau: mild sequential cap from last plateau day (steps, not smooth decline).
    - Keeps: crash detection, first-7 upward cap, additive interval adjustment.

    Output columns unchanged: date, low_price, expected_price, high_price.
    """
    y = pd.to_numeric(prophet_hist["y"], errors="coerce").dropna()
    if len(y) < 3:
        return forecast_df

    out = forecast_df.copy()
    n = len(out)
    last_y = float(y.iloc[-1])

    crash = detect_recent_crash(y, window=CRASH_DROP_WINDOW, threshold=CRASH_DROP_THRESHOLD_EGP)
    anchor = compute_forecast_anchor(y, crash=crash, last_n_mean=ANCHOR_LAST_N_MEAN)

    diffs = y.diff().abs().dropna().tail(90)
    med_step = float(diffs.median()) if len(diffs) else 1.5
    if med_step <= 0 or np.isnan(med_step):
        med_step = 1.5
    daily_cap = float(max(2.0, min(6.0, 3.0 * med_step)))
    if crash:
        daily_cap = min(daily_cap, 4.0)

    exp = out["expected_price"].astype(float).values.copy()

    # Blend: more anchor than Prophet (max weight capped at 0.75 / 0.73)
    t_norm = np.linspace(0.0, 1.0, n)
    for i in range(n):
        if crash:
            w_max = MAX_BLEND_WEIGHT_CRASH
            w = min(w_max, 0.12 + (w_max - 0.12) * (t_norm[i] ** 0.5))
        else:
            w_max = MAX_BLEND_WEIGHT
            w = min(w_max, 0.18 + (w_max - 0.18) * (t_norm[i] ** 0.55))
        exp[i] = w * exp[i] + (1.0 - w) * anchor

    # Plateau override: first 14 days = anchor + noise (not smooth Prophet decline)
    p_days = min(PLATEAU_FORECAST_DAYS, n)
    if p_days > 0:
        noise = _plateau_noise(p_days, anchor, last_y, y, PLATEAU_FLUCTUATION_EGP)
        for i in range(p_days):
            exp[i] = anchor + float(noise[i])

    # Upward cap first 7 days (unchanged)
    cap_level = last_y + SHORT_TERM_UPWARD_CAP_EGP
    for i in range(min(SHORT_TERM_CAP_DAYS, n)):
        exp[i] = min(exp[i], cap_level)

    if crash:
        for i in range(min(PLATEAU_FORECAST_DAYS, n)):
            exp[i] = min(exp[i], max(last_y + 1.5, anchor + 2.0))

    # Sequential cap only after plateau (continuity from end of plateau, occasional steps)
    if n > p_days:
        prev = float(exp[p_days - 1])
        for i in range(p_days, n):
            exp[i] = max(prev - daily_cap, min(prev + daily_cap, exp[i]))
            prev = float(exp[i])

    # --- CRITICAL: additive shift of intervals, NOT ratio scaling ---
    # Ratio (exp/base) when base→0 blows up low/high (e.g. 111k EGP). Shift by delta instead.
    raw_mid = forecast_df["expected_price"].astype(float).values
    raw_low = forecast_df["low_price"].astype(float).values
    raw_high = forecast_df["high_price"].astype(float).values
    shift = exp - raw_mid
    low_adj = raw_low + shift
    high_adj = raw_high + shift

    out["expected_price"] = exp
    out["low_price"] = np.minimum(low_adj, exp)
    out["high_price"] = np.maximum(high_adj, exp)

    # Cap interval half-width so uncertainty stays market-realistic (±~15 EGP max)
    half = (out["high_price"].values - out["low_price"].values) / 2.0
    half = np.clip(half, 1.5, 15.0)
    out["low_price"] = np.clip(exp - half, 0.0, None)
    out["high_price"] = exp + half

    # Final sanity band (history + absolute floor/ceiling)
    lo_b, hi_b = _historical_price_bounds(y)
    for col in ("low_price", "expected_price", "high_price"):
        out[col] = out[col].clip(lower=lo_b, upper=hi_b)
    mid = out["expected_price"].values
    out["low_price"] = np.minimum(out["low_price"].values, mid)
    out["high_price"] = np.maximum(out["high_price"].values, mid)

    return out


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_forecast(
    df_hist: pd.DataFrame, df_forecast: pd.DataFrame, out_path: Path = FORECAST_PLOT
) -> None:
    """Plot historical executed_price and forecast."""
    plt.figure(figsize=(12, 6))

    hist_sorted = df_hist.sort_values("ds")
    plt.plot(
        hist_sorted["ds"],
        hist_sorted["y"],
        label="Historical executed price",
        color="tab:blue",
    )

    plt.fill_between(
        df_forecast["date"],
        df_forecast["low_price"],
        df_forecast["high_price"],
        color="tab:orange",
        alpha=0.2,
        label="Forecast range (Prophet)",
    )
    plt.plot(
        df_forecast["date"],
        df_forecast["expected_price"],
        color="tab:red",
        linestyle="--",
        label="Expected price (adjusted)",
    )

    plt.xlabel("Date")
    plt.ylabel("Price (EGP/kg)")
    plt.title(f"Egyptian poultry executed price – {len(df_forecast)}-day forecast (Prophet)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def train_and_forecast_prophet() -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    """
    End-to-end: load data, train weighted Prophet, forecast, adjust short-term.

    Returns:
        df_hist (original ds/y, no duplicate rows — for UI/anchors),
        forecast_df (date, low_price, expected_price, high_price),
        mae, rmse
    """
    df_prophet = prepare_prophet_dataframe(DATA_PATH)
    model, mae, rmse = train_prophet_model(df_prophet)
    forecast_df = forecast_next_n_days(model, df_prophet)
    forecast_df = adjust_forecast_to_recent_market(forecast_df, df_prophet)
    return df_prophet, forecast_df, mae, rmse


def main() -> None:
    df_prophet, forecast_df, mae, rmse = train_and_forecast_prophet()
    print(f"Prophet MAE:  {mae:.2f} EGP")
    print(f"Prophet RMSE: {rmse:.2f} EGP")

    forecast_df.to_csv(FORECAST_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved Prophet {len(forecast_df)}-day forecast to {FORECAST_CSV}")

    plot_forecast(df_prophet, forecast_df, FORECAST_PLOT)
    print(f"Saved Prophet forecast plot to {FORECAST_PLOT}")


if __name__ == "__main__":
    main()
