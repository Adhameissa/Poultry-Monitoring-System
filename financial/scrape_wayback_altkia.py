"""
Scrape historical white broiler prices from altkia.com via the Wayback Machine.

Idea:
    - altkia has a single daily page:
        https://www.altkia.com/poultry-prices-today/
    - The Wayback Machine stores snapshots of this URL over time.
    - We query the CDX API for snapshots between 2024 and now, then
      for each snapshot fetch the archived HTML and parse white broiler
      prices using logic similar to financial.market_price._fetch_prices_from_altkia.

Run this script manually from the project root:

    python -m financial.scrape_wayback_altkia

Output:
    altkia_poultry_wayback_2024_2026.csv
with columns:
    date, meat_white_min, meat_white_max, meat_white_price
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
from typing import List, Dict

import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore


BASE_URL = "https://www.altkia.com/poultry-prices-today/"
CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_PREFIX = "https://web.archive.org/web"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)


def fetch_cdx_snapshots(from_year: int = 2024, to_year: int = 2026) -> List[Dict]:
    """
    Query Wayback CDX API for snapshots of the poultry-prices-today page.

    We collapse to one snapshot per day (timestamp:8) to avoid duplicates.
    """
    params = {
        "url": BASE_URL,
        "from": str(from_year),
        "to": str(to_year),
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "timestamp:8",
    }
    try:
        resp = session.get(CDX_API, params=params, timeout=15)
    except Exception:
        return []
    if resp.status_code != 200:
        return []

    try:
        data = json.loads(resp.text)
    except Exception:
        return []

    if not data or len(data) < 2:
        return []

    headers = data[0]
    rows = data[1:]
    snapshots: List[Dict] = []
    for row in rows:
        entry = dict(zip(headers, row))
        # Expect 'timestamp' like '20250307xxxxxx'
        ts = entry.get("timestamp")
        if not ts or len(ts) < 8:
            continue
        date_str = ts[:8]
        try:
            date = _dt.datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            continue
        entry["date"] = date
        snapshots.append(entry)
    # Sort by date
    snapshots.sort(key=lambda e: e["date"])
    return snapshots


def parse_altkia_html(html: str) -> Dict[str, float]:
    """
    Parse archived altkia poultry page HTML for white broiler min/max/price.

    We reuse the same patterns used in financial.market_price._fetch_prices_from_altkia.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    meat_white_price = None
    meat_min = None
    meat_max = None

    for tr in rows:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not cells:
            continue
        row_text = " ".join(cells)

        if "لحم الفراخ البيضاء" in row_text:
            nums = re.findall(r"(\d+(?:\.\d+)?)\s*جنيه", row_text)
            if nums:
                try:
                    meat_values = [float(v) for v in nums]
                    meat_min = min(meat_values)
                    meat_max = max(meat_values)
                    meat_white_price = meat_max
                except Exception:
                    pass

    result: Dict[str, float] = {}
    if meat_white_price is not None:
        result["meat_white_price"] = float(meat_white_price)
    if meat_min is not None:
        result["meat_white_min"] = float(meat_min)
    if meat_max is not None:
        result["meat_white_max"] = float(meat_max)
    return result


def scrape_wayback_altkia() -> List[Dict]:
    snapshots = fetch_cdx_snapshots(2024, 2026)
    print(f"Found {len(snapshots)} Wayback snapshots for altkia poultry page.", flush=True)
    rows: List[Dict] = []

    for i, snap in enumerate(snapshots, 1):
        ts = snap.get("timestamp")
        date = snap.get("date")
        if not ts or not date:
            continue

        url = f"{WAYBACK_PREFIX}/{ts}/{BASE_URL}"
        print(f"[{i}/{len(snapshots)}] {date} -> {url}", flush=True)
        try:
            resp = session.get(url, timeout=15)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        data = parse_altkia_html(resp.text)
        if not data:
            continue
        row = {
            "date": date.isoformat(),
            "meat_white_price": data.get("meat_white_price"),
            "meat_white_min": data.get("meat_white_min"),
            "meat_white_max": data.get("meat_white_max"),
            "wayback_timestamp": ts,
        }
        rows.append(row)
        time.sleep(0.7)

    return rows


def main() -> None:
    import pandas as pd  # local import to avoid hard dependency for other modules

    print("Scraping altkia historical poultry prices via Wayback Machine ...", flush=True)
    rows = scrape_wayback_altkia()
    if not rows:
        print("No rows scraped. Check CDX API or connectivity.")
        return
    df = pd.DataFrame(rows)
    df = df.sort_values("date")
    out_path = "altkia_poultry_wayback_2024_2026.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

