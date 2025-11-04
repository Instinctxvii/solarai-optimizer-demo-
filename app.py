import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# === LOCATION BUTTONS ===
st.markdown("### Select Location")
col_loc1, col_loc2 = st.columns(2)
with col_loc1:
    if st.button("Limpopo (Polokwane)", type="secondary", use_container_width=True):
        st.session_state.location = "limpopo"
with col_loc2:
    if st.button("Nelspruit (Mpumalanga)", type="secondary", use_container_width=True):
        st.session_state.location = "nelspruit"

if "location" not in st.session_state:
    st.session_state.location = "limpopo"

# === REFRESH ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    st.rerun()

st.title("SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99 / month**")

# === LOCATION COORDINATES ===
locations = {
    "limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
    "nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694},
}
loc = locations[st.session_state.location]
st.markdown(f"**Current Location:** {loc['name']}")

# === FETCH DATA ===
@st.cache_data(ttl=3600, show_spinner=False)
def get_solcast_forecast(lat: float, lon: float, api_key: str = "demo") -> pd.DataFrame:
    """Return hourly (or half-hourly) GHI forecast for 14 days.  
    Falls back to demo data when no API key is supplied."""
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
        st.warning(f"API unavailable → using demo data ({e})")

    # Demo synthetic data: every 30 minutes for 14 days
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(now - timedelta(hours=12), periods=24 * 14 * 2, freq="30min")
    hours = index.hour + index.minute / 60
    seasonal = 1.2 if now.month in [11, 12, 1, 2] else 0.8
    ghi = np.maximum(
        0,
        800 * np.sin((hours - 12) * np.pi / 12) * seasonal
        + np.random.normal(0, 40, len(index)),
    )
    return pd.DataFrame({"Time": index, "Solar Yield (W/m²)": ghi})

# === SIDEBAR ===
st.sidebar.header("Your Solar System")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Daily Usage (hours)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.5)
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")

# === GET DATA ===
df = get_solcast_forecast(loc["lat"], loc["lon"], api_key=solcast_key)

# === VIEW TOGGLE ===
view_mode = st.radio(
    "Select View:",
    ["Today Only", "Yesterday", "24 Hours (rolling)", "14-Day Forecast"],
    horizontal=True,
)

now = datetime.now()
today = now.date()
yesterday = today - timedelta(days=1)

if view_mode == "Today Only":
    df_view = df[df["Time"].dt.date == today]
elif view_mode == "Yesterday":
    df_view = df[df["Time"].dt.date == yesterday]
elif view_mode == "24 Hours (rolling)":
    df_view = df[(df["Time"] > now - timedelta(hours=24)) & (df["Time"] <= now)]
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

# === GRAPH ===
fig = px.line(
    df_view,
    x="Time",
    y="Solar Yield (W/m²)",
    title=f"GHI — {loc['name']} ({view_mode})",
    labels={"Solar Yield (W/m²)": "Yield (W/m²)", "Time": "Date & Time"},
)
fig.update_layout(
    height=420,
    margin=dict(l=40, r=40, t=60, b=40),
    title_x=0.5,
    hovermode="x unified",
)
config = {"displayModeBar": False, "displaylogo": False}

# === MAIN LAYOUT ===
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Solar Yield Forecast")
    st.plotly_chart(fig, use_container_width=True, config=config)
    st.markdown(
        """
**Reading the Graph**
- **X-axis:** Time  
- **Y-axis:** Sunlight (W/m²)  
- **Blue line:** Forecasted solar irradiance  
- **Peaks around 12 PM = best production hours**  
"""
    )
with col2:
    st.subheader("Live AI Insights")
    st.metric("Best Time to Charge", best_time)
    st.metric("14-Day Solar", f"{total_solar_kwh:.1f} kWh", delta=f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Money Saved", f"R{saved_r:.0f}", delta=f"R{saved_r/14:.0f}/week")
    if st.button("Simulate Charge Now", type="primary"):
        st.success(f"Geyser ON at {best_time} in {loc['name']}! Saved R{saved_r:.0f}.")

st.info(f"AI says: **Charge at {best_time}** in **{loc['name']}** for ≈ {daily_solar_kwh:.1f} kWh free power.")
st.caption("R1 200 Raspberry Pi + AI | R99/month | Contact: Keanu.kruger05@gmail.com")
