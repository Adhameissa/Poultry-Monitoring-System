"""
Scrape white broiler prices from seed news articles (المصري اليوم، المال، الدستور)
into a single pandas DataFrame for model training.

This script does NOT try to auto-discover URLs. Instead it relies on
hand-picked article URLs known to contain daily poultry prices.

Run from project root:

    python -m financial.scrape_news_broiler_history

Output:
    news_broiler_prices_2024_2026.csv
with columns:
    date, source, url, title, price_white_broiler_egp
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
    """Extract Gregorian date from Arabic text block."""
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


ALMASRY_URLS = [
    "https://www.almasryalyoum.com/news/details/4218462",
    "https://www.almasryalyoum.com/news/details/4213561",
    "https://www.almasryalyoum.com/news/details/4216026",
    "https://www.almasryalyoum.com/news/details/3528515",
    "https://www.almasryalyoum.com/news/details/3509254",
    "https://www.almasryalyoum.com/news/details/3396772",
    "https://www.almasryalyoum.com/news/details/3395958",
    "https://www.almasryalyoum.com/news/details/3565412",
    "https://www.almasryalyoum.com/news/details/4159610",
    "https://www.almasryalyoum.com/news/details/4212816",
]

ALMAL_URLS = [
    "https://almalnews.com/2101532/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D9%81%D9%8A-%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A7%D9%84%D9%8A%D9%88%D9%85-%D8%A7%D9%84%D8%AB%D9%84%D8%A7%D8%AB%D8%A7%D8%A1/",
    "https://almalnews.com/2101662/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D9%81%D9%8A-%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A7%D9%84%D9%8A%D9%88%D9%85-%D8%A7%D9%84%D8%A3%D8%B1%D8%A8%D8%B9%D8%A7%D8%A1/",
    "https://almalnews.com/2099704/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D9%81%D9%8A-%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A7%D9%84%D9%8A%D9%88%D9%85-%D8%A7%D9%84%D8%A3%D8%B1%D8%A8%D8%B9%D8%A7%D8%A1/",
    "https://almalnews.com/2096862/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D9%81%D9%8A-%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A7%D9%84%D9%8A%D9%88%D9%85-%D8%A7%D9%84%D8%A5%D8%AB%D9%86%D9%8A%D9%86/",
    "https://almalnews.com/2095590/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AE-%D9%81%D9%8A-%D8%A8%D9%88%D8%B1%D8%B5%D8%A9-%D8%A7%D9%84%D8%AF%D9%88%D8%A7%D8%AC%D9%86-%D8%A7%D9%84%D9%8A%D9%88%D9%85-%D8%A7%D9%84%D8%A3%D8%AD%D8%AF/",
]

DOSTOR_URLS = [
    "https://www.dostor.org/5440199",
    "https://www.dostor.org/5446975",
    "https://www.dostor.org/5417310",
    "https://www.dostor.org/5437888",
    "https://www.dostor.org/5427350",
]


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=15)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    return BeautifulSoup(resp.text, "html.parser")


def _extract_first_number_near(keyword: str, text: str) -> float | None:
    idx = text.find(keyword)
    if idx == -1:
        return None
    segment = text[idx : idx + 200]
    m = re.search(r"(\d+(?:\.\d+)?)\s*جنيه", segment)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)", segment)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def parse_almasry(url: str) -> Dict | None:
    soup = _fetch(url)
    if not soup:
        return None
    page_text = soup.get_text(" ", strip=True)
    date = parse_arabic_date(page_text)
    title_el = soup.find("h1") or soup.title
    title = title_el.get_text(strip=True) if title_el else ""

    # Prefer explicit "سعر / أسعار الفراخ البيضاء"
    price = _extract_first_number_near("سعر كيلو الفراخ البيضاء", page_text)
    if price is None:
        price = _extract_first_number_near("أسعار الفراخ البيضاء", page_text)
    if price is None:
        price = _extract_first_number_near("سعر الفراخ البيضاء", page_text)
    if price is None:
        price = _extract_first_number_near("الفراخ البيضاء", page_text)

    if price is None or date is None:
        return None

    return {
        "date": date,
        "source": "almasryalyoum",
        "url": url,
        "title": title,
        "price_white_broiler_egp": price,
    }


def parse_almal(url: str) -> Dict | None:
    soup = _fetch(url)
    if not soup:
        return None
    page_text = soup.get_text(" ", strip=True)
    date = parse_arabic_date(page_text)
    title_el = soup.find("h1") or soup.title
    title = title_el.get_text(strip=True) if title_el else ""

    # Al-Mal often phrases it as "البورصة عند 100و101" etc.
    # We treat the central farm price as the first 1–2 numbers after "فى السوق عند".
    price = _extract_first_number_near("الدجاج الأبيض", page_text)
    if price is None:
        price = _extract_first_number_near("الفراخ اليوم", page_text)
    if price is None:
        price = _extract_first_number_near("أسعار الفراخ", page_text)

    if price is None or date is None:
        return None

    return {
        "date": date,
        "source": "almalnews",
        "url": url,
        "title": title,
        "price_white_broiler_egp": price,
    }


def parse_dostor(url: str) -> Dict | None:
    soup = _fetch(url)
    if not soup:
        return None
    page_text = soup.get_text(" ", strip=True)
    date = parse_arabic_date(page_text)
    title_el = soup.find("h1") or soup.title
    title = title_el.get_text(strip=True) if title_el else ""

    # Dostor examples: "سجل سعر كيلو الفراخ البيضاء ... نحو 101 جنيه للكيلو تسليم أرض المزرعة"
    price = _extract_first_number_near("سعر كيلو الفراخ البيضاء", page_text)
    if price is None:
        price = _extract_first_number_near("سعر الفراخ البيضاء", page_text)
    if price is None:
        price = _extract_first_number_near("الفراخ البيضاء", page_text)

    if price is None or date is None:
        return None

    return {
        "date": date,
        "source": "dostor",
        "url": url,
        "title": title,
        "price_white_broiler_egp": price,
    }


def build_news_df() -> pd.DataFrame:
    rows: List[Dict] = []

    print("Scraping Al-Masry Al-Youm articles...", flush=True)
    for i, u in enumerate(ALMASRY_URLS, 1):
        print(f"[AlMasry {i}/{len(ALMASRY_URLS)}] {u}", flush=True)
        row = parse_almasry(u)
        if row:
            rows.append(row)
        time.sleep(0.5)

    print("Scraping Al-Mal articles...", flush=True)
    for i, u in enumerate(ALMAL_URLS, 1):
        print(f"[AlMal {i}/{len(ALMAL_URLS)}] {u}", flush=True)
        row = parse_almal(u)
        if row:
            rows.append(row)
        time.sleep(0.5)

    print("Scraping Dostor articles...", flush=True)
    for i, u in enumerate(DOSTOR_URLS, 1):
        print(f"[Dostor {i}/{len(DOSTOR_URLS)}] {u}", flush=True)
        row = parse_dostor(u)
        if row:
            rows.append(row)
        time.sleep(0.5)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        df = df[df["date"] >= pd.Timestamp("2024-01-01")]
    return df


def main() -> None:
    print("Building news-based broiler price dataset (2024+)...", flush=True)
    df = build_news_df()
    if df.empty:
        print("No rows scraped; check connectivity.")
        return
    out_path = "news_broiler_prices_2024_2026.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

