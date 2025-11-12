import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
import random

# === CONFIG ===
st.set_page_config(page_title="SolarcallAI™", layout="wide")

# === REFRESH BUTTON ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    time.sleep(2)
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

# === GPS (NO LOOP) ===
if st.session_state.get("gps_active", False):
    status_placeholder = st.empty()
    status_placeholder.markdown("**Detecting GPS...**")

    # JS for GPS (no rerun inside)
    location_js = """
    <script>
    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                const url = window.location.href.split('?')[0] + '?lat=' + lat + '&lon=' + lon;
                window.location.href = url;
            },
            function(error) {
                window.parent.postMessage({error: error.message}, "*");
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 30000 }
        );
    } else {
        window.parent.postMessage({error: "Geolocation not supported"}, "*");
    }
    </script>
    """
    st.components.v1.html(location_js, height=0)

    # Capture (no loop)
    query_params = st.experimental_get_query_params()
    if "lat" in query_params and "lon" in query_params:
        lat = float(query_params["lat"][0])
        lon = float(query_params["lon"][0])
        try:
            response = requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", timeout=5)
            data = response.json()
            addr = data.get("address", {})
            suburb = addr.get("suburb", addr.get("neighbourhood", addr.get("village", addr.get("hamlet", ""))))
            city = addr.get("city", addr.get("town", ""))
            province = addr.get("province", addr.get("state", ""))
            location_name = f"{suburb or city}, {city or province}, {province or 'South Africa'}".strip(", ")
            st.session_state.location_name = location_name
            st.session_state.lat = lat
            st.session_state.lon = lon
            status_placeholder.success(f"**Detected: {location_name}**")
            st.experimental_set_query_params()
            st.session_state.gps_active = False
        except:
            status_placeholder.error("Could not resolve location.")
            st.experimental_set_query_params()
            st.session_state.gps_active = False
    elif "error" in st.session_state:
        status_placeholder.error(f"GPS Error: {st.session_state.error}")
        st.session_state.gps_active = False

# === SEARCH BOX ===
with col_search:
    search_query = st.text_input(
        "Or search suburb (e.g., Nelspruit, Soweto, Kimberley)",
        placeholder="Type suburb name...",
        key="search_input"
    )

if search_query and len(search_query) > 2:
    with st.spinner("Searching..."):
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": search_query, "format": "json", "limit": 5, "countrycodes": "za", "addressdetails": 1},
                headers={"User-Agent": "SolarcallAI/1.0"},
                timeout=5
            )
            results = response.json()
            if results:
                options = []
                for r in results:
                    addr = r.get("address", {})
                    suburb = addr.get("suburb", addr.get("neighbourhood", addr.get("village", addr.get("hamlet", ""))))
                    city = addr.get("city", addr.get("town", ""))
                    province = addr.get("province", addr.get("state", ""))
                    name = f"{suburb or city}, {city or province}, {province or 'South Africa'}".strip(", ")
                    options.append((name, float(r["lat"]), float(r["lon"])))
                selected = st.selectbox("Select location:", [""] + [opt[0] for opt in options], key="location_select")
                if selected:
                    for name, lat, lon in options:
                        if name == selected:
                            st.session_state.location_name = name
                            st.session_state.lat = lat
                            st.session_state.lon = lon
                            st.success(f"Selected: {name}")
                            break
            else:
                st.warning("No SA locations found.")
        except:
            st.error("Search failed. Check connection.")

# Fallback
if 'location_name' not in st.session_state:
    st.session_state.location_name = "Limpopo (Polokwane)"
    st.session_state.lat = -23.8962
    st.session_state.lon = 29.4486

st.markdown(f"**Current Location: {st.session_state.location_name}**")

# === FORECAST RANGE & RESET ===
col_range, col_reset = st.columns([1, 1])
with col_range:
    days = st.radio("Forecast Range", [7, 14], horizontal=True, index=1)
with col_reset:
    if st.button("Reset Graph View", type="secondary"):
        st.success("Graph reset!")
        st.rerun()

# === REAL SOLAR FORECAST ===
@st.cache_data(ttl=3600)
def get_real_solar_forecast(lat, lon, days=14):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "direct_normal_irradiance",
        "forecast_days": days,
        "timezone": "Africa/Johannesburg"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
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

df = get_real_solar_forecast(st.session_state.lat, st.session_state.lon, days=days)

# === SIMULATED POWER ===
def get_current_power():
    hour = datetime.now().hour
    return random.randint(850, 1200) if 11 <= hour <= 14 else random.randint(100, 500)

# === CONTROL ===
def control_geyser():
    power = get_current_power()
    if power > 800:
        st.success("GEYSER ON — 100% Solar Power!")
        st.success("SMS SENT: Geyser ON — 2hr hot water (free!)")
    else:
        st.warning("Geyser OFF — Low sun")

# === SIDEBAR ===
st.sidebar.header("Your Solar Setup")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Geyser Usage (hours/day)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.50)

# === CALCULATIONS ===
avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * days
used_kwh = system_size_kw * hours_used_per_day * days
saved_kwh
