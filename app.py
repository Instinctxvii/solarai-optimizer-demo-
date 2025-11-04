import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.express as px

# =====================================================
# APP CONFIG
# =====================================================
st.set_page_config(page_title="SolarAI Optimizer™", layout="centered")
st.title("☀️ SolarAI Optimizer™")
st.caption("AI-Powered Solar Scheduling for Growatt 5kW ES + 48 V Systems")

# =====================================================
# FORECAST GENERATOR
# =====================================================
def safe_forecast(location: str):
    """Simulates solar irradiance safely (always returns valid DataFrame)."""
    try:
        now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        hours = pd.date_range(now, periods=24, freq="H")

        # Basic simulated irradiance curve
        if location == "Limpopo (Polokwane)":
            ghi = [max(0, 900 * np.sin((i - 6) / 24 * np.pi)) for i in range(24)]
        else:
            ghi = [max(0, 950 * np.sin((i - 5) / 24 * np.pi)) for i in range(24)]

        df = pd.DataFrame({"Time": hours, "GHI": ghi})
        df["Power_kW"] = df["GHI"] * 5 / 1000  # assume 5 kW array
        return df
    except Exception as e:
        st.warning(f"⚠️ Forecast generation failed: {e}")
        now = datetime.datetime.now()
        return pd.DataFrame({
            "Time": [now + datetime.timedelta(hours=i) for i in range(24)],
            "GHI": [0]*24,
            "Power_kW": [0]*24
        })

# =====================================================
# CORE AI LOGIC
# =====================================================
def optimize_schedule(df: pd.DataFrame, allow_evening: bool):
    """Derives best geyser heating time & battery performance."""
    try:
        inverter_capacity_kwh = 9.6    # 48 V 200 Ah LiFePO4 ≈ 9.6 kWh
        geyser_kw = 3.0
        geyser_hours = 1.5
        baseline_kw = 0.6
        cooking_kw = 1.0
        fridge_kw = 0.25
        phone_kw = 0.1

        if df.empty or "Power_kW" not in df:
            raise ValueError("Invalid forecast data.")

        best_idx = df["Power_kW"].idxmax()
        best_time = df.loc[best_idx, "Time"]

        # Energy & battery logic
        geyser_energy = geyser_kw * geyser_hours
        usable_batt = inverter_capacity_kwh * 0.9
        batt_after = max(0, usable_batt - geyser_energy)

        recharge_needed = usable_batt - batt_after
        avg_solar = max(df["Power_kW"].mean(), 0.1)
        recharge_time = recharge_needed / avg_solar

        if allow_evening:
            batt_evening = min(usable_batt, batt_after + avg_solar * 2)
        else:
            batt_evening = batt_after

        evening_load = baseline_kw * 4 + cooking_kw + fridge_kw * 2 + phone_kw * 0.5
        backup_hrs = batt_evening / evening_load if evening_load > 0 else 0

        tariff = 2.85
        daily = geyser_energy * tariff
        weekly = daily * 7
        monthly = daily * 30

        return {
            "time": best_time.strftime("%H:%M"),
            "batt_after_pct": batt_after / usable_batt * 100,
            "recharge_time": recharge_time,
            "backup_hours": backup_hrs,
            "savings": (daily, weekly, monthly)
        }
    except Exception as e:
        st.error(f"AI optimization failed: {e}")
        return None

# =====================================================
# SIDEBAR CONTROLS
# =====================================================
with st.sidebar:
    st.header("⚙️ Settings")
    location = st.radio("Select Location", ["📍 Limpopo (Polokwane)", "🌞 Nelspruit (Mbombela)"])
    allow_evening = st.toggle("Allow Evening Recharge Cycle", value=True)
    st.caption("Disable to prevent inverter recharging from grid after sunset.")

# =====================================================
# MAIN EXECUTION
# =====================================================
st.subheader("🔆 Solar Forecast & Optimization")
with st.spinner("Calculating solar profile..."):
    df = safe_forecast(location)
    result = optimize_schedule(df, allow_evening)

if result:
    st.success(f"AI scheduled geyser heating at **{result['time']}** (max solar output).")
    st.info(f"🔋 Battery after heating: **{result['batt_after_pct']:.1f}%**")
    st.info(f"🔁 Recharge time (solar only): **{result['recharge_time']:.1f} hrs**")
    st.info(f"💡 Backup runtime available: **{result['backup_hours']:.1f} hrs**")
    st.success(
        f"💰 Savings — Daily: R{result['savings'][0]:.2f} | "
        f"Weekly: R{result['savings'][1]:.2f} | Monthly: R{result['savings'][2]:.2f}"
    )
else:
    st.error("No optimization data available. Please check your configuration.")

# =====================================================
# GRAPH OUTPUT
# =====================================================
if not df.empty:
    try:
        fig = px.line(
            df, x="Time", y="Power_kW",
            title=f"☀️ Solar Power Forecast — {location}",
            labels={"Power_kW": "Estimated PV Output (kW)"}
        )
        fig.update_traces(mode="lines+markers")
        fig.update_layout(template="plotly_dark", xaxis_title="Time", yaxis_title="Power (kW)")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render chart: {e}")
else:
    st.warning("No forecast data to plot.")

st.caption("SolarAI Optimizer™ | Reliable Off-Grid Scheduling — © 2025")
