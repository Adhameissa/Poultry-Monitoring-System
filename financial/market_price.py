"""
Market price helper for Egyptian poultry prices (EGP / kg).

This module is intentionally lightweight and independent from the rest
of the app. It provides a single public function:

    get_today_price() -> float

Logic:
    1. Try to load today's price from a small SQLite table
       market_prices(date TEXT PRIMARY KEY, price_per_kg REAL).
    2. If not present, make a best-effort HTTP request to a public
       poultry price source and try to parse a price.
    3. Store any successfully fetched price in the DB.
    4. If fetching fails, fall back to the latest stored DB price.
    5. If no DB price exists, fall back to a safe default (70 EGP).

The web scraping step is intentionally defensive and will silently
fall back on error so that the financial module keeps working even
without internet access or if the remote HTML changes.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from typing import Optional

try:
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None
    BeautifulSoup = None


_DB_PATH = os.path.join(os.path.dirname(__file__), "market_prices.db")

# Some sites block generic Python user agents with 403. Use a realistic
# browser-like User-Agent and basic headers so that requests coming from
# this module look like a normal human visitor.
_ALT_KIA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
}


def _get_connection() -> sqlite3.Connection:
    """Open SQLite connection and ensure table exists."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_prices (
            date TEXT PRIMARY KEY,
            price_per_kg REAL NOT NULL
        )
        """
    )
    return conn


def _get_price_for_date(date_str: str) -> Optional[float]:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "SELECT price_per_kg FROM market_prices WHERE date = ?", (date_str,)
        )
        row = cur.fetchone()
        return float(row[0]) if row else None
    finally:
        conn.close()


def _get_last_price_from_db() -> Optional[float]:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "SELECT price_per_kg FROM market_prices ORDER BY date DESC LIMIT 1"
        )
        row = cur.fetchone()
        return float(row[0]) if row else None
    finally:
        conn.close()


def _save_price(date_str: str, price_per_kg: float) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO market_prices (date, price_per_kg) VALUES (?, ?)",
            (date_str, float(price_per_kg)),
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_prices_from_altkia() -> Optional[dict]:
    """
    Scrape poultry meat and chick prices from altkia.com.

    We focus on:
        - لحم الفراخ البيضاء  -> meat_white_price (EGP/kg, we take the
          highest price in the row, in line with typical trader price).
        - كتكوت أبيض شركات   -> chick_white_min / chick_white_max /
          chick_white_avg (EGP per chick).
    """
    if requests is None or BeautifulSoup is None:
        return None

    url = "https://www.altkia.com/poultry-prices-today/"
    try:
        resp = requests.get(url, headers=_ALT_KIA_HEADERS, timeout=8)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")

        meat_white_price: Optional[float] = None
        meat_min: Optional[float] = None
        meat_max: Optional[float] = None
        chick_min: Optional[float] = None
        chick_max: Optional[float] = None

        for tr in rows:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            row_text = " ".join(cells)

            # White broiler meat row
            if "لحم الفراخ البيضاء" in row_text:
                nums = re.findall(r"(\d+(?:\.\d+)?)\s*جنيه", row_text)
                if nums:
                    try:
                        meat_values = [float(v) for v in nums]
                        meat_min = min(meat_values)
                        meat_max = max(meat_values)
                        # Keep existing behavior: trader price uses upper bound.
                        meat_white_price = meat_max
                    except Exception:
                        pass

            # White chick companies row
            if "كتكوت أبيض شركات" in row_text:
                nums = re.findall(r"(\d+(?:\.\d+)?)\s*جنيه", row_text)
                if len(nums) >= 2:
                    try:
                        chick_min = float(nums[0])
                        chick_max = float(nums[-1])
                    except Exception:
                        pass

        if meat_white_price is None and chick_min is None and chick_max is None:
            return None

        data: dict = {}
        if meat_white_price is not None:
            data["meat_white_price"] = meat_white_price
        if meat_min is not None:
            data["meat_white_min"] = meat_min
        if meat_max is not None:
            data["meat_white_max"] = meat_max
        if meat_min is not None and meat_max is not None:
            data["meat_white_avg"] = (meat_min + meat_max) / 2.0
        if chick_min is not None:
            data["chick_white_min"] = chick_min
        if chick_max is not None:
            data["chick_white_max"] = chick_max
        if chick_min is not None and chick_max is not None:
            data["chick_white_avg"] = (chick_min + chick_max) / 2.0

        return data or None
    except Exception:
        return None


def _try_fetch_price_from_web() -> Optional[float]:
    """
    Fetch today's white broiler price (EGP/kg) using altkia.com.
    """
    data = _fetch_prices_from_altkia()
    if not data:
        return None

    price = data.get("meat_white_price")
    if price is None:
        return None

    try:
        price_f = float(price)
    except Exception:
        return None

    # Basic sanity check for poultry price (50–200 EGP / kg)
    if 50.0 <= price_f <= 200.0:
        return price_f
    return None


def get_today_price() -> float:
    """
    Return today's best-known poultry price in EGP / kg.

    This function is safe to call on every request; DB operations are
    light and the web scraping step is only attempted when today's
    price isn't already cached.
    """
    today_str = _dt.date.today().isoformat()

    # 1) Try today's cached value
    cached = _get_price_for_date(today_str)
    if cached is not None:
        return cached

    # 2) Best-effort fetch from web
    fetched = _try_fetch_price_from_web()
    if fetched is not None:
        _save_price(today_str, fetched)
        return fetched

    # 3) Fallback to last known DB price
    last = _get_last_price_from_db()
    if last is not None:
        return last

    # 4) Final fallback to safe default.
    # For your use-case we use 91 EGP/kg as a realistic Egyptian
    # white broiler trader price when scraping/DB are unavailable.
    return 91.0


def get_today_chick_price(default: float = 15.0) -> float:
    """
    Best-effort retrieval of today's chick price based on altkia.com.

    We mainly use the row "كتكوت أبيض شركات" and take the average
    between the minimum and maximum prices. If anything fails, we
    fall back to a configurable default.
    """
    data = _fetch_prices_from_altkia()
    if not data:
        return default

    chick = data.get("chick_white_avg") or data.get("chick_white_min") or data.get(
        "chick_white_max"
    )
    try:
        chick_f = float(chick)
    except Exception:
        return default

    # Sanity bounds (5–50 EGP / chick)
    if 5.0 <= chick_f <= 50.0:
        return chick_f
    return default


def get_today_feed_prices() -> Optional[dict]:
    """
    Scrape today's feed prices (per kg) for starter/grower/finisher
    from altkia's 'poultry-feed-prices-today' page.

    Returns a dict like:
        {
            "starter_price_per_kg": ...,
            "grower_price_per_kg": ...,
            "finisher_price_per_kg": ...
        }
    or None if scraping fails.
    """
    if requests is None or BeautifulSoup is None:
        return None

    url = "https://www.altkia.com/poultry-feed-prices-today/"
    try:
        resp = requests.get(url, headers=_ALT_KIA_HEADERS, timeout=8)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")

        starter_ton = None
        grower_ton = None
        finisher_ton = None

        for tr in rows:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 2:
                continue
            name = cells[0]
            price_text = cells[1]

            # Expect numeric like "22000"
            m = re.search(r"(\d+(?:\.\d+)?)", price_text)
            if not m:
                continue
            price_ton = float(m.group(1))

            if "علف بادي" in name:
                starter_ton = price_ton
            elif "علف نامي" in name:
                grower_ton = price_ton
            elif "علف ناهي" in name:
                finisher_ton = price_ton

        if starter_ton is None and grower_ton is None and finisher_ton is None:
            return None

        result: dict = {}
        if starter_ton is not None:
            result["starter_price_per_ton"] = starter_ton
            result["starter_price_per_kg"] = starter_ton / 1000.0
        if grower_ton is not None:
            result["grower_price_per_ton"] = grower_ton
            result["grower_price_per_kg"] = grower_ton / 1000.0
        if finisher_ton is not None:
            result["finisher_price_per_ton"] = finisher_ton
            result["finisher_price_per_kg"] = finisher_ton / 1000.0

        return result or None
    except Exception:
        return None


def get_today_prices_snapshot() -> dict:
    """
    Return a unified best-effort snapshot for cards/UI.

    Keys:
        broiler_price, broiler_min, broiler_max,
        chick_price, chick_min, chick_max,
        feed (dict)
    """
    raw = _fetch_prices_from_altkia() or {}
    broiler_price = get_today_price()
    chick_price = get_today_chick_price(15.0)
    feed = get_today_feed_prices() or {}

    return {
        "broiler_price": raw.get("meat_white_price", broiler_price),
        "broiler_min": raw.get("meat_white_min"),
        "broiler_max": raw.get("meat_white_max"),
        "chick_price": raw.get("chick_white_avg", chick_price),
        "chick_min": raw.get("chick_white_min"),
        "chick_max": raw.get("chick_white_max"),
        "feed": feed,
    }
