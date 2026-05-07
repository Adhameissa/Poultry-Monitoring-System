"""
Pure financial calculations for the Financial Intelligence Module.

All functions here are independent of Flask and any vision models.
Values are expected to be numeric (int/float); unit handling is done
at the view/template layer (e.g. EGP currency formatting).
"""

from typing import Dict, Any, List, Tuple
import math


def calculate_startup_plan(
    number_of_chickens: float,
    chick_price: float,
    feed_cost_per_chicken_per_day: float,
    electricity_cost_per_day: float,
    labor_cost_per_day: float,
    medicine_cost_total: float,
    water_cost_total: float,
    farm_rent: float,
    expected_days_to_sell: float,
    expected_avg_weight_kg: float,
    mortality_rate_percent: float,
    selling_price_per_kg: float,
) -> Dict[str, Any]:
    """
    Compute startup financial metrics for a new poultry cycle.

    Formulas are provided by the product spec:
        live_chickens = number_of_chickens * (1 - mortality_rate_percent/100)
        total_weight = live_chickens * expected_avg_weight_kg
        revenue = total_weight * selling_price_per_kg
        feed_total = feed_cost_per_chicken_per_day * expected_days_to_sell * number_of_chickens
        total_cost = feed_total +
                     electricity_cost_per_day * expected_days_to_sell +
                     labor_cost_per_day * expected_days_to_sell +
                     medicine_cost_total +
                     water_cost_total +
                     farm_rent +
                     (chick_price * number_of_chickens)
        profit = revenue - total_cost
        roi = profit / total_cost if total_cost>0 else 0
        break_even_price = total_cost / total_weight if total_weight>0 else 0
    """

    mortality_rate = max(0.0, mortality_rate_percent) / 100.0

    live_chickens = max(0.0, number_of_chickens * (1.0 - mortality_rate))
    total_weight = max(0.0, live_chickens * max(0.0, expected_avg_weight_kg))

    # Expected revenue from selling the flock
    revenue = max(0.0, total_weight * max(0.0, selling_price_per_kg))

    # Total feed cost over the growing period
    feed_total = max(
        0.0,
        feed_cost_per_chicken_per_day
        * expected_days_to_sell
        * number_of_chickens,
    )

    # Sum of all cost components
    total_cost = (
        feed_total
        + electricity_cost_per_day * expected_days_to_sell
        + labor_cost_per_day * expected_days_to_sell
        + medicine_cost_total
        + water_cost_total
        + farm_rent
        + (chick_price * number_of_chickens)
    )

    profit = revenue - total_cost

    roi = profit / total_cost if total_cost > 0 else 0.0
    break_even_price = total_cost / total_weight if total_weight > 0 else 0.0

    # Breakdown for charts (all values in EGP, handled as numbers here)
    cost_breakdown = {
        "chicks": chick_price * number_of_chickens,
        "feed": feed_total,
        "electricity": electricity_cost_per_day * expected_days_to_sell,
        "labor": labor_cost_per_day * expected_days_to_sell,
        "medicine": medicine_cost_total,
        "water": water_cost_total,
        "farm_rent": farm_rent,
    }

    return {
        "live_chickens": live_chickens,
        "total_weight": total_weight,
        "revenue": revenue,
        "feed_total": feed_total,
        "total_cost": total_cost,
        "profit": profit,
        "roi": roi,
        "break_even_price": break_even_price,
        "cost_breakdown": cost_breakdown,
    }


def analyze_existing_farm(
    initial_chickens: float,
    current_day_number: float,
    daily_feed_cost_total: float,
    electricity_cost_daily: float,
    labor_cost_daily: float,
    medicine_cost_to_date: float,
    deaths_to_date: float,
    avg_weight_now: float,
    current_market_price_per_kg: float,
) -> Dict[str, Any]:
    """
    Compute financial & performance metrics for an existing flock.

    Spec formulas (with clarified multiplication for accumulated_cost):
        live_chickens = initial_chickens - deaths_to_date
        accumulated_cost =
            (daily_feed_cost_total + electricity_cost_daily + labor_cost_daily)
            * current_day_number
            + medicine_cost_to_date
        current_value =
            live_chickens * avg_weight_now * current_market_price_per_kg
        profit_today = current_value - accumulated_cost
        mortality_rate_actual =
            deaths_to_date / initial_chickens if initial_chickens>0 else 0
    """

    live_chickens = max(0.0, initial_chickens - deaths_to_date)

    # Total operating costs (feed + electricity + labor) until today
    daily_operating_cost = (
        daily_feed_cost_total + electricity_cost_daily + labor_cost_daily
    )
    operating_cost_to_date = daily_operating_cost * max(0.0, current_day_number)

    # Accumulated cost = operating cost + medicine cost so far
    accumulated_cost = operating_cost_to_date + medicine_cost_to_date

    # Current market value of the flock
    current_value = max(
        0.0,
        live_chickens * max(0.0, avg_weight_now) * max(0.0, current_market_price_per_kg),
    )

    profit_today = current_value - accumulated_cost

    mortality_rate_actual = (
        deaths_to_date / initial_chickens if initial_chickens > 0 else 0.0
    )

    cost_breakdown = {
        "feed": operating_cost_to_date
        * (daily_feed_cost_total / daily_operating_cost)
        if daily_operating_cost > 0
        else daily_feed_cost_total * current_day_number,
        "electricity": operating_cost_to_date
        * (electricity_cost_daily / daily_operating_cost)
        if daily_operating_cost > 0
        else electricity_cost_daily * current_day_number,
        "labor": operating_cost_to_date
        * (labor_cost_daily / daily_operating_cost)
        if daily_operating_cost > 0
        else labor_cost_daily * current_day_number,
        "medicine": medicine_cost_to_date,
    }

    return {
        "live_chickens": live_chickens,
        "accumulated_cost": accumulated_cost,
        "current_value": current_value,
        "profit_today": profit_today,
        "mortality_rate_actual": mortality_rate_actual,
        "operating_cost_to_date": operating_cost_to_date,
        "cost_breakdown": cost_breakdown,
    }


def build_profit_sensitivity_series(
    base_params: Dict[str, float],
    price_step_egp: float = 1.0,
    span_egp: float = 10.0,
) -> Tuple[List[float], List[float]]:
    """
    Build a profit sensitivity curve around the current selling price.

    X-axis: selling price per kg (EGP)
    Y-axis: profit (EGP)

    We vary the selling price from (price - span) to (price + span)
    using the same base parameters as the main startup calculation.
    """
    center_price = float(base_params.get("selling_price_per_kg", 0.0))
    if center_price < 0:
        center_price = 0.0

    if price_step_egp <= 0:
        price_step_egp = 1.0

    prices: List[float] = []
    profits: List[float] = []

    min_price = max(0.0, center_price - span_egp)
    max_price = max(min_price, center_price + span_egp)

    # Only pass arguments that calculate_startup_plan expects
    allowed_keys = {
        "number_of_chickens",
        "chick_price",
        "feed_cost_per_chicken_per_day",
        "electricity_cost_per_day",
        "labor_cost_per_day",
        "medicine_cost_total",
        "water_cost_total",
        "farm_rent",
        "expected_days_to_sell",
        "expected_avg_weight_kg",
        "mortality_rate_percent",
        "selling_price_per_kg",
    }

    current = min_price
    while current <= max_price + 1e-6:
        params = {k: base_params[k] for k in allowed_keys if k in base_params}
        params["selling_price_per_kg"] = current
        res = calculate_startup_plan(**params)
        prices.append(current)
        profits.append(res["profit"])
        current += price_step_egp

    return prices, profits


def build_mortality_impact_series(
    base_params: Dict[str, float],
    max_mortality_percent: float = 20.0,
    step_percent: float = 2.0,
) -> Tuple[List[float], List[float]]:
    """
    Build a simple revenue curve under different mortality assumptions.

    X-axis: mortality rate (%)
    Y-axis: revenue (EGP)
    """
    max_m = max(0.0, max_mortality_percent)
    if step_percent <= 0:
        step_percent = 2.0

    mortality_rates: List[float] = []
    revenues: List[float] = []

    # Only pass arguments that calculate_startup_plan expects
    allowed_keys = {
        "number_of_chickens",
        "chick_price",
        "feed_cost_per_chicken_per_day",
        "electricity_cost_per_day",
        "labor_cost_per_day",
        "medicine_cost_total",
        "water_cost_total",
        "farm_rent",
        "expected_days_to_sell",
        "expected_avg_weight_kg",
        "mortality_rate_percent",
        "selling_price_per_kg",
    }

    m = 0.0
    while m <= max_m + 1e-6:
        params = {k: base_params[k] for k in allowed_keys if k in base_params}
        params["mortality_rate_percent"] = m
        res = calculate_startup_plan(**params)
        mortality_rates.append(m)
        revenues.append(res["revenue"])
        m += step_percent

    return mortality_rates, revenues


def simulate_best_selling_time(
    live_chickens: float,
    avg_weight_now: float,
    current_market_price_per_kg: float,
    accumulated_cost: float,
    daily_operating_cost: float,
    days_ahead: int = 10,
    daily_weight_gain_kg: float = 0.05,
) -> Dict[str, Any]:
    """
    Simulate projected profit for the coming days and recommend
    a "best selling time" window.

    Assumptions (simple but realistic enough for guidance):
        - Each bird gains ~daily_weight_gain_kg per day on average.
        - Market price fluctuates slightly using a smooth sinusoidal
          pattern around the current price (± ~1%).
        - Daily operating cost (feed + electricity + labor) stays
          constant.
        - Mortality is assumed stable over this short horizon.
    """
    days_ahead = max(1, int(days_ahead))
    live_chickens = max(0.0, live_chickens)
    avg_weight_now = max(0.0, avg_weight_now)
    current_market_price_per_kg = max(0.0, current_market_price_per_kg)
    accumulated_cost = max(0.0, accumulated_cost)
    daily_operating_cost = max(0.0, daily_operating_cost)
    daily_weight_gain_kg = max(0.0, daily_weight_gain_kg)

    days: List[int] = []
    projected_profits: List[float] = []

    for d in range(days_ahead + 1):  # include "today" as day 0
        # Simple deterministic weight projection
        est_weight = avg_weight_now + daily_weight_gain_kg * d

        # Gentle sinusoidal price fluctuation ±1%
        price_factor = 1.0 + 0.01 * math.sin(d or 1)
        est_price = current_market_price_per_kg * price_factor

        revenue = live_chickens * est_weight * est_price

        # Costs: existing accumulated cost + extra days of operating cost
        projected_cost = accumulated_cost + daily_operating_cost * d
        profit = revenue - projected_cost

        days.append(d)
        projected_profits.append(profit)

    # Find best day (max projected profit)
    if projected_profits:
        best_index = max(range(len(projected_profits)), key=lambda i: projected_profits[i])
        best_day_offset = days[best_index]
        best_profit = projected_profits[best_index]
    else:
        best_index = 0
        best_day_offset = 0
        best_profit = 0.0

    return {
        "days": days,
        "projected_profits": projected_profits,
        "best_day_index": best_index,
        "best_day_offset": best_day_offset,
        "best_profit": best_profit,
    }


def simulate_decision_curves(
    *,
    live_chickens: float,
    avg_weight_now_kg: float,
    accumulated_cost_egp: float,
    daily_operating_cost_egp: float,
    medicine_cost_to_date_egp: float,
    current_day_number: float,
    price_per_kg_by_offset: Dict[int, float],
    curve_day_offsets: List[int],
    scenario_day_offsets: List[int],
    daily_weight_gain_kg: float = 0.05,
    weight_cap_kg: float = 2.8,
) -> Dict[str, Any]:
    """
    Simulate decision-focused curves for an existing flock.

    Inputs:
        price_per_kg_by_offset: mapping day_offset -> forecasted/assumed price (EGP/kg)
        curve_day_offsets: offsets to plot (e.g. 30..45)
        scenario_day_offsets: offsets for comparison table (e.g. [0,14,30])

    Output:
        - profit_curve_* arrays for curve_day_offsets
        - scenario_* arrays for scenario_day_offsets
        - best_profit_day_offset within curve_day_offsets
        - break_even_day_offset within curve_day_offsets (closest price vs cost/kg)
    """
    curve_day_offsets = sorted(set(int(d) for d in curve_day_offsets))
    scenario_day_offsets = sorted(set(int(d) for d in scenario_day_offsets))
    all_offsets = sorted(set(curve_day_offsets + scenario_day_offsets))

    if live_chickens < 0:
        live_chickens = 0.0
    avg_weight_now_kg = max(0.0, float(avg_weight_now_kg))
    accumulated_cost_egp = max(0.0, float(accumulated_cost_egp))
    daily_operating_cost_egp = max(0.0, float(daily_operating_cost_egp))

    max_offset = max(all_offsets) if all_offsets else 0
    max_offset = max(0, int(max_offset))

    # Approximate remaining medicine cost by spreading the already-spent medicine
    # across days (helps keep cost curve realistic without needing a full program).
    if current_day_number > 0:
        medicine_per_day = max(0.0, float(medicine_cost_to_date_egp)) / float(
            current_day_number
        )
    else:
        medicine_per_day = 0.0

    # Simulate weight growth with decreasing daily increments (plateau-like).
    avg_weight_by_offset: Dict[int, float] = {0: avg_weight_now_kg}
    prev = avg_weight_now_kg
    for d in range(1, max_offset + 1):
        progress = d / max_offset if max_offset > 0 else 1.0
        # Start at ~daily_weight_gain_kg and taper down to ~30% by the end.
        gain = daily_weight_gain_kg * (1.0 - 0.7 * progress)
        gain = max(0.005, gain)
        prev = min(weight_cap_kg, prev + gain)
        avg_weight_by_offset[d] = prev

    def _safe_price(offset: int) -> float:
        v = price_per_kg_by_offset.get(int(offset))
        if v is None or not isinstance(v, (int, float)):
            return 0.0
        return max(0.0, float(v))

    def _compute_for_offsets(offsets: List[int]) -> Dict[str, List[float]]:
        profits: List[float] = []
        prices: List[float] = []
        avg_weights: List[float] = []
        total_weights: List[float] = []
        cumulative_costs: List[float] = []
        cost_per_kg_list: List[float] = []

        for off in offsets:
            off_i = int(off)
            avg_w = avg_weight_by_offset.get(off_i, prev)
            total_weight = live_chickens * avg_w
            price = _safe_price(off_i)
            cumulative_cost = accumulated_cost_egp + (daily_operating_cost_egp + medicine_per_day) * off_i
            cost_per_kg = (cumulative_cost / total_weight) if total_weight > 0 else 0.0
            profit = (total_weight * price) - cumulative_cost

            profits.append(profit)
            prices.append(price)
            avg_weights.append(avg_w)
            total_weights.append(total_weight)
            cumulative_costs.append(cumulative_cost)
            cost_per_kg_list.append(cost_per_kg)

        return {
            "profits": profits,
            "prices": prices,
            "avg_weights": avg_weights,
            "total_weights": total_weights,
            "cumulative_costs": cumulative_costs,
            "cost_per_kg": cost_per_kg_list,
        }

    curve = _compute_for_offsets(curve_day_offsets)
    scenarios = _compute_for_offsets(scenario_day_offsets)

    # Best profit in the curve range.
    if curve_day_offsets:
        best_idx = max(range(len(curve["profits"])), key=lambda i: curve["profits"][i])
        best_profit_day_offset = curve_day_offsets[best_idx]
        max_profit = curve["profits"][best_idx]
    else:
        best_profit_day_offset = None
        max_profit = None

    # Break-even where |price - cost_per_kg| is minimal.
    break_even_day_offset = None
    if curve_day_offsets:
        diffs = [abs(curve["prices"][i] - curve["cost_per_kg"][i]) for i in range(len(curve_day_offsets))]
        be_idx = min(range(len(diffs)), key=lambda i: diffs[i])
        break_even_day_offset = curve_day_offsets[be_idx]

    return {
        "curve_day_offsets": curve_day_offsets,
        "curve_profits": curve["profits"],
        "curve_prices": curve["prices"],
        "curve_avg_weights": curve["avg_weights"],
        "curve_total_weights": curve["total_weights"],
        "curve_cumulative_costs": curve["cumulative_costs"],
        "curve_cost_per_kg": curve["cost_per_kg"],
        "best_profit_day_offset": best_profit_day_offset,
        "max_profit": max_profit,
        "break_even_day_offset": break_even_day_offset,
        "scenario_day_offsets": scenario_day_offsets,
        "scenario_profits": scenarios["profits"],
        "scenario_prices": scenarios["prices"],
        "scenario_avg_weights": scenarios["avg_weights"],
        "scenario_total_weights": scenarios["total_weights"],
        "scenario_cumulative_costs": scenarios["cumulative_costs"],
        "scenario_cost_per_kg": scenarios["cost_per_kg"],
    }


def build_startup_plan_from_budget(
    total_budget: float,
    chick_price: float,
    selling_price_per_kg: float,
    feed_cost_per_chicken_per_day: float | None = None,
    water_cost_total: float = 0.0,
) -> Dict[str, float]:
    """
    Given only total budget, chick price and selling price, build a
    reasonable startup plan by choosing the number of chicks such that
    the total cycle cost stays within the available budget.

    Assumptions (tuned for typical Egyptian broiler farms):
        - Cycle length ~35 days
        - Average final weight ~2.0 kg
        - Mortality ~5%
        - Feed cost per chick per day ~1.8 EGP
        - Electricity per day ~120 EGP (per house)
        - Labor per day ~250 EGP (per house)
        - Medicine, equipment, rent scale approximately with flock size
          using a 1000-bird reference flock.

    The function performs a simple search on number_of_chickens and
    returns a parameter dict suitable to pass into calculate_startup_plan.
    """

    total_budget = max(0.0, total_budget)
    chick_price = max(0.0, chick_price)
    selling_price_per_kg = max(0.0, selling_price_per_kg)

    # If budget or chick price is zero, fall back to a tiny plan
    if total_budget <= 0 or chick_price <= 0:
        return {
            "number_of_chickens": 0.0,
            "chick_price": chick_price or 0.0,
            "feed_cost_per_chicken_per_day": 1.8,
            "electricity_cost_per_day": 120.0,
            "labor_cost_per_day": 250.0,
            "medicine_cost_total": 0.0,
            "water_cost_total": max(0.0, water_cost_total),
            "farm_rent": 0.0,
            "expected_days_to_sell": 35.0,
            "expected_avg_weight_kg": 2.0,
            "mortality_rate_percent": 5.0,
            "selling_price_per_kg": selling_price_per_kg,
        }

    # Reference values for a 1000-bird flock
    REF_BIRDS = 1000.0
    FEED_COST_PER_CHICKEN_PER_DAY = (
        feed_cost_per_chicken_per_day if feed_cost_per_chicken_per_day is not None else 1.8
    )
    ELECTRICITY_PER_DAY = 120.0
    LABOR_PER_DAY = 250.0
    # Medicine: typical 3–6 EGP/chicken per 35-day cycle; average ≈ 4.5 EGP (vaccines, vitamins, antibiotics, disinfectants).
    MEDICINE_PER_CHICKEN_EGP = 4.5
    WATER_COST_TOTAL = max(0.0, water_cost_total)
    DAYS = 35.0
    AVG_WEIGHT = 2.0
    MORTALITY_PERCENT = 5.0

    def estimate_cost_for_n(n: float) -> tuple[float, Dict[str, float]]:
        scale = n / REF_BIRDS if REF_BIRDS > 0 else 0.0
        params: Dict[str, float] = {
            "number_of_chickens": n,
            "chick_price": chick_price,
            "feed_cost_per_chicken_per_day": FEED_COST_PER_CHICKEN_PER_DAY,
            "electricity_cost_per_day": ELECTRICITY_PER_DAY,
            "labor_cost_per_day": LABOR_PER_DAY,
            # Medicine: 4.5 EGP per chicken (35-day cycle; typical range 3–6 EGP).
            "medicine_cost_total": n * MEDICINE_PER_CHICKEN_EGP,
            "water_cost_total": WATER_COST_TOTAL,
            # Rent = number of chicks × chick price (per cycle).
            # Example: 900 chicks * 15 EGP => 13,500 EGP farm rent.
            "farm_rent": n * chick_price,
            "expected_days_to_sell": DAYS,
            "expected_avg_weight_kg": AVG_WEIGHT,
            "mortality_rate_percent": MORTALITY_PERCENT,
            "selling_price_per_kg": selling_price_per_kg,
        }
        res = calculate_startup_plan(**params)
        return res["total_cost"], params

    # Initial bracket for search
    low = 0.0
    high = 1000.0
    cost_high, _ = estimate_cost_for_n(high)

    # Scale up until we exceed budget or hit a hard cap
    while cost_high < total_budget and high < 100_000:
        high *= 2.0
        cost_high, _ = estimate_cost_for_n(high)

    best_params: Dict[str, float] = {}

    # Binary search for max n where total_cost <= budget
    for _ in range(25):
        mid = (low + high) / 2.0
        cost_mid, params_mid = estimate_cost_for_n(mid)
        if cost_mid <= total_budget:
            best_params = params_mid
            low = mid
        else:
            high = mid

    if not best_params:
        # Fallback if something went wrong
        _, best_params = estimate_cost_for_n(REF_BIRDS / 10.0)

    # Round number of chickens to an integer
    best_params["number_of_chickens"] = float(int(best_params["number_of_chickens"]))
    return best_params


