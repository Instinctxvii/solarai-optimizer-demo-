import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import requests
import time
import random

# === CONFIG ===
st.set_page_config(page_title="SolarcallAI™", layout="wide")

# === REFRESH BUTTON ===
if st.button("Refresh Demo", type="primary", use_container_width=True):
    st.success("Refreshing...")
    time.sleep(1)
    st.rerun()

# === TITLE ===
st.title("SolarcallAI™")
st.markdown("**AI Solar Geyser Control | R149/month | R0 Upfront**")

# === LOCATION SEARCH ===
st.markdown("### Enter Your Location")

col_auto, col_search = st.columns([1, 3])
with col_auto:
    if st.button("Use My Location", type="secondary", use_container_width=True):
        st.session_state.gps_active = True
        st.rerun()

# === GPS ===
if st.session_state.get("gps_active", False):
    status = st.empty()
    status.markdown("**Detecting GPS...**")

    location_js = """
    <script>
    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                window.location.href = window.location.href.split('?')[0] + '?lat=' + lat + '&lon=' + lon;
            },
            function() {
                window.parent.postMessage({error: "Failed"}, "*");
            },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    }
    </script>
    """
    st.components.v1.html(location_js, height=0)

    params = st.experimental_get_query_params()
    if "lat" in params and "lon" in params:
        try:
            lat, lon = float(params["lat"][0]), float(params["lon"][0])
            response = requests.get(
                f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json",
                headers={"User-Agent": "SolarcallAI/1.0"}, timeout=5
            )
            data = response.json()
            addr = data.get("address", {})
            suburb = addr.get("suburb", addr.get("neighbourhood", addr.get("village", "")))
            city = addr.get("city", addr.get("town", ""))
            province = addr.get("province", addr.get("state", ""))
            name = f"{suburb or city}, {city or province}".strip(", ")
            st.session_state.location_name = name
            st.session_state.lat = lat
            st.session_state.lon = lon
            status.success(f"**Detected: {name}**")
            st.experimental_set_query_params()
            st.session_state.gps_active = False
        except:
            status.error("Location failed.")
            st.session_state.gps_active = False

# === SEARCH ===
with col_search:
    search_query = st.text_input(
        "Or search suburb", placeholder="Nelspruit, Soweto...", key="search_input"
    )

if search_query and len(search_query) > 2:
    with st.spinner("Searching..."):
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": search_query, "format": "json", "limit": 5, "countrycodes": "za", "addressdetails": 1},
                headers={"User-Agent": "SolarcallAI/1.0"}, timeout=5
            )
            results = response.json()
            if results:
                options = []
                for r in results:
                    addr = r.get("address", {})
                    suburb = addr.get("suburb", addr.get("neighbourhood", ""))
                    city = addr.get("city", addr.get("town", ""))
                    province = addr.get("province", "")
                    name = f"{suburb or city}, {city or province}".strip(", ")
                    options.append((name, float(r["lat"]), float(r["lon"])))
                selected = st.selectbox("Select:", [""] + [opt[0] for opt in options], key="location_select")
                if selected:
                    for name, lat, lon in options:
                        if name == selected:
                            st.session_state.location_name = name
                            st.session_state.lat = lat
                            st.session_state.lon = lon
                            st.success(f"Selected: {name}")
                            break
            else:
                st.warning("No results.")
        except:
            st.error("Search failed.")

# Fallback
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

# === SIMULATED POWER ===
def get_power():
    hour = datetime.now().hour
    return random.randint(850, 1200) if 11 <= hour <= 14 else random.randint(100, 500)

# === SIDEBAR ===
st.sidebar.header("Your Setup")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Geyser Use (hrs/day)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Cost (R/kWh)", 2.0, 6.0, 2.50)

# === CALCULATIONS (FIXED) ===
avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * days
used_kwh = system_size_kw * hours_used_per_day * days
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh
weekly_savings = saved_r / days

next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp(df.loc[best_hour, 'Time']).strftime("%I:%M %p")

# === GRAPH ===
fig = px.line(
    df, x='Time', y='Solar Yield (W/m²)',
    title=f"{days}-Day AI Solar Forecast",
    labels={'Solar Yield (W/m²)': 'Sunlight (W/m²)'}
)
fig.update_layout(height=450, hovermode='x unified', xaxis=dict(rangeselector=dict(buttons=[
    dict(count=1, label="1d", step="day"), dict(count=7, label="7d", step="day"), dict(step="all")
]), rangeslider=dict(visible=True), type="date"))
st.plotly_chart(fig, use_container_width=True)

if st.button("Simulate Geyser Control", type="primary", use_container_width=True):
    if get_power() > 800:
        st.success("GEYSER ON — 100% Solar!")
        st.success("SMS: Geyser ON — 2hr hot water (free!)")
    else:
        st.warning("Geyser OFF — Low sun")

# === METRICS ===
col1, col2 = st.columns(2)
with col1:
    st.metric("Best Charge Time", best_time)
    st.metric("Money Saved", f"R{saved_r:.0f}", f"R{weekly_savings:.0f}/week")
with col2:
    st.metric(f"{days}-Day Solar", f"{total_solar_kwh:.1f} kWh", f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Current Solar", f"{get_power()}W")

st.info(f"**AI says: Charge at {best_time} — Save R{saved_r:.0f} in {days} days!**")
st.caption("© 2025 SolarcallAI | info@solarcallai.co.za")
