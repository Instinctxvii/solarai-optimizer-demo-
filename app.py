import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# === LOCATION BUTTON AT TOP ===
st.markdown("### Select Location")
col_loc1, col_loc2 = st.columns(2)
with col_loc1:
    if st.button("Limpopo (Polokwane)", type="secondary", use_container_width=True):
        st.session_state.location = "limpopo"
with col_loc2:
    if st.button("Nelspruit (Mpumalanga)", type="secondary", use_container_width=True):
        st.session_state.location = "nelspruit"

# Default location
if 'location' not in st.session_state:
    st.session_state.location = "limpopo"

# === REFRESH BUTTON ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    st.rerun()

st.title("SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# Location Coordinates (Real)
locations = {
    "limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
    "nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694}
}
loc = locations[st.session_state.location]

st.markdown(f"**Current Location: {loc['name']}**")

# Real Solcast API (free satellite data)
@st.cache_data(ttl=3600)
def get_solcast_forecast(lat, lon, api_key='demo'):
    if api_key == 'demo':
        now = datetime.now()
        index = pd.date_range(now, periods=336, freq='h')
        hours = index.hour
        seasonal = 1.2 if now.month in [11,12,1,2] else 0.8
        ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 50, len(index)))
        return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})
    
    url = f"https://api.solcast.com.au/radiation/forecasts?latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()['forecasts']
            df = pd.DataFrame(data)
            df['Time'] = pd.to_datetime(df['period_end'])
            df['Solar Yield (W/m²)'] = df['ghi']
            return df[['Time', 'Solar Yield (W/m²)']].tail(336)
    except Exception as e:
        st.error(f"API Error: {e}. Using demo data.")
    
    # Fallback
    now = datetime.now()
    index = pd.date_range(now, periods=336, freq='h')
    hours = index.hour
    seasonal = 1.2 if now.month in [11,12,1,2] else 0.8
    ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 50, len(index)))
    return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})

# Sidebar Inputs
st.sidebar.header("Your Solar System")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Daily Usage (hours)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.50)
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")

df = get_solcast_forecast(loc['lat'], loc['lon'], api_key=solcast_key)

# kWh & Savings (Accurate SA Model)
avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5  # 5 peak sun hours/day
total_solar_kwh = daily_solar_kwh * 14
used_kwh = system_size_kw * hours_used_per_day * 14
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh

# Best charge time
next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp(df.loc[best_hour, 'Time']).strftime("%I:%M %p")

# Graph reset
if 'graph_relayout' not in st.session_state:
    st.session_state.graph_relayout = None

# Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("14
