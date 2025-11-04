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

if 'location' not in st.session_state:
    st.session_state.location = "limpopo"

# === REFRESH BUTTON ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    st.rerun()

st.title("SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# === LOCATION COORDINATES ===
locations = {
    "limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
    "nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694}
}
loc = locations[st.session_state.location]
st.markdown(f"**Current Location: {loc['name']}**")

# === FETCH DATA (REAL OR DEMO) ===
@st.cache_data(ttl=3600)
def get_solcast_forecast(lat, lon, api_key='demo'):
    """Simulated or real Solcast 14-day hourly forecast."""
    if api_key == 'demo':
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        index = pd.date_range(now - timedelta(days=1), periods=336, freq='h')  # includes yesterday + today + future
        hours = index.hour
        seasonal = 1.2 if now.month in [11,12,1,2] else 0.8
        ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 40, len(index)))
        return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})
    
    try:
        url = f"https://api.solcast.com.au/radiation/forecasts?latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()['forecasts']
            df = pd.DataFrame(data)
            df['Time'] = pd.to_datetime(df['period_end'])
            df['Solar Yield (W/m²)'] = df['ghi']
            return df[['Time', 'Solar Yield (W/m²)']].tail(336)
    except Exception as e:
        st.error(f"API Error: {e}. Using demo data.")
    
    # fallback
    now = datetime.now()
    index = pd.date_range(now, periods=336, freq='h')
    ghi = np.maximum(0, 800 * np.sin((index.hour -
