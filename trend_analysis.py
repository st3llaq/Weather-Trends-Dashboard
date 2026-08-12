"""Aggregation and trend-fitting helpers for the historical temperature dashboard."""

import pandas as pd
from scipy import stats

# Meteorological seasons, Northern Hemisphere convention (month -> season)
_MONTH_TO_SEASON = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Fall", 10: "Fall", 11: "Fall",
}
SEASON_ORDER = ["Winter", "Spring", "Summer", "Fall"]


def add_year_season(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["season"] = df["month"].map(_MONTH_TO_SEASON)
    # December belongs to the following winter (e.g. Dec 1996 -> winter 1997)
    df["season_year"] = df["year"].where(df["month"] != 12, df["year"] + 1)
    return df


def yearly_mean_temps(df: pd.DataFrame, min_days: int = 300) -> pd.DataFrame:
    """One row per calendar year with the mean daily temperature. Drops years with sparse data."""
    grouped = df.groupby("year")["temp_mean_c"].agg(mean_temp_c="mean", n_days="count").reset_index()
    return grouped[grouped["n_days"] >= min_days].reset_index(drop=True)


def seasonal_yearly_means(df: pd.DataFrame, min_days: int = 80) -> pd.DataFrame:
    """One row per (season_year, season) with the mean daily temperature for that season."""
    grouped = (
        df.groupby(["season_year", "season"])["temp_mean_c"]
        .agg(mean_temp_c="mean", n_days="count")
        .reset_index()
        .rename(columns={"season_year": "year"})
    )
    return grouped[grouped["n_days"] >= min_days].reset_index(drop=True)


def fit_trend(years: pd.Series, values: pd.Series) -> dict:
    """Fit a linear trend (value ~ year). Returns slope per year/decade, fit quality, and significance."""
    result = stats.linregress(years, values)
    return {
        "slope_per_year_c": result.slope,
        "slope_per_decade_c": result.slope * 10,
        "intercept": result.intercept,
        "r_squared": result.rvalue ** 2,
        "p_value": result.pvalue,
        "predict": lambda x: result.slope * x + result.intercept,
    }
