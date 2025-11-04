This is my python code please cut my the solar yield graph from 14 to 7 days, add a drop down menu allowing me the view specific days and the solar yield time E.g I choose to view today only, I should be able to see the solar yield for 24hrs

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

=== LOCATION BUTTON AT TOP ===

st.markdown("### Select Location")
col_loc1, col_loc2 = st.columns(2)
with col_loc1:
if st.button("Limpopo (Polokwane)", type="secondary", use_container_width=True):
st.session_state.location = "limpopo"
with col_loc2:
if st.button("Nelspruit (Mpumalanga)", type="secondary", use_container_width=True):
st.session_state.location = "nelspruit"

Default location

if 'location' not in st.session_state:
st.session_state.location = "limpopo"

=== REFRESH DEMO BUTTON ===

if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
st.success("Refreshing... Page will reload in 2 seconds.")
st.rerun()

st.title("SolarAI Optimizer™")
st.markdown("AI-Powered Solar Intelligence | R99/month")

Location Coordinates

locations = {
"limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
"nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694}
}
loc = locations[st.session_state.location]
st.markdown(f"Current Location: {loc['name']}")

Solcast API

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
  
now = datetime.now()  
index = pd.date_range(now, periods=336, freq='h')  
hours = index.hour  
seasonal = 1.2 if now.month in [11,12,1,2] else 0.8  
ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 50, len(index)))  
return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})

Sidebar

st.sidebar.header("Your Solar System")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Daily Usage (hours)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.50)
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")

df = get_solcast_forecast(loc['lat'], loc['lon'], api_key=solcast_key)

kWh & Savings

avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * 14
used_kwh = system_size_kw * hours_used_per_day * 14
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh

Best charge time

next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp(df.loc[best_hour, 'Time']).strftime("%I:%M %p")

=== FORCE RESET ON BUTTON PRESS ===

if st.button("Reset Graph View", type="secondary"):
# Clear any saved layout
if 'graph_relayout' in st.session_state:
del st.session_state.graph_relayout
st.success("Graph reset to full 14-day view!")
st.rerun()  # Full refresh

=== BUILD FRESH GRAPH (NO INTERACTION) ===

fig = px.line(df, x='Time', y='Solar Yield (W/m²)',
title=f"GHI — {loc['name']} (Free Satellite Data)",
labels={'ghi': 'Yield (W/m²)', 'Time': 'Date & Time'})
fig.update_layout(
height=400,
margin=dict(l=40, r=40, t=80, b=40),
title_x=0.5,
title_font_size=16,
hovermode=False,
dragmode=False,
xaxis=dict(fixedrange=True),  # Lock X-axis
yaxis=dict(fixedrange=True)   # Lock Y-axis
)

=== NON-INTERACTABLE CONFIG ===

config = {
'staticPlot': True,
'displayModeBar': False,
'displaylogo': False
}

Layout

col1, col2 = st.columns([2, 1])

with col1:
st.subheader("14-Day Solar Yield Forecast")
st.plotly_chart(fig, use_container_width=True, config=config, key="solar_chart")

# EXPLANATION  
st.markdown("""

What is Solar Yield?
→ Solar Yield (W/m²) = How much sunlight hits your panel right now.
→ Higher number = more power (e.g., 800 W/m² = full sun).
→ 0 at night = no power.

How to read the graph:

1. X-axis (bottom) = Date & Time (next 14 days)


2. Y-axis (left) = Sunlight strength (0 to 1000 W/m²)


3. Blue line = AI’s forecast using free satellite data


4. Peaks at 12 PM = best time to charge geyser/battery



Example: At 12:15 PM on Nov 10, yield = 950 W/m² → perfect time to turn on geyser!
""")

with col2:
st.subheader("Live AI Insights")
st.metric("Best Time to Charge", best_time)
st.metric("14-Day Solar", f"{total_solar_kwh:.1f} kWh", delta=f"{daily_solar_kwh:.1f} kWh/day")
st.metric("Money Saved", f"R{saved_r:.0f}", delta=f"R{saved_r/14:.0f}/week")

if st.button("Simulate Charge Now", type="primary"):  
    st.success(f"Geyser ON at {best_time} in {loc['name']}! Saved R{saved_r:.0f} (real data).")

st.info(f"AI says: Charge at {best_time} in {loc['name']} for {daily_solar_kwh:.1f} kWh free power!")
st.caption("R1,200 Raspberry Pi + AI | R99/month | Contact: [Keanu.kruger05@gmail.com]")
