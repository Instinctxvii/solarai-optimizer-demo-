import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.express as px
import requests
import random

# ==============================
# App Config
# ==============================
st.set_page_config(page_title="SolarAI Optimizer™", layout="centered")
st.title("☀️ SolarAI Optimizer™")
st.markdown("**AI-Powered Smart Solar Control — Growatt 5kW ES + 48V System**")

# ==============================
# Simulated Locations & GHI
# ==============================
def get_solcast_forecast(location: str):
    """Simulated real Solcast data (replace with your API if available)."""
    hours = pd.date_range(datetime.datetime.now().replace(minute=0, second=0, microsecond=0),
                          periods=24, freq="H")
    if location == "Limpopo (Polokwane)":
        base_ghi = [max(0, 900 * np.sin((i-6)/24*np.pi)) for i in range(24)]
    else:
        base_ghi = [max(0, 950 * np.sin((i-5)/24*np.pi)) for i in range(24)]
    df = pd.DataFrame({"Time": hours, "GHI": base_ghi})
    return df

# ==============================
# Core Simulation Logic
# ==============================
def simulate_ai_decision(df, inverter_capacity_kwh=9.6, geyser_power_kw=3.0, geyser_duration_hr=1.5,
                         baseline_load_kw=0.6, cooking_kw=1.0, fridge_kw=0.25, phone_kw=0.1,
                         allow_evening_charge=True):

    df["Power_kW"] = df["GHI"] * 5 / 1000  # 5kW panel max
    best_idx = df["Power_kW"].idxmax()
    best_time = df.loc[best_idx, "Time"]

    geyser_energy = geyser_power_kw * geyser_duration_hr
    usable_batt_kwh = inverter_capacity_kwh * 0.9  # 90% usable

    batt_after_geyser = max(0, usable_batt_kwh - geyser_energy)
    recharge_needed = usable_batt_kwh - batt_after_geyser
    recharge_time_hr = recharge_needed / max(df["Power_kW"].mean(), 0.1)

    evening_batt = batt_after_geyser
    if allow_evening_charge:
        evening_batt = min(usable_batt_kwh, batt_after_geyser + df["Power_kW"].mean() * 2)

    total_evening_load = baseline_load_kw * 4 + cooking_kw * 1 + fridge_kw * 2 + phone_kw * 0.5
    backup_hours = evening_batt / total_evening_load if total_evening_load > 0 else 0

    daily_savings = geyser_energy * 2.85  # R2.85/kWh
    weekly_savings = daily_savings * 7
    monthly_savings = daily_savings * 30

    return {
        "time": best_time.strftime("%H:%M"),
        "batt_after": batt_after_geyser / usable_batt_kwh * 100,
        "recharge_time": recharge_time_hr,
        "backup_hrs": backup_hours,
        "savings": (daily_savings, weekly_savings, monthly_savings)
    }

# ==============================
# Sidebar + Inputs
# ==============================
with st.sidebar:
    st.header("🌍 Select Location")
    loc_choice = st.radio("Choose your area:", ["📍 Limpopo (Polokwane)", "🌞 Nelspruit (Mbombela)"])
    allow_evening_charge = st.toggle("Allow Evening Recharge Cycle", value=True)
    st.caption("If off, inverter will not charge at night even if grid is available.")

# ==============================
# AI Simulation
# ==============================
df = get_solcast_forecast(loc_choice)
result = simulate_ai_decision(df, allow_evening_charge=allow_evening_charge)

# ==============================
# UI Display
# ==============================
st.markdown("### 🤖 AI Detection Results")
st.button("📡 Simulate AI Detection", help="Run the AI optimizer to schedule geyser and inverter use.")

st.success(f"✅ AI will run the geyser at **{result['time']}** using **solar inverter power** only.")
st.info(f"🔋 Battery after heating: **{result['batt_after']:.1f}%** capacity remaining.")
st.info(f"🔁 Estimated solar recharge time: **{result['recharge_time']:.1f} hours** "
        f"({'evening recharge enabled' if allow_evening_charge else 'no evening recharge'})")
st.info(f"💡 Expected backup power available: **{result['backup_hrs']:.1f} hours** during outage.")
st.success(f"💰 Savings: R{result['savings'][0]:.2f}/day | R{result['savings'][1]:.2f}/week | R{result['savings'][2]:.2f}/month")

# ==============================
# Plot: Real-time Solcast (Simulated)
# ==============================
fig = px.line(df, x="Time", y="GHI", title=f"☀️ Global Horizontal Irradiance — {loc_choice}",
              labels={"GHI": "Solar Irradiance (W/m²)"})
fig.update_traces(mode="markers+lines")
fig.update_layout(template="plotly_dark", xaxis_title="Hour of Day", yaxis_title="Irradiance (W/m²)")
st.plotly_chart(fig, use_container_width=True)

# Footer
st.caption("SolarAI Optimizer™ — Smart Solar Management, 2025 ©")
