"""
Scrape historical poultry prices (2024 -> now) from Al-Masry Al-Youm and
Youm7 into a pandas DataFrame, and save as CSV.

This is a standalone utility script; it does NOT run as part of Flask.
Run it manually from the project root:

    python -m financial.scrape_poultry_history

The output file will be:
    poultry_prices_2024_now.csv
in the project root.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import List, Dict

import pandas as pd  # type: ignore
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore


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


def parse_arabic_date(text: str) -> datetime | None:
    """Extract a Gregorian date from mixed Arabic text."""
    months = {
        "يناير": 1,
        "فبراير": 2,
        "مارس": 3,
        "أبريل": 4,
        "ابريل": 4,
        "مايو": 5,
        "يونيو": 6,
        "يوليو": 7,
        "أغسطس": 8,
        "اغسطس": 8,
        "سبتمبر": 9,
        "أكتوبر": 10,
        "اكتوبر": 10,
        "نوفمبر": 11,
        "ديسمبر": 12,
    }
    m = re.search(r"(\d{1,2})\s+([اأإآa-zA-Zء-ي]+)\s+(\d{4})", text)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2)
    year = int(m.group(3))
    month = months.get(month_name, 1)
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


# ---------- 1) Al-Masry Al-Youm ----------


def search_almasryalyoum(query: str, max_pages: int = 40) -> List[str]:
    """Collect article URLs from Al-Masry Al-Youm search results."""
    urls: List[str] = []
    base = "https://www.almasryalyoum.com/search"
    for page in range(1, max_pages + 1):
        params = {"searchword": query, "page": page}
        resp = session.get(base, params=params, timeout=10)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select("a")
        new_on_page = 0
        for a in links:
            href = a.get("href", "")
            if "/news/details/" in href:
                full = (
                    href
                    if href.startswith("http")
                    else "https://www.almasryalyoum.com" + href
                )
                if full not in urls:
                    urls.append(full)
                    new_on_page += 1
        if new_on_page == 0:
            break
        time.sleep(0.6)
    return urls


def parse_almasry_article(url: str) -> List[Dict]:
    """Parse one Al-Masry Al-Youm article into 0..N structured rows."""
    try:
        resp = session.get(url, timeout=12)
    except Exception:
        return []
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    date = parse_arabic_date(page_text)

    title_el = soup.find("h1") or soup.title
    title = title_el.get_text(strip=True) if title_el else ""

    # Rough governorate / location (optional)
    loc_match = re.search(r"في\s+([اأإآa-zA-Zء-ي]+)", title)
    location = loc_match.group(1) if loc_match else ""

    rows: List[Dict] = []
    text = page_text

    # We focus only on white broiler prices for this dataset.
    labels = [
        "الفراخ البيضاء",
        "الدواجن البيضاء",
        "الدجاج الأبيض",
    ]

    for label in labels:
        if label not in text:
            continue
        idx = text.find(label)
        segment = text[idx : idx + 200]
        nums = re.findall(r"(\d+(?:\.\d+)?)\s*جنيه", segment)
        if not nums:
            continue
        mn = float(nums[0])
        mx = float(nums[-1]) if len(nums) > 1 else mn
        rows.append(
            {
                "source": "almasryalyoum",
                "url": url,
                "date": date,
                "title": title,
                "location": location,
                "product": label,
                "price_min": mn,
                "price_max": mx,
            }
        )

    return rows


# ---------- 2) Youm7 ----------


def search_youm7(query: str, max_pages: int = 40) -> List[str]:
    """Collect article URLs from Youm7 search results."""
    urls: List[str] = []
    base = "https://www.youm7.com/Search/index"
    for page in range(1, max_pages + 1):
        params = {"searchtext": query, "page": page}
        resp = session.get(base, params=params, timeout=10)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a"):
            href = a.get("href", "")
            text = a.get_text(" ", strip=True)
            if "/story/" in href and ("أسعار الدواجن" in text or "أسعار الفراخ" in text):
                full = href if href.startswith("http") else "https://www.youm7.com" + href
                if full not in urls:
                    urls.append(full)
        time.sleep(0.6)
    return urls


def parse_youm7_article(url: str) -> List[Dict]:
    """Parse one Youm7 article into 0..N structured rows."""
    try:
        resp = session.get(url, timeout=12)
    except Exception:
        return []
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    date = parse_arabic_date(page_text)

    title_el = soup.find("h1") or soup.title
    title = title_el.get_text(strip=True) if title_el else ""

    rows: List[Dict] = []
    text = page_text

    labels = [
        "الفراخ البيضاء",
        "الدواجن البيضاء",
        "الدجاج الأبيض",
    ]

    for label in labels:
        if label not in text:
            continue
        idx = text.find(label)
        segment = text[idx : idx + 200]
        nums = re.findall(r"(\d+(?:\.\d+)?)\s*جنيه", segment)
        if not nums:
            continue
        mn = float(nums[0])
        mx = float(nums[-1]) if len(nums) > 1 else mn
        rows.append(
            {
                "source": "youm7",
                "url": url,
                "date": date,
                "title": title,
                "location": "",  # could extract المحافظه from title text if needed
                "product": label,
                "price_min": mn,
                "price_max": mx,
            }
        )

    return rows


# ---------- 3) Orchestration ----------


def google_search_almasry(year: int, max_pages: int = 5) -> List[str]:
    """
    Use Google-style search to find almasryalyoum poultry price articles for a year.

    Query pattern:
        site:almasryalyoum.com \"أسعار الفراخ اليوم\" <year>
    """
    urls: List[str] = []
    base = "https://www.google.com/search"
    query = f'site:almasryalyoum.com "أسعار الفراخ اليوم" {year}'

    for page in range(0, max_pages):
        params = {
            "q": query,
            "start": page * 10,
            "num": 10,
            "hl": "ar",
        }
        try:
            resp = session.get(base, params=params, timeout=10)
        except Exception:
            break
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        new_on_page = 0
        for a in soup.select("a"):
            href = a.get("href", "")
            m = re.search(r"https://www\.almasryalyoum\.com/news/details/\d+", href)
            if not m:
                continue
            full = m.group(0)
            if full not in urls:
                urls.append(full)
                new_on_page += 1
        if new_on_page == 0:
            break
        time.sleep(0.6)
    return urls


def build_poultry_price_df() -> pd.DataFrame:
    all_rows: List[Dict] = []

    # Seed URLs provided by the user (known-good examples).
    seed_almasry = [
        "https://www.almasryalyoum.com/news/details/4218462",
        "https://www.almasryalyoum.com/news/details/4213561",
    ]
    seed_youm7 = [
        "https://www.youm7.com/story/2024/6/11/%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A7%D9%84%D9%8A%D9%88%D9%85-%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D8%A7%D9%84%D8%A8%D9%8A%D8%B6%D8%A7%D8%A1-%D9%81%D9%8A-%D8%A7%D9%84%D8%A3%D8%B3%D9%88%D8%A7%D9%82/6605337",
        "https://www.youm7.com/story/2026/3/10/%D9%81%D9%8A-%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D8%A7%D9%84%D8%A8%D9%8A%D8%B6%D8%A7%D8%A1-%D8%AA%D9%83%D8%B3%D8%B1-%D8%AD%D8%A7%D8%AC%D8%B2-%D8%A7%D9%84%D9%80100-%D8%AC%D9%86%D9%8A%D9%87/7335318",
    ]

    print("Scraping seed Al-Masry Al-Youm articles ...", flush=True)
    for i, u in enumerate(seed_almasry, 1):
        print(f"[AlMasry seed {i}/{len(seed_almasry)}] {u}", flush=True)
        all_rows.extend(parse_almasry_article(u))
        time.sleep(0.3)

    print("Scraping seed Youm7 articles ...", flush=True)
    for i, u in enumerate(seed_youm7, 1):
        print(f"[Youm7 seed {i}/{len(seed_youm7)}] {u}", flush=True)
        all_rows.extend(parse_youm7_article(u))
        time.sleep(0.3)

    # Optional: try to discover more articles via site search.
    # Discover more Al-Masry Al-Youm articles via Google for years of interest.
    print("Discovering Al-Masry Al-Youm articles via Google ...", flush=True)
    almasry_urls: List[str] = []
    for yr in (2024, 2025, 2026):
        year_urls = google_search_almasry(yr, max_pages=5)
        print(f"  Year {yr}: found {len(year_urls)} URLs", flush=True)
        for u in year_urls:
            if u not in almasry_urls and u not in seed_almasry:
                almasry_urls.append(u)

    for i, u in enumerate(almasry_urls, 1):
        print(f"[AlMasry Google {i}/{len(almasry_urls)}] {u}", flush=True)
        all_rows.extend(parse_almasry_article(u))
        time.sleep(0.3)

    # Optionally, still search Youm7 broadly (may return few or none).
    print("Searching Youm7 (broad search) ...", flush=True)
    youm7_urls = search_youm7("أسعار الدواجن اليوم", max_pages=20)
    print(f"  Found {len(youm7_urls)} candidate Youm7 articles.", flush=True)
    for i, u in enumerate(youm7_urls, 1):
        if u in seed_youm7:
            continue
        print(f"[Youm7 search {i}/{len(youm7_urls)}] {u}", flush=True)
        all_rows.extend(parse_youm7_article(u))
        time.sleep(0.3)

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    # Normalize and filter by date >= 2024-01-01
    if "date" in df.columns:
        df = df[df["date"].notna()].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"] >= pd.Timestamp("2024-01-01")]
        df = df.sort_values(["date", "source", "product"])

    return df


def main() -> None:
    print("Building poultry prices DataFrame (from 2024)...", flush=True)
    df = build_poultry_price_df()
    if df.empty:
        print("No data scraped. Check connectivity or selectors.")
        return
    out_path = "poultry_prices_2024_now.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

