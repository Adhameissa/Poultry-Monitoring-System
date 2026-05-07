"""
Scrape historical white broiler prices from المرشد للدواجن via the Wayback Machine.

Target URL (daily, overwritten):
    https://www.elmorshdledwagn.com/prices/l2

Wayback stores snapshots of this page over time. For each snapshot between
2024 and 2026 we:
    - Fetch archived HTML.
    - Parse the row for 'اللحم الابيض'.
    - Extract the 'سوق' and 'نتفيذ' values (market and execution prices).

Run manually from project root:

    python -m financial.scrape_wayback_elmorshd

Output CSV:
    elmorshd_broiler_wayback_2024_2026.csv
with columns:
    date, price_market, price_execution, wayback_timestamp
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
from typing import List, Dict

import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore


BASE_URL = "https://www.elmorshdledwagn.com/prices/l2"
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
    Query Wayback CDX API for snapshots of the المرشد للدواجن prices page.

    Collapse to one snapshot per day to avoid duplicates.
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
    snapshots.sort(key=lambda e: e["date"])
    return snapshots


def parse_elmorshd_html(html: str) -> Dict[str, float]:
    """
    Parse archived المرشد للدواجن prices page HTML for white broiler.

    We look for the first table where there is a row whose first cell
    contains 'اللحم الابيض', and then interpret the columns as:
        | الصنف | سوق | نتفيذ | المؤشر |
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return {}

    for table in tables:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            label = tds[0].get_text(strip=True)
            if "اللحم الابيض" not in label and "اللحم الأبيض" not in label:
                continue
            market_text = tds[1].get_text(strip=True)
            exec_text = tds[2].get_text(strip=True)
            def _to_float(s: str) -> float | None:
                m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", ""))
                if not m:
                    return None
                try:
                    return float(m.group(1))
                except Exception:
                    return None

            market = _to_float(market_text)
            execution = _to_float(exec_text)
            if market is None and execution is None:
                continue
            result: Dict[str, float] = {}
            if market is not None:
                result["price_market"] = market
            if execution is not None:
                result["price_execution"] = execution
            return result

    return {}


def scrape_wayback_elmorshd() -> List[Dict]:
    snapshots = fetch_cdx_snapshots(2024, 2026)
    print(
        f"Found {len(snapshots)} Wayback snapshots for elmorshd prices page.",
        flush=True,
    )
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
        data = parse_elmorshd_html(resp.text)
        if not data:
            continue
        row = {
            "date": date.isoformat(),
            "price_market": data.get("price_market"),
            "price_execution": data.get("price_execution"),
            "wayback_timestamp": ts,
        }
        rows.append(row)
        time.sleep(0.7)

    return rows


def main() -> None:
    import pandas as pd  # local import

    print(
        "Scraping elmorshd historical white broiler prices via Wayback Machine ...",
        flush=True,
    )
    rows = scrape_wayback_elmorshd()
    if not rows:
        print("No rows scraped. Check CDX API or connectivity.")
        return
    df = pd.DataFrame(rows)
    df = df.sort_values("date")
    out_path = "elmorshd_broiler_wayback_2024_2026.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

