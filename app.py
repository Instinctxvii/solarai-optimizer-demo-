import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# === REFRESH BUTTON AT TOP ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    st.rerun()

st.title("⚡ SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | Soweto Demo | R99/month**")

# Generate demo solar data (14 days hourly)
def generate_solar_data():
    now = datetime.now()
    index = pd.date_range(now, periods=336, freq='H')  # 14 days
    hours = index.hour
    seasonal = 1.2 if now.month in [11,12,1,2] else 0.8  # SA summer
    ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 50, len(index)))
    return pd.DataFrame({'ghi': ghi}, index=index).resample('H').mean()

# Session state for graph reset
if 'graph_relayout' not in st.session_state:
    st.session_state.graph_relayout = None

df = generate_solar_data().reset_index()
df.columns = ['Time', 'Solar Yield (W/m²)']

# Best charge time
next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp(df.loc[best_hour, 'Time']).strftime("%I:%M %p")

# Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("14-Day Solar Yield Forecast")
    
    fig = px.line(df, x='Time', y='Solar Yield (W/m²)', 
                  title="Global Horizontal Irradiance (W/m²)",
                  labels={'ghi': 'Yield (W/m²)', 'Time': 'Date & Time'})
    fig.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=40))
    
    config = {
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'zoomIn', 'zoomOut', 'autoScale'],
        'displaylogo': False
    }
    
    if st.session_state.graph_relayout:
        fig.update_layout(st.session_state.graph_relayout)

    st.plotly_chart(fig, use_container_width=True, config=config, key="solar_chart")

    # Reset Graph Button
    if st.button("Reset Graph View", type="secondary"):
        st.session_state.graph_relayout = None
        st.success("Graph reset to full 14-day view!")
        st.rerun()

    # HIGH SCHOOL EXPLANATION
    st.markdown("""
    ### **How to Use This Demo (Easy as 1-2-3!)**

    1. **Look at the graph**
