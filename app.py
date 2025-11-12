import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
import random

st.set_page_config(page_title="SolarcallAI™", layout="wide")

# === REFRESH ===
if st.button("Refresh Demo", type="primary", use_container_width=True):
    st.success("Refreshing...")
    time.sleep(1)
    st.rerun()

st.title("SolarcallAI™")
st.markdown("**AI Solar Geyser Control | R149/month | R0 Upfront**")

# === LOCATION ===
st.markdown("### Enter Your Location")

col_auto, col_search = st.columns([1, 3])

with col_auto:
    if st.button("Use My Location", type="secondary", use_container_width=True):
        st.session_state.gps_active = True
        st.rerun()

# === GPS ===
if st.session_state.get("gps_active", False):
    status = st.empty()
    status.markdown("**Finding your address...**")

    js = """
    <script>
    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
            pos => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                window.location.href = `?lat=${lat}&lon=${lon}`;
            },
            () => window.parent.postMessage({error: "denied"}, "*"),
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }
    </script>
    """
    st.components.v1.html(js, height=0)

    params = st.experimental_get_query_params()
    if "lat" in params and "lon" in params:
        try:
            lat, lon = float(params["lat"][0]), float(params["lon"][0])
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
            data = requests.get(url, headers={"User-Agent": "SolarcallAI/1.0"}, timeout=10).json()
            addr = data.get("address", {})
            house = addr.get("house_number", "")
            road = addr.get("road", addr.get("pedestrian", ""))
            suburb = addr.get("suburb", addr.get("neighbourhood", ""))
            city = addr.get("city", addr.get("town", ""))
            province = addr.get("province", addr.get("state", ""))
            parts = [p for p in [house, road, suburb, city, province] if p]
            name = ", ".join(parts) if parts else "Your Location"
            st.session_state.location_name = name
            st.session_state.lat = lat
            st.session_state.lon = lon
            status.success(f"**Found: {name}**")
            st.experimental_set_query_params()
            st.session_state.gps_active = False
        except:
            status.error("Address not found.")
            st.session_state.gps_active = False

# === SEARCH ===
with col_search:
    search_query = st.text_input(
        "Or search street/suburb", placeholder="114 Clivia Street, Nelspruit...", key="search_input"
    )

if search_query and len(search_query) > 2:
    with st.spinner("Searching..."):
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": search_query, "format": "json", "limit": 10, "countrycodes": "za", "addressdetails": 1}
            results = requests.get(url, params=params, headers={"User-Agent": "SolarcallAI/1.0"}, timeout=10).json()
            options = []
            seen = set()
            for r in results:
                addr = r.get("address", {})
                house = addr.get("house_number", "")
                road = addr.get("road", addr.get("pedestrian", ""))
                suburb = addr.get("suburb", addr.get("neighbourhood", ""))
                city = addr.get("city", addr.get("town", ""))
                province = addr.get("province", addr.get("state", ""))
                parts = [p for p in [house, road, suburb, city, province] if p]
                full = ", ".join(parts)
                if full and full not in seen and "ward" not in full.lower():
                    seen.add(full)
                    options.append((full, float(r["lat"]), float(r["lon"])))
            if options:
                selected = st.selectbox("Select address:", [""] + [opt[0] for opt in options], key="location_select")
                if selected:
                    for name, lat, lon in options:
                        if name == selected:
                            st.session_state.location_name = name
                            st.session_state.lat = lat
                            st.session_state.lon = lon
                            st.success(f"**Selected: {name}**")
                            break
            else:
                st.warning("No address found.")
        except:
            st.error("Search failed.")

# === FALLBACK ===
if 'location_name' not in st.session_state:
    st.session_state.location_name = "Limpopo (Polokwane)"
    st.session_state.lat = -23.8962
    st.session_state.lon = 29.4486

st.markdown(f"**Current Location: {st.session_state.location_name}**")

# === FORECAST ===
col_range, col_reset = st.columns([1, 1])
with col_range:
    days = st.radio("Forecast", [7, 14], horizontal=True, index=1)
with col_reset:
    if st.button("Reset Graph", type="secondary"):
        st.rerun()

@st.cache_data(ttl=3600)
def get_forecast(lat, lon, days=14):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "direct_normal_irradiance",
        "forecast_days": days, "timezone": "Africa/Johannesburg"
    }
    try:
        data = requests.get(url, params=params, timeout=10).json()
        df = pd.DataFrame({
            "Time": pd.to_datetime(data["hourly"]["time"]),
            "Solar Yield (W/m²)": data["hourly"]["direct_normal_irradiance"]
        })
        return df
    except:
        now = datetime.now()
        index = pd.date_range(now, periods=days*24, freq='h')
        hours = index.hour
        ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) + np.random.normal(0, 50, len(index)))
        return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})

df = get_forecast(st.session_state.lat, st.session_state.lon, days=days)

# === POWER SIMULATION ===
def get_power():
    hour = datetime.now().hour
    return random.randint(850, 1200) if 11 <= hour <= 14 else random.randint(100, 500)

# === CALCULATIONS ===
avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * 5 * 5
total_solar_kwh = daily_solar_kwh * days
used_kwh = 5 * 6 * days
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * 2.50
weekly_savings = saved_r / days

# === BEST TIME TODAY ===
next_24h = df.head(24)
peak_today = next_24h[next_24h['Solar Yield (W/m²)'] > 800]
best_time_today = None
best_start = None
best_end = None

if not peak_today.empty:
    # Find longest continuous block > 800
    peak_today['block'] = (peak_today['Solar Yield (W/m²)'] <= 800).cumsum()
    blocks = peak_today.groupby('block').size()
    if not blocks.empty:
        best_block = blocks.idxmax()
        block_times = peak_today[peak_today['block'] == best_block]['Time']
        best_start = block_times.iloc[0].strftime("%I:%M %p")
        best_end = block_times.iloc[-1].strftime("%I:%M %p")
        best_time_today = f"{best_start} – {best_end}"

# === NEXT GEYSER ON ===
current_power = get_power()
next_on_msg = ""
precharge_msg = ""

if current_power <= 800:
    future = df[df['Time'] > datetime.now()]
    strong_sun = future[future['Solar Yield (W/m²)'] > 800]
    if not strong_sun.empty:
        next_time = strong_sun.iloc[0]['Time']
        if next_time.date() == datetime.now().date():
            next_on_msg = f"**Next ON: Today {next_time.strftime('%I:%M %p')}**"
        else:
            next_on_msg = f"**Next ON: {next_time.strftime('%d %b, %I:%M %p')}**"
    else:
        next_on_msg = "**No strong sun in 7 days — using grid backup**"

# === PRE-CHARGE MESSAGE (HOT AT 5 PM) ===
if best_time_today:
    precharge_msg = f"**Tank pre-charged {best_time_today} → Hot water ready by 5 PM**"

# === GRAPH ===
fig = px.line(df, x='Time', y='Solar Yield (W/m²)', title=f"{days}-Day AI Forecast")
fig.add_hline(y=800, line_dash="dash", line_color="orange", annotation_text="Geyser ON Threshold")
fig.update_layout(height=450, xaxis=dict(rangeselector=dict(buttons=[
    dict(count=1, label="1d", step="day"), dict(count=7, label="7d", step="day"), dict(step="all")
]), rangeslider=dict(visible=True)))
st.plotly_chart(fig, use_container_width=True)

# === CONTROL ===
if st.button("Simulate Geyser Control", type="primary", use_container_width=True):
    if current_power > 800:
        st.success("GEYSER ON — 100% Solar!")
        st.success("SMS: Geyser ON — 2hr hot water (free!)")
        if precharge_msg:
            st.success(precharge_msg)
    else:
        st.warning("Geyser OFF — Low sun")
        st.info(next_on_msg)
        if best_time_today:
            st.success(precharge_msg)

# === METRICS ===
col1, col2 = st.columns(2)
with col1:
    if best_time_today:
        st.metric("Best Charge Today", best_time_today)
    else:
        st.metric("Today", "Low Sun", "No ON time")
    st.metric("Money Saved", f"R{saved_r:.0f}", f"R{weekly_savings:.0f}/week")
with col2:
    st.metric(f"{days}-Day Solar", f"{total_solar_kwh:.1f} kWh", f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Current Solar", f"{current_power}W")

# === DISPLAY MESSAGES ===
if next_on_msg and current_power <= 800:
    st.warning(next_on_msg)

if precharge_msg:
    st.success(precharge_msg)

st.info(f"**AI says: Save R{saved_r:.0f} in {days} days!**")
st.caption("© 2025 SolarcallAI | info@solarcallai.co.za")
