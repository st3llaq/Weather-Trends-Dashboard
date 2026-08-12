"""Thin client for the Open-Meteo geocoding and historical archive APIs (no API key required)."""

import time

import pandas as pd
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _get_with_retry(url: str, params: dict, timeout: int, max_retries: int = 6) -> requests.Response:
    """GET with exponential backoff on 429 (rate limit) and 5xx responses."""
    for attempt in range(max_retries + 1):
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else min(5 * (2 ** attempt), 120)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp


def geocode_city(name: str, count: int = 5) -> pd.DataFrame:
    """Look up candidate locations for a city name. Returns an empty DataFrame if none found."""
    resp = _get_with_retry(
        GEOCODING_URL,
        params={"name": name, "count": count, "language": "en", "format": "json"},
        timeout=10,
    )
    results = resp.json().get("results", [])
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    keep = ["name", "country", "admin1", "latitude", "longitude", "timezone"]
    return df[[c for c in keep if c in df.columns]]


def get_historical_daily(latitude: float, longitude: float, start_year: int, end_year: int) -> dict:
    """Fetch daily historical temperatures for full calendar years [start_year, end_year]."""
    resp = _get_with_retry(
        ARCHIVE_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": f"{start_year}-01-01",
            "end_date": f"{end_year}-12-31",
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean",
            "timezone": "auto",
        },
        timeout=30,
    )
    return resp.json()


def historical_to_dataframe(archive_json: dict) -> pd.DataFrame:
    """Flatten the 'daily' block of an archive response into a tidy DataFrame, dropping missing days."""
    daily = archive_json["daily"]
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "temp_max_c": daily["temperature_2m_max"],
            "temp_min_c": daily["temperature_2m_min"],
            "temp_mean_c": daily["temperature_2m_mean"],
        }
    )
    return df.dropna(subset=["temp_mean_c"])
