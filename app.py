import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# === PAGE CONFIG ===
st.set_page_config(page_title="SolarAI Optimizer™", layout="wide")

# === LOCATION BUTTONS ===
st.markdown("### 🌍 Select Location")
col_loc1, col_loc2 = st.columns(2)
with col_loc1:
    if st.button("📍 Limpopo (Polokwane)", use_container_width=True):
        st.session_state.location = "limpopo"
with col_loc2:
    if st.button("🌞 Nelspruit (Mbombela)", use_container_width=True):
        st.session_state.location = "nelspruit"

if "location" not in st.session_state:
    st.session_state.location = "limpopo"

# === REFRESH BUTTON ===
if st.button("🔄 Reset / Refresh Demo", use_container_width=True):
    st.success("Refreshing... Page will reload shortly.")
    st.rerun()

# === HEADER ===
st.title("☀️ SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# === LOCATION COORDINATES ===
locations = {
    "limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
    "nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694},
}
loc = locations[st.session_state.location]
st.markdown(f"**📡 Current Location:** {loc['name']}")

# === FETCH DATA ===
@st.cache_data(ttl=3600, show_spinner=False)
def get_solcast_forecast(lat: float, lon: float, api_key: str = "demo") -> pd.DataFrame:
    """Return solar irradiance (GHI) forecast for 14 days (hourly)."""
    try:
        if api_key and api_key != "demo":
            url = (
                f"https://api.solcast.com.au/radiation/forecasts?"
                f"latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
            )
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()["forecasts"]
            df = pd.DataFrame(data)
            df["Time"] = pd.to_datetime(df["period_end"])
            df["Solar Yield (W/m²)"] = df["ghi"]
            return df[["Time", "Solar Yield (W/m²)"]].tail(336)
    except Exception as e:
        st.warning(f"⚠️ API unavailable — using demo data ({e})")

    # === Demo synthetic data (HOURLY for 14 days) ===
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(now - timedelta(days=14), now + timedelta(days=1), freq="1h")
    hours = index.hour + index.minute / 60
    seasonal = 1.2 if now.month in [11, 12, 1, 2] else 0.8
    ghi = np.maximum(
        0,
        800 * np.sin((hours - 12) * np.pi / 12) * seasonal
        + np.random.normal(0, 40, len(index)),
    )
    return pd.DataFrame({"Time": index, "Solar Yield (W/m²)": ghi})

# === SIDEBAR ===
st.sidebar.header("⚙️ Your Solar System")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Daily Usage (hours)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.5)
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")

# === FETCH FORECAST DATA ===
df = get_solcast_forecast(loc["lat"], loc["lon"], api_key=solcast_key)

# === VIEW TOGGLE ===
view_mode = st.radio(
    "📊 Select View:",
    ["24 Hours (Today)", "14-Day Forecast"],
    horizontal=True,
)

# === FILTER VIEW ===
now = datetime.now()
today = now.date()
start_of_day = datetime.combine(today, datetime.min.time())
end_of_day = start_of_day + timedelta(days=1)

if view_mode == "24 Hours (Today)":
    df_view = df[(df["Time"] >= start_of_day) & (df["Time"] < end_of_day)]
else:
    df_view = df.copy()

# === CALCULATIONS ===
avg_ghi = df_view["Solar Yield (W/m²)"].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * 14
used_kwh = system_size_kw * hours_used_per_day * 14
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh

best_idx = df_view["Solar Yield (W/m²)"].idxmax()
best_time = pd.Timestamp(df_view.loc[best_idx, "Time"]).strftime("%I:%M %p")

# === GRAPH (ENHANCED) ===
fig = px.line(
    df_view,
    x="Time",
    y="Solar Yield (W/m²)",
    title=f"☀️ Global Horizontal Irradiance — {loc['name']} ({view_mode})",
    labels={"Solar Yield (W/m²)": "Yield (W/m²)", "Time": "Date & Time"},
)

fig.update_traces(
    line=dict(color="#007BFF", width=2.5),
    hovertemplate="Time: %{x|%H:%M}<br>Yield: %{y:.1f} W/m²<extra></extra>",
)

# Layout & interactivity tuning
fig.update_layout(
    height=460,
    margin=dict(l=30, r=30, t=60, b=40),
    title_x=0.5,
    hovermode="x unified",   # Single vertical line that follows the finger/mouse
    hoverdistance=30,        # Increases tolerance for touch input
    spikedistance=30,        # Keeps the spike line visible during drag
    xaxis=dict(
        showgrid=True,
        gridwidth=0.3,
        gridcolor="rgba(180,180,180,0.3)",
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="rgba(255,255,255,0.8)",
        spikethickness=1.2,
    ),
    yaxis=dict(
        showgrid=True,
        gridwidth=0.3,
        gridcolor="rgba(180,180,180,0.3)",
        showspikes=True,
        spikemode="across",
        spikecolor="rgba(255,255,255,0.8)",
        spikethickness=1.2,
    ),
)

# Enable drag-to-inspect mode by default (no zoom needed)
config = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": False,   # Prevent accidental zoom while dragging
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
    "doubleClick": "reset",  # Double-tap to reset zoom if you do zoom
}

# === MAIN LAYOUT ===
col1, col2 = st.columns([1.8, 1.2], gap="large")

with col1:
    st.subheader("🔆 Solar Yield Forecast")
    st.plotly_chart(fig, use_container_width=True, config=config)
    st.markdown(
        """
**📘 Reading the Graph**
- **X-axis:** Time of day  
- **Y-axis:** Sunlight intensity (W/m²)  
- **Blue line:** Forecasted sunlight strength  
- **Peaks around 12 PM = Best production hours**  
- **Touch or hover to inspect values**  
- **Double-tap to reset zoom.**
        """
    )

with col2:
    st.subheader("🤖 Live AI Insights")
    st.metric("Best Time to Charge", best_time)
    st.metric("14-Day Solar", f"{total_solar_kwh:.1f} kWh", delta=f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Money Saved", f"R{saved_r:.0f}", delta=f"≈ R{saved_r/14:.0f}/day")

    if st.button("⚡ Simulate Charge Now", use_container_width=True):
        st.success(f"Geyser ON at {best_time} in {loc['name']}! Saved R{saved_r:.0f}.")

# === FOOTER ===
st.markdown("---")
st.info(f"💡 AI Suggestion: Charge at **{best_time}** in **{loc['name']}** to maximize free solar power.")
st.caption("R1 200 Raspberry Pi + AI | R99/month | Contact: **Keanu.kruger05@gmail.com**")
