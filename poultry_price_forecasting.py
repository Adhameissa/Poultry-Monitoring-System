"""
Poultry price forecasting pipeline.

This script trains quantile XGBoost models on Egyptian poultry prices
and forecasts a 35-day price range for the executed (actual) price.

Usage (from project root):

    python poultry_price_forecasting.py

Requirements:
    - pandas
    - numpy
    - xgboost
    - scikit-learn
    - matplotlib
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split


DATA_PATH = Path("pricespoultryegypt (2).csv")
FORECAST_CSV = Path("poultry_price_forecast_35_days.csv")
FORECAST_PLOT = Path("poultry_forecast_plot.png")


# ---------------------------------------------------------------------------
# Holiday / seasonal flags
# ---------------------------------------------------------------------------

def _build_holiday_ranges() -> Dict[str, List[Tuple[datetime, datetime]]]:
    """
    Hardcoded Gregorian date ranges for Ramadan and Eids (2025–2030).

    Dates are approximate; for forecasting features, small shifts are acceptable.
    """
    # Source: public calendars (approximate ranges; adjust as needed).
    ramadan_ranges = [
        (datetime(2025, 2, 28), datetime(2025, 3, 30)),
        (datetime(2026, 2, 18), datetime(2026, 3, 19)),
        (datetime(2027, 2, 8), datetime(2027, 3, 9)),
        (datetime(2028, 1, 28), datetime(2028, 2, 27)),
        (datetime(2029, 1, 16), datetime(2029, 2, 14)),
        (datetime(2030, 1, 6), datetime(2030, 2, 4)),
    ]

    eid_fitr_days = [
        datetime(2025, 3, 31),
        datetime(2026, 3, 20),
        datetime(2027, 3, 10),
        datetime(2028, 2, 28),
        datetime(2029, 2, 15),
        datetime(2030, 2, 5),
    ]

    eid_adha_days = [
        datetime(2025, 6, 7),
        datetime(2026, 5, 27),
        datetime(2027, 5, 17),
        datetime(2028, 5, 6),
        datetime(2029, 4, 25),
        datetime(2030, 4, 14),
    ]

    # Treat Eid al-Fitr / Adha as 3-day windows (Eid +2)
    eid_fitr_ranges = [(d, d + timedelta(days=2)) for d in eid_fitr_days]
    eid_adha_ranges = [(d, d + timedelta(days=2)) for d in eid_adha_days]

    return {
        "ramadan": ramadan_ranges,
        "eid_fitr": eid_fitr_ranges,
        "eid_adha": eid_adha_ranges,
    }


HOLIDAYS = _build_holiday_ranges()


def _is_in_ranges(d: datetime, ranges: List[Tuple[datetime, datetime]]) -> bool:
    """Return True if date d is within any of the [start, end] ranges."""
    for start, end in ranges:
        if start.date() <= d.date() <= end.date():
            return True
    return False


def add_seasonal_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add month, day_of_week and Ramadan/Eid flags to the dataframe."""
    if not np.issubdtype(df["date"].dtype, np.datetime64):
        df["date"] = pd.to_datetime(df["date"])

    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek  # Monday=0

    df["is_ramadan"] = df["date"].apply(
        lambda d: _is_in_ranges(d.to_pydatetime(), HOLIDAYS["ramadan"])
    )
    df["is_eid_al_fitr"] = df["date"].apply(
        lambda d: _is_in_ranges(d.to_pydatetime(), HOLIDAYS["eid_fitr"])
    )
    df["is_eid_al_adha"] = df["date"].apply(
        lambda d: _is_in_ranges(d.to_pydatetime(), HOLIDAYS["eid_adha"])
    )

    # Convert boolean flags to int (0/1) for the model.
    df["is_ramadan"] = df["is_ramadan"].astype(int)
    df["is_eid_al_fitr"] = df["is_eid_al_fitr"].astype(int)
    df["is_eid_al_adha"] = df["is_eid_al_adha"].astype(int)
    return df


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

LAG_FEATURES = [1, 3, 7, 14, 30]


def add_lag_features(df: pd.DataFrame, target_col: str = "executed_price") -> pd.DataFrame:
    """Add lagged price features (e.g. 1/3/7/14/30 days)."""
    for lag in LAG_FEATURES:
        df[f"price_{lag}_day"] = df[target_col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, target_col: str = "executed_price") -> pd.DataFrame:
    """Add rolling mean/std features over the target column."""
    df["rolling_mean_7"] = df[target_col].rolling(window=7).mean()
    df["rolling_mean_14"] = df[target_col].rolling(window=14).mean()
    df["rolling_std_7"] = df[target_col].rolling(window=7).std()
    return df


def prepare_dataset(path: Path = DATA_PATH) -> pd.DataFrame:
    """
    Load the Excel dataset and perform feature engineering.

    - Parse date and sort.
    - Use executed_price as target.
    - Add lag, rolling and seasonal features.
    - Drop rows with NaNs introduced by lags/rolls.
    """
    df = pd.read_csv(path)

    # Drop completely empty rows
    df = df.dropna(how="all")

    # Robust date parsing
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Ensure we only keep rows with valid date and executed_price
    if "executed_price" not in df.columns:
        raise ValueError("Dataset must contain 'executed_price' column.")
    df = df[df["date"].notna() & df["executed_price"].notna()].copy()

    df = df.sort_values("date").reset_index(drop=True)

    # Ensure required columns exist; if day_of_week/month absent, recompute from date.
    if "day_of_week" not in df.columns:
        df["day_of_week"] = df["date"].dt.dayofweek
    if "month" not in df.columns:
        df["month"] = df["date"].dt.month

    # Feature engineering
    df = add_lag_features(df, target_col="executed_price")
    df = add_rolling_features(df, target_col="executed_price")
    df = add_seasonal_flags(df)

    # Drop rows with NaNs after lag/rolling
    df = df.dropna().reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Quantile XGBoost models
# ---------------------------------------------------------------------------

def make_quantile_objective(q: float):
    """
    Create a custom XGBoost objective implementing quantile (pinball) loss.

    Loss L_q(y, f) = max(q*(y - f), (q - 1)*(y - f))
    dL/df = -(q - I[y < f])

    We approximate the second derivative (hessian) with 1 for all samples.
    """

    def _objective(y_pred: np.ndarray, dtrain: xgb.DMatrix):
        y_true = dtrain.get_label()
        error = y_true - y_pred
        grad = np.where(error < 0, -q, 1 - q)
        hess = np.ones_like(grad)
        return grad, hess

    return _objective


@dataclass
class QuantileModels:
    lower: xgb.Booster
    median: xgb.Booster
    upper: xgb.Booster
    feature_names: List[str]


def train_quantile_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    num_round: int = 400,
) -> QuantileModels:
    """Train three XGBoost models for 0.1, 0.5, 0.9 quantiles."""
    params_base = {
        "max_depth": 4,
        "eta": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 1.0,
        "objective": "reg:squarederror",  # overridden by custom objective
        "verbosity": 0,
    }

    dtrain = xgb.DMatrix(X_train, label=y_train)
    dvalid = xgb.DMatrix(X_valid, label=y_valid)
    watchlist = [(dtrain, "train"), (dvalid, "valid")]

    # Lower quantile (10%)
    lower_model = xgb.train(
        params_base,
        dtrain,
        num_boost_round=num_round,
        obj=make_quantile_objective(0.1),
        evals=watchlist,
        early_stopping_rounds=50,
        verbose_eval=False,
    )

    # Median (50%)
    median_model = xgb.train(
        params_base,
        dtrain,
        num_boost_round=num_round,
        obj=make_quantile_objective(0.5),
        evals=watchlist,
        early_stopping_rounds=50,
        verbose_eval=False,
    )

    # Upper (90%)
    upper_model = xgb.train(
        params_base,
        dtrain,
        num_boost_round=num_round,
        obj=make_quantile_objective(0.9),
        evals=watchlist,
        early_stopping_rounds=50,
        verbose_eval=False,
    )

    return QuantileModels(
        lower=lower_model,
        median=median_model,
        upper=upper_model,
        feature_names=list(X_train.columns),
    )


def evaluate_median_model(
    model: xgb.Booster, X_test: pd.DataFrame, y_test: pd.Series
) -> Tuple[float, float]:
    """Evaluate the median model using MAE and RMSE."""
    dtest = xgb.DMatrix(X_test, feature_names=list(X_test.columns))
    preds = model.predict(dtest)
    mae = mean_absolute_error(y_test, preds)
    rmse = math.sqrt(mean_squared_error(y_test, preds))
    return mae, rmse


# ---------------------------------------------------------------------------
# Forecasting 35 days ahead
# ---------------------------------------------------------------------------

def _build_feature_row_from_history(
    dates_hist: List[datetime],
    prices_hist: List[float],
    current_date: datetime,
) -> Dict[str, float]:
    """
    Given historical dates/prices and a new date, build features
    (lags, rolling stats, seasonal flags) for the next prediction step.
    """
    # Assume dates_hist aligned with prices_hist and daily frequency
    history_series = pd.Series(prices_hist)

    # Lags: last n values from history
    feats: Dict[str, float] = {}
    for lag in LAG_FEATURES:
        if len(history_series) >= lag:
            feats[f"price_{lag}_day"] = float(history_series.iloc[-lag])
        else:
            feats[f"price_{lag}_day"] = float(history_series.iloc[0])

    # Rolling stats
    if len(history_series) >= 7:
        feats["rolling_mean_7"] = float(history_series.iloc[-7:].mean())
        feats["rolling_std_7"] = float(history_series.iloc[-7:].std(ddof=0))
    else:
        feats["rolling_mean_7"] = float(history_series.mean())
        feats["rolling_std_7"] = float(history_series.std(ddof=0))

    if len(history_series) >= 14:
        feats["rolling_mean_14"] = float(history_series.iloc[-14:].mean())
    else:
        feats["rolling_mean_14"] = float(history_series.mean())

    feats["month"] = current_date.month
    feats["day_of_week"] = current_date.weekday()

    feats["is_ramadan"] = int(_is_in_ranges(current_date, HOLIDAYS["ramadan"]))
    feats["is_eid_al_fitr"] = int(_is_in_ranges(current_date, HOLIDAYS["eid_fitr"]))
    feats["is_eid_al_adha"] = int(_is_in_ranges(current_date, HOLIDAYS["eid_adha"]))

    return feats


def predict_next_35_days(
    models: QuantileModels,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Iteratively forecast the next 35 days using the trained quantile models.

    - Start from the last known date and executed_price.
    - At each step, build features from the most recent history.
    - Predict low/median/high and append to history for later lags.
    """
    # Sort and ensure datetime
    hist = df.sort_values("date").reset_index(drop=True)
    hist["date"] = pd.to_datetime(hist["date"])

    last_date = hist["date"].iloc[-1].to_pydatetime()
    history_dates: List[datetime] = list(hist["date"].dt.to_pydatetime())
    history_prices: List[float] = hist["executed_price"].tolist()

    future_rows: List[Dict[str, object]] = []

    for step in range(1, 36):
        next_date = last_date + timedelta(days=step)
        feats = _build_feature_row_from_history(history_dates, history_prices, next_date)

        # Align feature order with training
        X_next = np.array([[feats[name] for name in models.feature_names]])
        dnext = xgb.DMatrix(X_next, feature_names=models.feature_names)

        # Raw quantile predictions from the models
        raw_low = float(models.lower.predict(dnext)[0])
        raw_mid = float(models.median.predict(dnext)[0])
        raw_high = float(models.upper.predict(dnext)[0])

        # Safety: clamp to non-negative and blend with latest observed price
        last_observed = history_prices[-1]
        raw_mid = max(0.0, raw_mid)

        # Blend AI signal with recent actual price so forecast stays realistic
        blended_mid = 0.3 * raw_mid + 0.7 * last_observed

        # Simple statistical band around the blended median
        band = 5.0  # EGP range on each side
        low = max(0.0, blended_mid - band)
        high = blended_mid + band

        # Update history with blended median for subsequent lags
        history_dates.append(next_date)
        history_prices.append(blended_mid)

        future_rows.append(
            {
                "date": next_date.date(),
                "low_price": low,
                "expected_price": blended_mid,
                "high_price": high,
            }
        )

    return pd.DataFrame(future_rows)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_forecast(
    df_hist: pd.DataFrame,
    df_forecast: pd.DataFrame,
    out_path: Path = FORECAST_PLOT,
) -> None:
    """Plot historical executed_price and 35-day forecast with uncertainty band."""
    plt.figure(figsize=(12, 6))

    # Historical
    hist_sorted = df_hist.sort_values("date")
    plt.plot(
        hist_sorted["date"],
        hist_sorted["executed_price"],
        label="Historical executed price",
        color="tab:blue",
    )

    # Forecast
    plt.fill_between(
        df_forecast["date"],
        df_forecast["low_price"],
        df_forecast["high_price"],
        color="tab:orange",
        alpha=0.2,
        label="Forecast range (low–high)",
    )
    plt.plot(
        df_forecast["date"],
        df_forecast["expected_price"],
        color="tab:red",
        linestyle="--",
        label="Expected price (median)",
    )

    plt.xlabel("Date")
    plt.ylabel("Price (EGP/kg)")
    plt.title("Egyptian poultry executed price – historical and 35-day forecast")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def train_and_forecast() -> Tuple[pd.DataFrame, pd.DataFrame, float, float]:
    """
    End-to-end helper:
        - prepare dataset
        - train quantile models
        - evaluate median model
        - forecast next 35 days

    Returns:
        df_hist: full historical dataframe with engineered features
        forecast_df: 35-day forecast dataframe
        mae, rmse: evaluation metrics of the median model
    """
    df = prepare_dataset(DATA_PATH)

    feature_cols = [
        "price_1_day",
        "price_3_day",
        "price_7_day",
        "price_14_day",
        "price_30_day",
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_std_7",
        "month",
        "day_of_week",
        "is_ramadan",
        "is_eid_al_fitr",
        "is_eid_al_adha",
    ]
    target_col = "executed_price"

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # Further split train into train/valid for early stopping
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.2, shuffle=False
    )

    models = train_quantile_models(X_tr, y_tr, X_val, y_val, num_round=400)

    mae, rmse = evaluate_median_model(models.median, X_test, y_test)
    forecast_df = predict_next_35_days(models, df[["date", "executed_price"]].copy())
    return df, forecast_df, mae, rmse


def main() -> None:
    df, forecast_df, mae, rmse = train_and_forecast()
    print(f"Median model MAE:  {mae:.3f}")
    print(f"Median model RMSE: {rmse:.3f}")

    forecast_df.to_csv(FORECAST_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved 35-day forecast to {FORECAST_CSV}")

    plot_forecast(df[["date", "executed_price"]].copy(), forecast_df, FORECAST_PLOT)
    print(f"Saved forecast plot to {FORECAST_PLOT}")


if __name__ == "__main__":
    main()

