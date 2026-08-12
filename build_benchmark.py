"""One-off script to precompute global benchmark warming trends into benchmark_trends.csv.

Not part of the live app — run manually to (re)generate the reference data:
    python build_benchmark.py

Fetches each benchmark city's daily history once (for the largest window the app offers),
then slices that same data to compute the trend for every window size the "Years of
history" slider supports. This keeps the one-time cost to one API call per city instead
of one per (city, window) pair.

Resumable: cities already present in an existing benchmark_trends.csv are skipped, and
progress is saved after every city, so a rate-limit failure partway through doesn't lose
earlier results — just re-run the script to pick up where it left off.
"""

import time
from datetime import date
from pathlib import Path

import pandas as pd

from benchmark_cities import BENCHMARK_CITIES
from trend_analysis import add_year_season, fit_trend, yearly_mean_temps
from weather_api import get_historical_daily, historical_to_dataframe

MAX_YEARS_BACK = 40
YEARS_BACK_OPTIONS = [10, 15, 20, 25, 30, 35, 40]  # must match the app's slider steps
OUTPUT_PATH = Path("benchmark_trends.csv")
DELAY_BETWEEN_REQUESTS_S = 5

end_year = date.today().year - 1
fetch_start_year = end_year - MAX_YEARS_BACK + 1

existing = pd.read_csv(OUTPUT_PATH) if OUTPUT_PATH.exists() else pd.DataFrame()
done_cities = set(existing["city"]) if not existing.empty else set()
rows = existing.to_dict("records")

remaining = [c for c in BENCHMARK_CITIES if f"{c['name']}, {c['country']}" not in done_cities]
if not remaining:
    print("All benchmark cities already present in benchmark_trends.csv — nothing to do.")
else:
    print(f"{len(done_cities)} cities already done, {len(remaining)} remaining.")

for i, city in enumerate(remaining):
    label = f"{city['name']}, {city['country']}"
    print(f"[{i + 1}/{len(remaining)}] {label}...")
    if i > 0:
        time.sleep(DELAY_BETWEEN_REQUESTS_S)

    try:
        raw = get_historical_daily(city["latitude"], city["longitude"], fetch_start_year, end_year)
    except Exception as exc:
        print(f"  Failed: {exc}. Progress so far is saved — re-run the script to resume.")
        break

    daily = add_year_season(historical_to_dataframe(raw))

    for years_back in YEARS_BACK_OPTIONS:
        window_start = end_year - years_back + 1
        subset = daily[daily["year"] >= window_start]
        yearly = yearly_mean_temps(subset)
        if len(yearly) < 5:
            continue
        trend = fit_trend(yearly["year"], yearly["mean_temp_c"])
        rows.append(
            {
                "years_back": years_back,
                "start_year": window_start,
                "end_year": end_year,
                "city": label,
                "trend_c_per_decade": trend["slope_per_decade_c"],
            }
        )

    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)  # save after every city

print(f"benchmark_trends.csv now has {len(rows)} rows covering {len(set(r['city'] for r in rows))} cities.")
