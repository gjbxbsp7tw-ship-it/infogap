#!/usr/bin/env python3
"""
Fetch CNY exchange rates from Frankfurter API.
Generates rates/cny_rates.json with 3-year history + latest rates.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

CURRENCIES = ["USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "HKD", "KRW", "SGD", "NZD", "THB"]
FRANKFURTER_BASE = "https://api.frankfurter.app"

# Output directory: rates/ relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RATES_DIR = os.path.join(SCRIPT_DIR, "rates")
os.makedirs(RATES_DIR, exist_ok=True)


def fetch_json(url, retries=3, delay=2.0):
    """Fetch JSON from URL with user-agent header and retry logic."""
    for attempt in range(retries):
        req = Request(url, headers={"User-Agent": "InfoGap-FetchRates/1.0"})
        try:
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
                return json.loads(data.decode("utf-8"))
        except Exception as e:
            print(f"  Attempt {attempt+1}/{retries} failed for {url}: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def get_monthly_dates():
    """Generate list of last-day-of-month dates from 2023-06 to now."""
    start = datetime(2023, 6, 1)
    end = datetime.now().replace(day=1)
    dates = []
    current = start
    while current <= end:
        # Last day of month
        if current.month == 12:
            next_month = datetime(current.year + 1, 1, 1)
        else:
            next_month = datetime(current.year, current.month + 1, 1)
        last_day = next_month - timedelta(days=1)
        # Cap at today if we're past today
        if last_day > datetime.now():
            last_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        dates.append(last_day.strftime("%Y-%m-%d"))
        current = next_month
    return dates


def main():
    print("Fetching CNY exchange rates from Frankfurter API...")

    # 1. Fetch latest rates
    symbols_str = ",".join(CURRENCIES)
    latest_url = f"{FRANKFURTER_BASE}/latest?from=CNY&to={symbols_str}"
    latest_data = fetch_json(latest_url)
    if not latest_data:
        print("Failed to fetch latest rates.", file=sys.stderr)
        sys.exit(1)
    latest_rates = latest_data.get("rates", {})
    print(f"  Latest rates: {len(latest_rates)} currencies")

    # 2. Fetch historical rates (monthly, last day of each month)
    dates = get_monthly_dates()
    history = []
    for idx, d in enumerate(dates):
        hist_url = f"{FRANKFURTER_BASE}/{d}?from=CNY&to={symbols_str}"
        hist_data = fetch_json(hist_url)
        if hist_data and "rates" in hist_data:
            history.append({"date": d, "rates": hist_data["rates"]})
            print(f"  {d}: OK")
        else:
            print(f"  {d}: FAILED, skipping", file=sys.stderr)
        # Be polite to the free API: delay between requests
        if idx < len(dates) - 1:
            time.sleep(1.0)

    # 3. Build output structure
    output = {
        "updated": datetime.now().isoformat(),
        "base": "CNY",
        "latest": latest_rates,
        "history": history,
    }

    # 4. Write to file
    output_path = os.path.join(RATES_DIR, "cny_rates.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(history)} months of history to {output_path}")


if __name__ == "__main__":
    main()
