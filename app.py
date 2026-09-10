"""Weather Trends Dashboard — is it getting hotter?

Fetches decades of daily historical temperature data (Open-Meteo archive), aggregates to yearly and seasonal averages,
and fits a linear trend to determine if the long-term average temperature is rising, falling, or constant?
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from benchmark_cities import BENCHMARK_CITIES
from trend_analysis import SEASON_ORDER, add_year_season, fit_trend, seasonal_yearly_means, yearly_mean_temps
from weather_api import geocode_city, get_historical_daily, historical_to_dataframe

st.set_page_config(page_title="Weather Trends Dashboard", page_icon="🌡️", layout="wide")

SEASON_COLORS = {"Winter": "#3d5a80", "Spring": "#588157", "Summer": "#e07a5f", "Fall": "#bc6c25"}

#cache results of city search to avoid multiple api calls, cache expires after 1 day
@st.cache_data(ttl="1d", show_spinner=False)
def fetch_history(latitude: float, longitude: float, start_year: int, end_year: int):
    raw = get_historical_daily(latitude, longitude, start_year, end_year)
    return historical_to_dataframe(raw)

#cache benchmark trends, no ttl, 
@st.cache_data(show_spinner=False)
def load_benchmark_trends(years_back: int) -> pd.DataFrame:
    """Load precomputed global benchmark trends (see build_benchmark.py) for a given window size."""
    all_benchmarks = pd.read_csv("benchmark_trends.csv")
    return all_benchmarks[all_benchmarks["years_back"] == years_back][["city", "trend_c_per_decade"]].reset_index(drop=True)


st.title("🌡️ Weather Trends Dashboard")
st.caption("Is it getting hotter? Explore long-term temperature trends for any city using historical daily data.")

def label_for(row) -> str:
    parts = [row["name"]]
    if isinstance(row.get("admin1"), str):
        parts.append(row["admin1"])
    parts.append(row["country"])
    return ", ".join(parts)


with st.sidebar:
    st.header("Search")
    with st.form("search_form"):
        city_query = st.text_input("City name", value="Seattle")
        years_back = st.slider("Years of history", min_value=10, max_value=40, value=30, step=5)
        search_clicked = st.form_submit_button("Search", type="primary")

#st.sessions_state persists data across user's browsing session since the script reruns with each interaction, variables not shared between runs
#a new session created every browser tab that connects to st server
#initialize locations to none
if "locations" not in st.session_state:
    st.session_state.locations = None

#save city dataframe to session_state.locations
if search_clicked and city_query.strip():
    with st.spinner("Looking up city..."):
        st.session_state.locations = geocode_city(city_query.strip())

locations = st.session_state.locations

if locations is None:
    st.info("Enter a city name in the sidebar and click **Search** to get started.")
    st.stop()

if locations.empty:
    st.error(f"No matches found for '{city_query}'. Try a different spelling.")
    st.stop()

#replace index with default 0, 1, 2 sequence in case the index was messed up by filtering data
#locations = locations.reset_index(drop=True) 
labels = [label_for(r) for _, r in locations.iterrows()]
with st.sidebar:
    choice_idx = st.selectbox("Matching locations", options=range(len(labels)), format_func=lambda i: labels[i])
location = locations.loc[choice_idx]

end_year = date.today().year - 1  # last complete calendar year
start_year = end_year - years_back + 1

with st.spinner(f"Fetching {start_year}–{end_year} daily history..."):
    daily_df = fetch_history(location["latitude"], location["longitude"], start_year, end_year)

if daily_df.empty:
    st.error("No historical data available for this location.")
    st.stop()

daily_df = add_year_season(daily_df)
yearly_df = yearly_mean_temps(daily_df)

if len(yearly_df) < 5:
    st.error("Not enough complete years of data to fit a trend. Try a shorter history window.")
    st.stop()

st.subheader(f"📍 {label_for(location)} — {yearly_df['year'].min()}–{yearly_df['year'].max()}")

overall = fit_trend(yearly_df["year"], yearly_df["mean_temp_c"])
direction = "warming" if overall["slope_per_decade_c"] > 0 else "cooling" if overall["slope_per_decade_c"] < 0 else "flat"
significant = overall["p_value"] < 0.05

col1, col2, col3 = st.columns(3)
col1.metric("Trend", f"{overall['slope_per_decade_c']:+.2f} °C / decade")
col2.metric("Fit quality (R²)", f"{overall['r_squared']:.2f}")
col3.metric("p-value", f"{overall['p_value']:.3f}")

verdict = (
    f"Over {len(yearly_df)} years of data, the average temperature is **{direction}** at "
    f"**{overall['slope_per_decade_c']:+.2f} °C per decade**."
)
if significant:
    st.success(verdict + " This trend is statistically significant (p < 0.05).")
else:
    st.warning(verdict + " This trend is **not** statistically significant (p ≥ 0.05) — treat it as noisy.")

st.divider()

st.subheader("Yearly Average Temperature")
fig_yearly = go.Figure()
fig_yearly.add_trace(
    go.Scatter(
        x=yearly_df["year"], y=yearly_df["mean_temp_c"], name="Yearly average",
        mode="lines+markers", line=dict(color="#457b9d"),
    )
)
trend_x = [yearly_df["year"].min(), yearly_df["year"].max()]
trend_y = [overall["predict"](x) for x in trend_x]
fig_yearly.add_trace(
    go.Scatter(x=trend_x, y=trend_y, name="Linear trend", mode="lines", line=dict(color="#e63946", dash="dash"))
)
fig_yearly.update_layout(xaxis_title="Year", yaxis_title="°C", hovermode="x unified", height=400, margin=dict(t=20, b=20))
st.plotly_chart(fig_yearly, use_container_width=True)

st.divider()

st.subheader("Global Comparison")
try:
    benchmark_df = load_benchmark_trends(years_back)
except FileNotFoundError:
    benchmark_df = pd.DataFrame()

if benchmark_df.empty:
    st.info(
        "No precomputed global benchmark found. Run `python build_benchmark.py` once to generate "
        "`benchmark_trends.csv`."
    )
else:
    benchmark_avg = benchmark_df["trend_c_per_decade"].mean()
    diff = overall["slope_per_decade_c"] - benchmark_avg
    comparison_word = "faster than" if diff > 0 else "slower than" if diff < 0 else "at the same rate as"
    percentile = (benchmark_df["trend_c_per_decade"] < overall["slope_per_decade_c"]).mean() * 100

    st.markdown(
        f"**{label_for(location)}** is warming **{abs(diff):.2f} °C/decade {comparison_word}** the "
        f"{len(benchmark_df)}-city global benchmark average of **{benchmark_avg:+.2f} °C/decade** "
        f"— faster than **{percentile:.0f}%** of benchmark cities."
    )

    selected_label = f"{label_for(location)} (selected)"
    compare_df = pd.concat(
        [
            benchmark_df,
            pd.DataFrame([{"city": selected_label, "trend_c_per_decade": overall["slope_per_decade_c"]}]),
        ],
        ignore_index=True,
    ).sort_values("trend_c_per_decade")

    bar_colors = ["#e63946" if c == selected_label else "#457b9d" for c in compare_df["city"]]
    fig_compare = go.Figure(
        go.Bar(
            x=compare_df["trend_c_per_decade"], y=compare_df["city"], orientation="h",
            marker_color=bar_colors, name="Trend",
        )
    )
    fig_compare.add_vline(x=benchmark_avg, line_dash="dash", line_color="gray", annotation_text="Benchmark avg")
    fig_compare.update_layout(xaxis_title="°C / decade", height=600, margin=dict(t=20, b=20))
    st.plotly_chart(fig_compare, use_container_width=True)

st.divider()

st.subheader("Seasonal Breakdown")
st.caption("Meteorological seasons, Northern Hemisphere convention (Dec–Feb = Winter, etc.).")

seasonal_df = seasonal_yearly_means(daily_df)
seasonal_trends = {}
for season in SEASON_ORDER:
    subset = seasonal_df[seasonal_df["season"] == season]
    if len(subset) >= 5:
        seasonal_trends[season] = fit_trend(subset["year"], subset["mean_temp_c"])

fig_seasonal = make_subplots(rows=2, cols=2, subplot_titles=SEASON_ORDER)
positions = {"Winter": (1, 1), "Spring": (1, 2), "Summer": (2, 1), "Fall": (2, 2)}
for season in SEASON_ORDER:
    subset = seasonal_df[seasonal_df["season"] == season]
    if subset.empty:
        continue
    row, col = positions[season]
    color = SEASON_COLORS[season]
    fig_seasonal.add_trace(
        go.Scatter(
            x=subset["year"], y=subset["mean_temp_c"], mode="lines+markers", line=dict(color=color),
            name=f"{season} average", showlegend=False,
        ),
        row=row, col=col,
    )
    trend = seasonal_trends.get(season)
    if trend:
        tx = [subset["year"].min(), subset["year"].max()]
        ty = [trend["predict"](x) for x in tx]
        fig_seasonal.add_trace(
            go.Scatter(
                x=tx, y=ty, mode="lines", line=dict(color=color, dash="dash"),
                name=f"{season} trend", showlegend=False,
            ),
            row=row, col=col,
        )
fig_seasonal.update_layout(height=550, margin=dict(t=40, b=20))
st.plotly_chart(fig_seasonal, use_container_width=True)

if seasonal_trends:
    seasonal_summary_df = pd.DataFrame(
        [
            {
                "season": season,
                "trend_c_per_decade": round(trend["slope_per_decade_c"], 2),
                "r_squared": round(trend["r_squared"], 2),
                "p_value": round(trend["p_value"], 3),
                "significant": trend["p_value"] < 0.05,
            }
            for season, trend in seasonal_trends.items()
        ]
    )
    st.dataframe(seasonal_summary_df, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Data")
tab1, tab2 = st.tabs(["Yearly averages", "Daily raw data"])
with tab1:
    st.dataframe(yearly_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download yearly averages as CSV",
        data=yearly_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{location['name']}_yearly_avg_temp.csv",
        mime="text/csv",
    )
with tab2:
    st.dataframe(daily_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download daily data as CSV",
        data=daily_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{location['name']}_daily_temp.csv",
        mime="text/csv",
    )

with st.expander("Methodology"):
    st.markdown(
        f"""
- **Data source:** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
  (ERA5 reanalysis), no API key required.
- **Window:** full calendar years {start_year}–{end_year} only — the current partial year is excluded
  so seasonal mix doesn't bias the average.
- **Yearly average:** mean of daily mean temperature, requiring at least 300 days of data in a year.
- **Trend:** ordinary least-squares linear regression of yearly (or seasonal-yearly) average temperature
  against year. Reported as °C change per decade, with R² (fit quality) and p-value (significance,
  p < 0.05 conventionally considered significant).
- **Seasons:** meteorological seasons, Northern Hemisphere convention (Dec–Feb Winter, Mar–May Spring,
  Jun–Aug Summer, Sep–Nov Fall). December is grouped with the following January/February.
- **Global benchmark:** a fixed set of {len(BENCHMARK_CITIES)} cities spread across continents (see
  `benchmark_cities.py`), each fit with the same trend method over the same window, then averaged.
  This is a convenience sample, not a scientifically weighted global mean. It's precomputed offline
  (`build_benchmark.py`) into `benchmark_trends.csv` rather than fetched live, since 18 rapid archive
  requests reliably tripped the free API's rate limit — reference data like this doesn't need to be
  fetched on every page load anyway.
"""
    )

st.caption("Data: [Open-Meteo](https://open-meteo.com/) — free historical weather archive, no key required.")
