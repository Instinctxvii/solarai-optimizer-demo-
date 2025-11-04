import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.express as px
import random

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(page_title="SolarAI Optimizer™", layout="centered")
st.title("☀️ SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence — Growatt 5kW ES + 48V System**")

# =====================================================
# SIMULATED SOLCAST FORECAST
# =====================================================
def get_solar_forecast(location: str):
    """Simulate solar irradiance curve for 24 hours."""
    hours = pd.date_range(
        datetime.datetime.now().replace(minute=0, second=0, microsecond=0),
        periods=24,
        freq="H"
    )
    if location == "Limpopo (Polokwane)":
        ghi = [max(0, 950 * np.sin((i - 6) / 24 * np.pi)) for i in range(24)]
    else:
        ghi = [max(0, 980 * np.sin((i - 5) / 24 * np.pi)) for i in range(24)]
    df = pd.DataFrame({"Time": hours, "GHI": ghi})
    df["Power_kW"] = df["GHI"] * 5 / 1000  # 5 kW panels assumed
    return df

# =====================================================
# CORE AI LOGIC
# =====================================================
def solar_ai_optimize(df, allow_evening_charge=True):
    inverter_capacity_kwh = 9.6  # Growatt 5kW ES 48V (200Ah LiFePO4)
    geyser_power_kw = 3.0
    geyser_duration_hr = 1.5
    baseline_load_kw = 0.6
    cooking_kw = 1.0
    fridge_kw = 0.25
    phone_kw = 0.1

    # Find the best sunlight window for geyser operation
    df["Power_kW"] = df["Power_kW"].clip(lower=0)
    if df.empty or "Power_kW" not in df:
        return None

    best_idx = df["Power_kW"].idxmax()
    best_time = df.loc[best_idx, "Time"]

    # Energy calculations
    geyser_energy = geyser_power_kw * geyser_duration_hr  # kWh
    usable_batt_kwh = inverter_capacity_kwh * 0.9
    batt_after_geyser = max(0, usable_batt_kwh - geyser_energy)
    recharge_needed = usable_batt_kwh - batt_after_geyser
    recharge_time_hr = recharge_needed / max(df["Power_kW"].mean(), 0.1)

    # If evening charging is allowed, recharge extra
    evening_batt = batt_after_geyser
    if allow_evening_charge:
        evening_batt = min(usable_batt_kwh, batt_after_geyser + df["Power_kW"].mean() * 2)

    # Evening load simulation
    evening_load = baseline_load_kw * 4 + cooking_kw * 1 + fridge_kw * 2 + phone_kw * 0.5
    backup_hours = evening_batt / evening_load if evening_load > 0 else 0

    # Cost savings (assume R2.85/kWh)
    daily_savings = geyser_energy * 2.85
    weekly_savings = daily_savings * 7
    monthly_savings = daily_savings * 30

    return {
        "best_time": best_time.strftime("%H:%M"),
        "batt_after": batt_after_geyser / usable_batt_kwh * 100,
        "recharge_time": recharge_time_hr,
        "backup_hours": backup_hours,
        "savings": (daily_savings, weekly_savings, monthly_savings)
    }

# =====================================================
# SIDEBAR CONFIG
# =====================================================
with st.sidebar:
    st.header("🌍 Select Location")
    location = st.radio("Choose your area:", ["📍 Limpopo (Polokwane)", "🌞 Nelspruit (Mbombela)"])
    allow_evening_charge = st.toggle("Allow Evening Recharge Cycle", value=True)
    st.caption("If disabled, inverter will *not* recharge at night using grid.")

# =====================================================
# MAIN APP BODY
# =====================================================
df = get_solar_forecast(location)
result = solar_ai_optimize(df, allow_evening_charge=allow_evening_charge)

if result is None:
    st.error("No valid forecast data found. Please try again.")
else:
    # Display results
    st.subheader("🤖 AI Detection Summary")
    if st.button("📡 Simulate AI Detection"):
        st.success(f"✅ AI scheduled the geyser at **{result['best_time']}** using **solar inverter power**.")
        st.info(f"🔋 Inverter battery after heating: **{result['batt_after']:.1f}%** capacity remaining.")
        st.info(f"🔁 Recharge time: **{result['recharge_time']:.1f} hrs** "
                f"({'evening charge ON' if allow_evening_charge else 'evening charge OFF'})")
        st.info(f"💡 Backup runtime available: **{result['backup_hours']:.1f} hrs** during outage.")
        st.success(f"💰 Savings: R{result['savings'][0]:.2f}/day | "
                   f"R{result['savings'][1]:.2f}/week | R{result['savings'][2]:.2f}/month")

# =====================================================
# GRAPH
# =====================================================
if not df.empty:
    fig = px.line(df, x="Time", y="GHI", title=f"☀️ Global Horizontal Irradiance — {location}",
                  labels={"GHI": "Solar Irradiance (W/m²)"})
    fig.update_traces(mode="lines+markers")
    fig.update_layout(template="plotly_dark", xaxis_title="Hour", yaxis_title="Irradiance (W/m²)")
    st.plotly_chart(fig, use_container_width=True)

st.caption("SolarAI Optimizer™ | Smart Solar Management — 2025 ©")
