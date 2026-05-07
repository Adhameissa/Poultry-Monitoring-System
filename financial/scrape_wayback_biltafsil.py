"""
Scrape historical white broiler prices from biltafsil.com via the Wayback Machine.

Target URL (current day, overwritten daily):
    https://www.biltafsil.com/poultry/chickens/

Wayback stores many snapshots of this page. For each snapshot between
2024 and 2026 we:
    - Fetch archived HTML.
    - Parse the table row for 'كيلو الفراخ البيضاء'.
    - Extract its price in EGP.

Run manually from project root:

    python -m financial.scrape_wayback_biltafsil

Output CSV:
    biltafsil_chickens_wayback_2024_2026.csv
with columns:
    date, price_white_broiler_egp, wayback_timestamp
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
from typing import List, Dict

import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore


BASE_URL = "https://www.biltafsil.com/poultry/chickens/"
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
    Query Wayback CDX API for snapshots of the biltafsil chickens page.

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


def parse_biltafsil_chickens_html(html: str) -> Dict[str, float]:
    """
    Parse archived biltafsil chickens page HTML for white broiler price.

    We look for table row whose first cell contains 'كيلو الفراخ البيضاء'
    and parse the numeric price from the second cell.
    """
    soup = BeautifulSoup(html, "html.parser")
    price = None

    table = soup.find("table")
    if not table:
        return {}

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        label = tds[0].get_text(strip=True)
        if "كيلو الفراخ البيضاء" in label:
            val_text = tds[1].get_text(strip=True)
            m = re.search(r"(\d+(?:\.\d+)?)", val_text)
            if m:
                try:
                    price = float(m.group(1))
                except Exception:
                    price = None
            break

    return {"white_broiler_price": price} if price is not None else {}


def scrape_wayback_biltafsil() -> List[Dict]:
    snapshots = fetch_cdx_snapshots(2024, 2026)
    print(
        f"Found {len(snapshots)} Wayback snapshots for biltafsil chickens page.",
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
        data = parse_biltafsil_chickens_html(resp.text)
        if not data:
            continue
        row = {
            "date": date.isoformat(),
            "price_white_broiler_egp": data.get("white_broiler_price"),
            "wayback_timestamp": ts,
        }
        rows.append(row)
        time.sleep(0.7)

    return rows


def main() -> None:
    import pandas as pd  # local import

    print(
        "Scraping biltafsil historical white broiler prices via Wayback Machine ...",
        flush=True,
    )
    rows = scrape_wayback_biltafsil()
    if not rows:
        print("No rows scraped. Check CDX API or connectivity.")
        return
    df = pd.DataFrame(rows)
    df = df.sort_values("date")
    out_path = "biltafsil_chickens_wayback_2024_2026.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

