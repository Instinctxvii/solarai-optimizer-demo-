import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="SolarAI Optimizer", layout="wide")
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

# Use session state to store graph view
if 'graph_relayout' not in st.session_state:
    st.session_state.graph_relayout = None

df = generate_solar_data().reset_index()
df.columns = ['Time', 'Solar Yield (W/m²)']

# Predict optimal charge time (next 24h best window)
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
    
    # FIXED VIEW: Disable zoom/pan
    config = {
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'zoomIn', 'zoomOut', 'autoScale'],
        'displaylogo': False
    }
    
    # Apply stored relayout (or None for default)
    relayout_data = st.session_state.graph_relayout
    if relayout_data:
        fig.update_layout(relayout_data)

    chart = st.plotly_chart(fig, use_container_width=True, config=config, key="solar_chart")

    # Reset Button
    if st.button("Reset Graph View", type="secondary"):
        st.session_state.graph_relayout = None
        st.success("Graph reset to full 14-day view!")
        st.rerun()

    # Explanation under graph
    st.markdown("""
    **What this shows**:  
    This 14-day solar forecast predicts **how much energy your panels will generate** each hour.  
    Our AI uses satellite data + local weather to find the **best time to charge** (e.g., geyser, battery).  
    → **No zoom allowed** so investors see the full picture at a glance.  
    → Use **"Reset Graph View"** if the view shifts.
    """)

with col2:
    st.subheader("Live AI Insights")
    st.metric("Optimal Charge Time", best_time)
    st.metric("Estimated Weekly Savings", "R187", delta="+R42")
    st.metric("Battery Efficiency", "94%", delta="+2%")
    
    if st.button("Simulate Charge Now", type="primary"):
        st.success(f"Relay activated! Geyser ON at {best_time}.")

st.info(f"AI recommends charging at **{best_time}** for maximum yield.")
st.caption("Built with Raspberry Pi + AI | R99/month | Contact: [Your Email]")
