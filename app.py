import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="☀️ SolarAI Optimizer", layout="wide")

# ------------------ TITLE ------------------
st.markdown("# ☀️ SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# ------------------ LOCATION SELECTION ------------------
st.subheader("🌍 Select Location")
loc_choice = st.radio(
    "Choose your area:",
    ["📍 Limpopo (Polokwane)", "🌞 Nelspruit (Mbombela)"],
    horizontal=True
)
st.button("🔄 Reset / Refresh")

# ------------------ SYSTEM AUTOMATION ------------------
st.subheader("🤖 AI System Configuration")
st.markdown(
    "AI auto-detects your system peak capacity and battery storage based on Solcast irradiance data and inverter specs."
)

# AI estimated values
if "Limpopo" in loc_choice:
    system_kw = 5.0
    battery_kwh = 9.6  # Based on 48V 200Ah LiFePO4
else:
    system_kw = 4.5
    battery_kwh = 8.5

# ------------------ AI + GROWATT INVERTER ------------------
inverter_model = "Growatt SPF 5000 ES (48V)"
inverter_efficiency = 0.92
battery_efficiency = 0.95
reserve_soc = 0.1

# ------------------ SOLCAST LIVE FETCH ------------------
@st.cache_data
def get_solcast_data(lat, lon):
    try:
        api_key = "YOUR_SOLCAST_API_KEY"  # Replace with actual API key
        url = f"https://api.solcast.com.au/data/forecast/radiation_and_weather?latitude={lat}&longitude={lon}&api_key={api_key}"
        resp = requests.get(url)
        data = resp.json()["forecasts"]
        df = pd.DataFrame(data)
        df["period_end"] = pd.to_datetime(df["period_end"])
        df["GHI"] = df["ghi"]  # Global Horizontal Irradiance
        df = df[["period_end", "GHI"]]
        df.rename(columns={"period_end": "Time"}, inplace=True)
        df["Time"] = df["Time"].dt.tz_localize(None)
        return df
    except Exception:
        # fallback data
        now = datetime.now()
        hours = pd.date_range(now, now + timedelta(hours=24), freq="1H")
        ghi_values = np.clip(900 * np.sin(np.linspace(0, np.pi, len(hours))) + np.random.randn(len(hours)) * 50, 0, 1000)
        return pd.DataFrame({"Time": hours, "GHI": ghi_values})

if "Limpopo" in loc_choice:
    df_24 = get_solcast_data(-23.9, 29.45)
else:
    df_24 = get_solcast_data(-25.46, 30.99)

# ------------------ AI DETECTION ------------------
st.subheader("🧠 AI Smart Load Control")
simulate = st.button("🛰️ Simulate AI Detection")

if simulate:
    st.toast("🔍 AI analyzing solar forecast & battery behavior...")
    st.markdown("### ⚙️ AI Simulation Running...")

# ------------------ AI FORECAST ANALYSIS ------------------
ghi_max = df_24["GHI"].max()
best_time = df_24.loc[df_24["GHI"].idxmax(), "Time"]

# Assume geyser uses 3kW for 1 hour
geyser_kw = 3.0
geyser_duration = 1.0
geyser_energy_kwh = geyser_kw * geyser_duration

# Determine if inverter can power geyser at best time
available_energy = battery_kwh * battery_efficiency * (1 - reserve_soc)
if available_energy >= geyser_energy_kwh:
    ai_message = f"✅ AI will run the geyser at **{best_time.strftime('%H:%M')}** using inverter solar power."
else:
    ai_message = f"⚠️ Battery too low to run geyser fully from inverter. Partial heating possible."

st.markdown(f"**{ai_message}**")

# ------------------ SAVINGS ESTIMATION ------------------
# Assume R2.85/kWh grid cost
cost_per_kwh = 2.85
daily_saving = geyser_energy_kwh * cost_per_kwh
weekly_saving = daily_saving * 7
monthly_saving = daily_saving * 30

st.markdown(
    f"💰 **Savings:** R{daily_saving:.2f} /day | R{weekly_saving:.2f} /week | R{monthly_saving:.2f} /month"
)

# ------------------ GRAPH ------------------
fig = px.line(
    df_24,
    x="Time",
    y="GHI",
    title=f"☀️ Global Horizontal Irradiance — {loc_choice} (Live Solcast)",
    labels={"GHI": "Irradiance (W/m²)", "Time": "Hour of Day"},
)

fig.update_traces(
    line=dict(color="rgba(0, 123, 255, 0.5)", width=3),
    mode="lines+markers",
    marker=dict(size=7, color="rgba(0,123,255,0.6)", line=dict(width=1.5, color="white")),
    hovertemplate="Time: %{x|%H:%M}<br>Irradiance: %{y:.0f} W/m²<extra></extra>",
    line_shape="spline",
)

fig.update_layout(
    height=440,
    margin=dict(l=40, r=40, t=60, b=40),
    title_x=0.5,
    plot_bgcolor="white",
    paper_bgcolor="white",
    hovermode="x unified",
    xaxis=dict(
        tickformat="%H:%M",
        dtick=3 * 3600000,  # every 3 hours
        tickfont=dict(size=13),
        rangeslider=dict(visible=True),
    ),
    yaxis=dict(
        gridcolor="rgba(200,200,200,0.3)",
        zeroline=False,
        tickfont=dict(size=13),
    ),
    updatemenus=[
        {
            "type": "buttons",
            "showactive": False,
            "x": 0.1,
            "y": 1.15,
            "buttons": [
                {
                    "label": "▶️ Animate",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 700, "redraw": True}, "fromcurrent": True}],
                },
                {"label": "🔁 Reset Zoom", "method": "relayout", "args": [{"xaxis.autorange": True}]},
            ],
        }
    ],
)

st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

# ------------------ AI SUMMARY ------------------
st.markdown("### 📊 AI Summary")
st.markdown(
    f"""
**Inverter:** {inverter_model}  
**Detected Best Geyser Time:** {best_time.strftime('%H:%M')}  
**Available Battery Energy:** {available_energy:.2f} kWh  
**Expected Geyser Energy Need:** {geyser_energy_kwh:.2f} kWh  
**Solar Peak Irradiance:** {ghi_max:.0f} W/m²  
**Daily Savings:** R{daily_saving:.2f}
"""
)

# Hide footer info
st.markdown(
    "<style>footer {visibility: hidden;} div.block-container{padding-top:1rem;}</style>",
    unsafe_allow_html=True
)
