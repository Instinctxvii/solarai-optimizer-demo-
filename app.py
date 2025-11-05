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

# Auto-detect button
col_auto, col_search = st.columns([1, 3])
with col_auto:
    if st.button("Use My Location", type="secondary", use_container_width=True):
        st.write("Detecting GPS...")
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
                }
            );
        } else {
            window.parent.postMessage({error: "Geolocation not supported"}, "*");
        }
        </script>
        """
        st.components.v1.html(location_js, height=0)

# Capture GPS from URL
query_params = st.experimental_get_query_params()
if "lat" in query_params and "lon" in query_params:
    lat = float(query_params["lat"][0])
    lon = float(query_params["lon"][0])
    try:
        response = requests.get(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json")
        data = response.json()
        address = data.get("address", {})
        suburb = address.get("suburb", address.get("neighbourhood", address.get("village", "")))
        city = address.get("city", address.get("town", ""))
        province = address.get("province", address.get("state", ""))
        location_name = f"{suburb or city}, {city or province}, {province or 'South Africa'}".strip(", ")
        st.session_state.location_name = location_name
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.success(f"Location found: {location_name}")
        st.experimental_set_query_params()  # Clear URL
    except:
        st.error("Could not detect location.")

# Search box
with col_search:
    search_query = st.text_input(
        "Or search suburb (e.g., Kimberley, Soweto, Valencia Park)",
        placeholder="Type your suburb...",
        key="search_input"
    )

# Handle search
if search_query and len(search_query) > 2:
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": search_query,
                "format": "json",
                "limit": 5,
                "countrycodes": "za",
                "addressdetails": 1
            },
            headers={"User-Agent": "SolarcallAI/1.0"}
        )
        results = response.json()
        if results:
            options = []
            for r in results:
                addr = r.get("address", {})
                suburb = addr.get("suburb", addr.get("neighbourhood", addr.get("village", "")))
                city = addr.get("city", addr.get("town", ""))
                province = addr.get("province", addr.get("state", ""))
                name = f"{suburb or city}, {city or province}, {province or 'South Africa'}".strip(", ")
                options.append((name, float(r["lat"]), float(r["lon"])))
            selected = st.selectbox("Select location:", [opt[0] for opt in options], key="location_select")
            for name, lat, lon in options:
                if name == selected:
                    st.session_state.location_name = name
                    st.session_state.lat = lat
                    st.session_state.lon = lon
                    st.success(f"Selected: {name}")
                    st.rerun()
                    break
        else:
            st.warning("No SA locations found. Try 'Kimberley' or 'Soweto'.")
    except:
        st.error("Search failed. Check internet.")

# Fallback
if 'location_name' not in st.session_state:
    st.session_state.location_name = "Limpopo (Polokwane)"
    st.session_state.lat = -23.8962
    st.session_state.lon = 29.4486

st.markdown(f"**Current Location: {st.session_state.location_name}**")

# === REAL SOLAR FORECAST ===
@st.cache_data(ttl=3600)
def get_real_solar_forecast(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "direct_normal_irradiance",
        "forecast_days": 14,
        "timezone": "Africa/Johannesburg"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        df = pd.DataFrame({
            "Time": pd.to_datetime(data["hourly"]["time"]),
            "Solar Yield (W/m²)": data["hourly"]["direct_normal_irradiance"]
        })
        return df
    except:
        now = datetime.now()
        index = pd.date_range(now, periods=336, freq='h')
        hours = index.hour
        ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) + np.random.normal(0, 50, len(index)))
        return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})

df = get_real_solar_forecast(st.session_state.lat, st.session_state.lon)

# === SIMULATED CURRENT POWER ===
def get_current_power():
    hour = datetime.now().hour
    if 11 <= hour <= 14:
        return random.randint(850, 1200)
    else:
        return random.randint(100, 500)

# === SIMULATED SMS ===
def send_sms(message):
    st.success(f"SMS SENT: {message}")

# === SIMULATED RELAY CONTROL ===
def control_geyser():
    power = get_current_power()
    if power > 800:
        st.success("GEYSER ON — 100% Solar Power!")
        send_sms("Geyser ON — 2hr hot water (Solar only)")
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
total_solar_kwh = daily_solar_kwh * 14
used_kwh = system_size_kw * hours_used_per_day * 14
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh
weekly_savings = saved_r / 14

next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp(df.loc[best_hour, 'Time']).strftime("%I:%M %p")

# === MAIN LAYOUT ===
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("14-Day Solar Yield Forecast")
    fig = px.line(df, x='Time', y='Solar Yield (W/m²)', 
                  title=f"AI Forecast — {st.session_state.location_name}",
                  labels={'Solar Yield (W/m²)': 'Sunlight (W/m²)'})
    fig.update_layout(height=400, title_x=0.5)
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Simulate Geyser Control", type="primary", use_container_width=True):
        control_geyser()

    st.markdown("""
**How to Read:**
1. **X-axis** = Next 14 days
2. **Y-axis** = Real sunlight
3. **Peak at 12 PM** = Best time
4. **AI activates > 800W**
""")

with col2:
    st.subheader("Live AI Insights")
    st.metric("Best Charge Time", best_time)
    st.metric("14-Day Solar", f"{total_solar_kwh:.1f} kWh", f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Money Saved", f"R{saved_r:.0f}", f"R{weekly_savings:.0f}/week")
    st.metric("Current Solar", f"{get_current_power()}W", "Peak Sun")

st.info(f"AI says: **Charge at {best_time}** in **{st.session_state.location_name}** — Save R{saved_r:.0f} in 14 days!")

st.caption("© 2025 SolarcallAI (Pty) Ltd | info@solarcallai.co.za | Powered by Open-Meteo")
