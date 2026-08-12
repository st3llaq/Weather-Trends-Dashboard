# Weather Trends Dashboard

A data-analysis project built with **Streamlit**, **pandas**, **SciPy**, and **Plotly** that answers a simple question for any city: **is it getting hotter?**

Search a city, pick how many years of history to look at, and the dashboard fetches decades of daily historical temperature, aggregates it to yearly and seasonal averages, and fits a linear trend to quantify warming (or cooling) in °C per decade — with fit quality (R²) and statistical significance (p-value).

Data comes from the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (ERA5 reanalysis), which is free and requires no API key.

## Features

- City search with geocoding (handles ambiguous names, e.g. multiple "Springfield"s)
- Configurable history window (10–40 years), using only full calendar years to avoid seasonal bias
- Headline trend metric: °C change per decade, R², and p-value, with a plain-language verdict on significance
- Yearly average temperature chart with an overlaid linear regression trend line
- Seasonal breakdown: per-season (Winter/Spring/Summer/Fall) trend charts and a summary table
- Global comparison: is this city warming faster or slower than a benchmark of 18 cities spread across continents?
- Yearly and daily data tables with CSV export
- Methodology notes explaining data source, aggregation rules, and statistical method

## Setup

```bash
pip install -r requirements.txt
```

The global comparison feature needs a one-time precomputed reference file. Generate it once:

```bash
python build_benchmark.py
```

This fetches 18 benchmark cities from the Open-Meteo archive and writes `benchmark_trends.csv`. It's precomputed
(rather than fetched live on every page load) because the free archive API rate-limits bursts of requests, and
reference data like this doesn't need to be re-fetched constantly anyway. Re-run it occasionally to refresh the
reference data. If the file is missing, the app still works — the comparison section just shows a note instead.

## Run

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

## Project structure

- `app.py` — Streamlit UI and layout
- `weather_api.py` — Open-Meteo API client (geocoding + historical archive), returns pandas DataFrames
- `trend_analysis.py` — yearly/seasonal aggregation and linear-regression trend fitting (SciPy)
- `benchmark_cities.py` — fixed list of cities used for the global comparison
- `build_benchmark.py` — one-off script that precomputes `benchmark_trends.csv`

## Tech stack

Python, Streamlit, pandas, SciPy, Plotly, Requests.
