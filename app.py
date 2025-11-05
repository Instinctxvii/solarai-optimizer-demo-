import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time

# === REFRESH BUTTON ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    st.rerun()

st.title("SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# === LOCATION BUTTON ===
st.markdown("### Select Location")
col_loc1, col_loc2 = st.columns(2)
if col_loc1.button("Limpopo (Polokwane)", type="secondary", use_container_width=True):
    st.session_state.location = "limpopo"
if col_loc2.button("Nelspruit (Mpumalanga)", type="secondary", use_container_width=True):
    st.session_state.location = "nelspruit"

if 'location' not in st.session_state:
    st.session_state.location = "limpopo"

locations = {
    "limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
    "nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694}
}
loc = locations[st.session_state.location]
st.markdown(f"**Current Location: {loc['name']}**")

# === SIMULATED SOLAR FORECAST (No RPi.GPIO) ===
@st.cache_data(ttl=3600)
def get_solar_forecast(lat, lon):
    # Fake realistic data (replace with Solcast later)
    now = datetime.now()
    index = pd.date_range(now, periods=336, freq='h')
    hours = index.hour
    seasonal = 1.2 if now.month in [11,12,1,2] else 0.8
    ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 50, len(index)))
    return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})

df = get_solar_forecast(loc['lat'], loc['lon'])

# === SIMULATED SOLAR POWER (No INA219) ===
def get_solar_power():
    # Fake 800W+ during peak hours
    hour = datetime.now().hour
    if 11 <= hour <= 14:
        return random.randint(850, 1200)
    else:
        return random.randint(100, 500)

# === SIMULATED SMS (No Clickatell) ===
def send_sms(message):
    st.success(f"📱 SMS SENT: {message}")
    print(message)

# === SIMULATED RELAY (No GPIO) ===
def control_geyser(power, forecast_ok):
    if power > 800 and forecast_ok:
        st.success("🔌 GEYSER ON — Solar only!")
        send_sms("Geyser ON — 2hr hot water (Solar only)")
    else:
        st.warning("🔌 Geyser OFF — Low sun")

# Sidebar
st.sidebar.header("Your Solar System")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Daily Usage (hours)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.50)

# kWh & Savings
avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * 14
used_kwh = system_size_kw * hours_used_per_day * 14
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh

# Best charge time
next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp
