"""
Weather-aware helper for estimating broiler mortality and suggesting
start dates based on temperature and humidity in Egypt.

This module keeps the logic transparent and rule-based. **Adjusted
mortality %** is your farm baseline mortality multiplied by a **stress
multiplier** (mean over the grow-out window). Multipliers are not a
clinical forecast for one house; they are a **semi-quantitative index**
ranked from peer-reviewed evidence that heat, cold, and humidity shift
broiler losses **on average**.

Scientific basis (temperature, humidity, mortality risk)
---------------------------------------------------------
1. **Lara, L.J. & Rostagno, M.H. (2013).** Impact of heat stress on poultry
   production. *Animals*, 3(2), 356–369. https://doi.org/10.3390/ani3020356
   (PMID: 26487407). Review of heat stress, welfare, and production;
   thermal comfort for broilers commonly cited near **~18–22 °C**.

2. **Renaudeau, D., et al. (2012).** Adaptation to hot climate and strategies
   to alleviate heat stress in livestock production. *Animal*, 6(5),
   707–728. https://doi.org/10.1017/S1751731111002448 — combined
   environmental load (temperature and humidity).

3. **Daghir, N.J. (2008).** *Poultry production in hot climates.* CAB
   International. ISBN 9781845932589 — hot-climate poultry (incl. MENA).

4. **NRC (1994).** *Nutrient Requirements of Poultry.* 9th revised ed.
   National Academies Press — environmental effects on intake and growth.

**Implementation:** Forecast **daily maximum** °C and **humidity** are a
**coarse outdoor proxy** for heat load; real shed microclimate, age, and
ventilation differ. **Relative multipliers** below are **calibrated
ordinal scales** (optimal < warm < severe heat), not farm-specific
mortality rates from those papers.

It is safe to import from Flask handlers; if the `requests` library is
missing or the weather API is unavailable, functions will simply return
None or empty results so the UI can hide the advisory card gracefully.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None


# Visual Crossing: set VISUAL_CROSSING_API_KEY in the environment (e.g. .env)
# if the bundled key hits rate / cost limits (HTTP 429).
_VISUAL_CROSSING_KEY_FALLBACK = "5FWQYRLLSCRZTC9QTZNBUJC57"
_BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
_OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

# Default farm location when the farmer does not specify one.
DEFAULT_LOCATION = "Mansoura, Egypt"

# Rough coordinates for Open-Meteo when Visual Crossing is unavailable (no geocoder).
_LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "mansoura": (31.0409, 31.3785),
    "cairo": (30.0444, 31.2357),
    "alexandria": (31.2001, 29.9187),
    "giza": (30.0131, 31.2089),
}
_DEFAULT_COORDS = (31.0409, 31.3785)  # Mansoura

# --- Temperature bands (°C): daily maximum as outdoor proxy ---
# Thresholds follow Lara & Rostagno (2013) and reviews cited in the module
# docstring. Slight merge of “comfort” (~18–22) with finishing-bird upper
# TNZ seen in field summaries (up to ~24 °C) to avoid over-penalizing typical cycles.
TEMP_EXTREME_COLD_LT = 10.0
TEMP_COLD_MAX = 16.0  # below ~16 °C: cold stress band (NRC / cold-season reviews)
TEMP_COMFORT_LOW = 18.0  # Lara & Rostagno (2013) comfort region lower bound
TEMP_COMFORT_HIGH = 24.0  # upper thermoneutral-style bound for mixed-age proxy
TEMP_MILD_HEAT_LOW = 25.0  # gradient where heat stress rises in many broiler trials
TEMP_MILD_HEAT_HIGH = 30.0
TEMP_SEVERE_HEAT_LOW = 30.0  # >30 °C widely reported as detrimental (Lara & Rostagno 2013)
TEMP_SEVERE_HEAT_HIGH = 35.0
TEMP_EXTREME_HEAT_GT = 35.0

# Combined heat + humidity: high RH limits evaporative cooling (Renaudeau et al. 2012).
HUMIDITY_ESCALATE_RH_MIN = 65.0  # %
HUMIDITY_ESCALATE_TEMP_MIN = 28.0  # °C — escalate band only when already warm

# Mortality multipliers vs farm baseline: ordinal calibration from review-level
# risk ordering (severe heat >> comfort); not literal % points from one trial.
_MULT_COMFORT = 0.80
_MULT_WARM_TRANSITION = 0.92  # 22–24 °C edge of comfort in some summaries
_MULT_MILD_HEAT = 1.00
_MULT_SEVERE_HEAT = 1.30
_MULT_EXTREME_HEAT = 1.60
_MULT_COLD = 1.10
_MULT_EXTREME_COLD = 1.30


@dataclass
class WeatherCandidate:
    """Represents one possible cycle start window and its risk profile."""

    start_date: _dt.date
    end_date: _dt.date
    adjusted_mortality_percent: float
    risk_label: str  # "low" | "medium" | "high"
    avg_temp_max: float
    avg_humidity: float
    optimal_days: int
    mild_heat_days: int
    severe_heat_days: int
    extreme_heat_days: int


def _visual_crossing_api_key() -> str:
    return (
        (os.environ.get("VISUAL_CROSSING_API_KEY") or "").strip()
        or _VISUAL_CROSSING_KEY_FALLBACK
    )


def _coords_for_location(location: str) -> tuple[float, float]:
    low = location.lower()
    for needle, xy in _LOCATION_COORDS.items():
        if needle in low:
            return xy
    return _DEFAULT_COORDS


def _normalise_vc_days(raw: list) -> List[dict]:
    out: List[dict] = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        try:
            dt_raw = d.get("datetime")
            day = _dt.date.fromisoformat(str(dt_raw)[:10])
        except Exception:
            continue
        d = dict(d)
        d["date"] = day
        out.append(d)
    return out


def _fetch_daily_visual_crossing(
    location: str, start: _dt.date, end: _dt.date
) -> List[dict]:
    """
    Visual Crossing timeline API. Location must be URL-encoded in the path.
    """
    if requests is None:
        return []
    key = _visual_crossing_api_key()
    if not key:
        return []

    path_loc = quote(location.strip() or DEFAULT_LOCATION, safe="")
    params = {
        "unitGroup": "metric",
        "elements": "datetime,tempmax,tempmin,humidity",
        "key": key,
        "contentType": "json",
    }

    try:
        url = f"{_BASE_URL}/{path_loc}/{start.isoformat()}/{end.isoformat()}"
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        days = _normalise_vc_days(data.get("days") or [])
        return [d for d in days if d.get("date") is not None]
    except Exception:
        return []


def _pad_daily_to_range(
    partial: List[dict],
    start: _dt.date,
    end: _dt.date,
) -> List[dict]:
    """Fill every calendar day in [start, end] using partial rows; pad gaps with local averages."""
    by_date: dict[_dt.date, dict] = {}
    for d in partial:
        day = d.get("date")
        if isinstance(day, _dt.date):
            by_date[day] = d

    if not by_date:
        return []

    ordered = sorted(by_date.items(), key=lambda x: x[0])
    # Pad forward: carry last known temp/humidity through gaps (typical when forecast horizon is short)
    last_t = 26.0
    last_h = 55.0
    out: List[dict] = []
    cur = start
    while cur <= end:
        if cur in by_date:
            row = by_date[cur]
            try:
                last_t = float(row.get("tempmax") or last_t)
            except (TypeError, ValueError):
                pass
            try:
                last_h = float(row.get("humidity") or last_h)
            except (TypeError, ValueError):
                pass
            out.append(row)
        else:
            out.append(
                {
                    "date": cur,
                    "datetime": cur.isoformat(),
                    "tempmax": last_t,
                    "humidity": last_h,
                }
            )
        cur += _dt.timedelta(days=1)

    return out


def _fetch_daily_open_meteo(
    location: str, start: _dt.date, end: _dt.date
) -> List[dict]:
    """
    Free Open-Meteo forecast (no API key). Short horizon; `_pad_daily_to_range` extends.
    """
    if requests is None:
        return []
    lat, lon = _coords_for_location(location)
    try:
        r = requests.get(
            _OPEN_METEO_FORECAST,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,relative_humidity_2m_mean",
                "timezone": "Africa/Cairo",
                "forecast_days": 16,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        times = data.get("daily", {}).get("time") or []
        tmax = data.get("daily", {}).get("temperature_2m_max") or []
        rh = data.get("daily", {}).get("relative_humidity_2m_mean") or []
        partial: List[dict] = []
        for i, tstr in enumerate(times):
            try:
                day = _dt.date.fromisoformat(str(tstr)[:10])
            except Exception:
                continue
            try:
                tm = float(tmax[i]) if i < len(tmax) else 25.0
            except (TypeError, ValueError, IndexError):
                tm = 25.0
            try:
                hm = float(rh[i]) if i < len(rh) else 55.0
            except (TypeError, ValueError, IndexError):
                hm = 55.0
            partial.append(
                {
                    "date": day,
                    "datetime": day.isoformat(),
                    "tempmax": tm,
                    "humidity": hm,
                }
            )
        return _pad_daily_to_range(partial, start, end)
    except Exception:
        return []


def _fetch_daily_weather(
    location: str, start: _dt.date, end: _dt.date
) -> List[dict]:
    """
    Fetch daily weather (temp, humidity) for [start, end] inclusive.
    Tries Visual Crossing first, then Open-Meteo (no key) so the UI keeps working
    when VC quota is exceeded.
    """
    span = (end - start).days + 1
    days = _fetch_daily_visual_crossing(location, start, end)
    if span > 0 and len(days) >= span * 0.5:
        return _pad_daily_to_range(days, start, end)
    om = _fetch_daily_open_meteo(location, start, end)
    if om:
        return om
    if days:
        return _pad_daily_to_range(days, start, end)
    return []


def _classify_temp_band(temp_c: float) -> str:
    """
    Classify daily Tmax into stress bands (see module docstring for citations).
    Uses named constants aligned with Lara & Rostagno (2013), Renaudeau et al. (2012).
    """
    if temp_c < TEMP_EXTREME_COLD_LT:
        return "extreme_cold"
    if temp_c <= TEMP_COLD_MAX:
        return "cold"
    if TEMP_COMFORT_LOW <= temp_c < 22.0:
        return "optimal"  # core comfort ~18–22 °C (review consensus)
    if 22.0 <= temp_c <= TEMP_COMFORT_HIGH:
        return "warm_transition"  # upper comfort / early heat sensitivity
    if TEMP_MILD_HEAT_LOW <= temp_c <= TEMP_MILD_HEAT_HIGH:
        return "mild_heat"
    if TEMP_SEVERE_HEAT_LOW < temp_c <= TEMP_SEVERE_HEAT_HIGH:
        return "severe_heat"
    if temp_c > TEMP_EXTREME_HEAT_GT:
        return "extreme_heat"
    # Gaps 16–17 °C: cool but not full cold band — treat as mild heat index-wise.
    return "mild_heat"


def _apply_humidity_adjustment(band: str, temp_c: float, humidity: float) -> str:
    """
    When RH is high, evaporative heat loss is limited — combined stress
    (temperature–humidity) worsens heat load (Renaudeau et al. 2012).
    Escalate one stage along the heat axis only if already warm enough.
    """
    if temp_c < HUMIDITY_ESCALATE_TEMP_MIN or humidity < HUMIDITY_ESCALATE_RH_MIN:
        return band

    order = ["optimal", "warm_transition", "mild_heat", "severe_heat", "extreme_heat"]
    if band not in order:
        return band

    idx = order.index(band)
    if idx < len(order) - 1:
        return order[idx + 1]
    return band


def _band_multiplier(band: str) -> float:
    """Relative mortality **index** vs farm baseline (ordinal; see module docstring)."""
    return {
        "optimal": _MULT_COMFORT,
        "warm_transition": _MULT_WARM_TRANSITION,
        "mild_heat": _MULT_MILD_HEAT,
        "severe_heat": _MULT_SEVERE_HEAT,
        "extreme_heat": _MULT_EXTREME_HEAT,
        "cold": _MULT_COLD,
        "extreme_cold": _MULT_EXTREME_COLD,
    }.get(band, _MULT_MILD_HEAT)


def _multiplier_to_risk_label(mult: float) -> str:
    """Convert a mortality multiplier into a coarse risk label."""
    if mult <= 0.95:
        return "low"
    if mult <= 1.25:
        return "medium"
    return "high"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_weather_based_recommendations(
    base_mortality_percent: float,
    location: Optional[str] = None,
    cycle_days: int = 35,
    horizon_days: int = 30,
) -> Optional[dict]:
    """
    Build a small set of weather-aware start date recommendations.

    Strategy:
        - Fetch daily weather for [today, today + horizon_days + cycle_days].
        - Evaluate a few candidate start dates (today, +14d, +30d).
        - For each, compute an average mortality multiplier based on
          temperature & humidity over the grow-out period.
        - Return the candidates plus the index of the best one.

    Returns None if weather cannot be fetched.
    """
    # Zero mortality skips weather math in older versions — use a typical baseline for stress bands.
    base_eff = float(base_mortality_percent)
    if base_eff <= 0:
        base_eff = 5.0

    loc = (location or DEFAULT_LOCATION).strip() or DEFAULT_LOCATION
    today = _dt.date.today()
    last_needed = today + _dt.timedelta(days=horizon_days + cycle_days)

    days = _fetch_daily_weather(loc, today, last_needed)
    if not days:
        return None

    # Index by date for quick slicing.
    by_date: dict[_dt.date, dict] = {d["date"]: d for d in days}

    candidate_offsets = [0, 14, 30]
    candidates: list[WeatherCandidate] = []

    for offset in candidate_offsets:
        start = today + _dt.timedelta(days=offset)
        end = start + _dt.timedelta(days=cycle_days)

        window_days: list[dict] = []
        cur = start
        while cur < end:
            d = by_date.get(cur)
            if d is not None:
                window_days.append(d)
            cur += _dt.timedelta(days=1)

        # If we have too few days (e.g. forecast horizon too short), skip.
        if len(window_days) < cycle_days * 0.6:
            continue

        multipliers: list[float] = []
        temps: list[float] = []
        hums: list[float] = []
        optimal_days = 0
        mild_days = 0
        severe_days = 0
        extreme_days = 0
        for d in window_days:
            tempmax = float(d.get("tempmax") or 0.0)
            humidity = float(d.get("humidity") or 50.0)
            band = _classify_temp_band(tempmax)
            band = _apply_humidity_adjustment(band, tempmax, humidity)
            multipliers.append(_band_multiplier(band))
            temps.append(tempmax)
            hums.append(humidity)
            if band in ("optimal", "warm_transition"):
                optimal_days += 1
            elif band == "mild_heat":
                mild_days += 1
            elif band == "severe_heat":
                severe_days += 1
            elif band == "extreme_heat":
                extreme_days += 1

        if not multipliers:
            continue

        avg_mult = sum(multipliers) / len(multipliers)
        avg_temp = sum(temps) / len(temps) if temps else 0.0
        avg_hum = sum(hums) / len(hums) if hums else 0.0
        adjusted = _clamp(
            base_eff * avg_mult,
            low=1.0,
            high=20.0,
        )
        risk = _multiplier_to_risk_label(avg_mult)
        candidates.append(
            WeatherCandidate(
                start_date=start,
                end_date=end,
                adjusted_mortality_percent=adjusted,
                risk_label=risk,
                avg_temp_max=avg_temp,
                avg_humidity=avg_hum,
                optimal_days=optimal_days,
                mild_heat_days=mild_days,
                severe_heat_days=severe_days,
                extreme_heat_days=extreme_days,
            )
        )

    if not candidates:
        return None

    # Lower adjusted mortality is better.
    best_idx = min(
        range(len(candidates)),
        key=lambda i: candidates[i].adjusted_mortality_percent,
    )

    return {
        "location": loc,
        "candidates": candidates,
        "best_index": best_idx,
    }

