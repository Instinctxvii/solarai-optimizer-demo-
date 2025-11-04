# SolarAI Optimizer™ — AI finds the absolute next best solar time to run geyser using Growatt 5kW ES inverter
# Updated with bug fixes (Plotly import) + clean visuals + no grid usage
# Copy this file as app.py and run: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px  # ✅ FIXED: added missing import
from datetime import datetime, timedelta, time as dtime

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="SolarAI Optimizer™", layout="wide")
st.title("☀️ SolarAI Optimizer™")
st.markdown("**AI-smart geyser scheduling to avoid grid usage (Growatt 5kW ES class inverter).**")

# -------------------------
# USER INPUTS (simple)
# -------------------------
st.markdown("### ⚙️ Quick Home Setup")

c1, c2, c3 = st.columns(3)
household_size = c1.selectbox("Household size", [1, 2, 3, 4, 5, 6], index=2)
has_geyser = c2.checkbox("Electric geyser?", value=True)
cook_electric = c3.checkbox("Electric cooking?", value=False)

c4, c5 = st.columns(2)
panel_kw = c4.slider("Solar system peak (kW)", min_value=1.0, max_value=10.0, value=5.0, step=0.5)
battery_kwh = c5.slider("Battery usable capacity (kWh)", min_value=1.0, max_value=50.0, value=9.6, step=0.1)

arrival_time = st.time_input("Usual arrival time home", value=dtime(17, 0))

# Tariff + optional Solcast API
tariff_per_kwh = st.sidebar.number_input("Electricity cost (R / kWh)", min_value=0.1, max_value=20.0, value=2.5, step=0.1)
solcast_key = st.sidebar.text_input("Solcast API key (optional)", type="password")

# -------------------------
# SOLAR FORECAST FETCHING (Solcast or synthetic fallback)
# -------------------------
@st.cache_data(ttl=600)
def fetch_solcast(lat, lon, api_key):
    url = f"https://api.solcast.com.au/radiation/forecasts?latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json().get("forecasts", [])
    df = pd.DataFrame(data)
    df["Time"] = pd.to_datetime(df["period_end"])
    df["GHI"] = df["ghi"]
    return df[["Time", "GHI"]]

# Location selector
loc_choice = st.radio("🌍 Select Location", ["Limpopo (Polokwane)", "Nelspruit (Mbombela)"])
if loc_choice.startswith("Limpopo"):
    lat, lon = -23.8962, 29.4486
else:
    lat, lon = -25.4753, 30.9694

# Try fetching Solcast data
if solcast_key:
    try:
        df_fc = fetch_solcast(lat, lon, solcast_key)
    except Exception as e:
        st.warning(f"Solcast failed: {e}. Using demo forecast.")
        df_fc = None
else:
    df_fc = None

# Synthetic fallback
if df_fc is None:
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(now - timedelta(hours=12), periods=72, freq="1h")
    hours = index.hour + index.minute / 60.0
    ghi = np.maximum(0, 900 * np.sin((hours - 6) * np.pi / 12) + np.random.normal(0, 40, len(index)))
    df_fc = pd.DataFrame({"Time": index, "GHI": ghi})

# Compute solar power
SYSTEM_EFFICIENCY = 0.85
df_fc["Power_kW"] = (df_fc["GHI"] / 1000.0) * panel_kw * SYSTEM_EFFICIENCY

# -------------------------
# SYSTEM + LOAD PARAMETERS
# -------------------------
per_person_kw = 0.35
fridge_kw = 0.15
tv_kw = 0.10
wifi_kw = 0.02
phone_kw = 0.05
cook_kw = 1.2 if cook_electric else 0.0
evening_load_kw = household_size * per_person_kw + fridge_kw + tv_kw + wifi_kw + phone_kw + cook_kw

geyser_power_kw = 3.0 if has_geyser else 0.0
geyser_duration_h = 1.5 if has_geyser else 0.0

INVERTER_EFF = 0.90
CHARGER_EFF = 0.95
RESERVE_FRACTION = 0.10

# -------------------------
# AI Function to find best geyser time
# -------------------------
def find_next_geyser_time(forecast_df, now_dt, battery_total_kwh, battery_soc_frac,
                          inverter_eff, charger_eff, geyser_kw, geyser_h):
    fut = forecast_df[(forecast_df["Time"] >= now_dt) & (forecast_df["Time"] <= now_dt + timedelta(days=7))].copy()
    if fut.empty:
        return None, {"reason": "No forecast data available."}

    battery_energy = battery_total_kwh * battery_soc_frac
    durations = [(fut.loc[i + 1, "Time"] - fut.loc[i, "Time"]).total_seconds() / 3600
                 if i < len(fut) - 1 else 1.0 for i in range(len(fut))]

    for j in range(len(fut)):
        stored_by_j, batt_at_start = 0.0, battery_energy
        for i in range(j):
            prod_kwh = float(fut.loc[i, "Power_kW"]) * durations[i]
            to_store = min(max(0, prod_kwh) * charger_eff, max(0, battery_total_kwh - batt_at_start - stored_by_j))
            stored_by_j += to_store
        batt_at_start += stored_by_j

        hours_needed, k, battery_needed = geyser_h, j, 0.0
        while hours_needed > 0 and k < len(fut):
            step_h = durations[k]
            use_h = min(step_h, hours_needed)
            prod_kwh = float(fut.loc[k, "Power_kW"]) * use_h
            geyser_out_kwh = geyser_kw * use_h
            if prod_kwh < geyser_out_kwh:
                deficit = geyser_out_kwh - prod_kwh
                battery_needed += deficit / inverter_eff
            hours_needed -= use_h
            k += 1

        if batt_at_start >= battery_needed:
            start_time = fut.loc[j, "Time"]
            details = {
                "start_time": start_time,
                "battery_at_start_kwh": round(batt_at_start, 2),
                "battery_needed_kwh": round(battery_needed, 2),
            }
            return start_time, details
    return None, {"reason": "No off-grid window found in next 7 days."}

# -------------------------
# Money saved
# -------------------------
def money_saved_for_geyser(geyser_kw, geyser_h, tariff_rpkwh):
    energy_kwh = geyser_kw * geyser_h
    saving = energy_kwh * tariff_rpkwh
    return energy_kwh, saving

# -------------------------
# AI Simulation Button
# -------------------------
st.markdown("### 🧠 Test AI Logic — Find Next Solar-Only Geyser Time")
simulate_now = st.button("🔎 Test AI (Simulate Outage Now)")

initial_soc_frac = 0.40

if simulate_now:
    st.subheader("Results — AI Scheduling (Simulated)")
    now_dt = datetime.now().replace(minute=0, second=0, microsecond=0)

    start_time, details = find_next_geyser_time(
        forecast_df=df_fc,
        now_dt=now_dt,
        battery_total_kwh=battery_kwh,
        battery_soc_frac=initial_soc_frac,
        inverter_eff=INVERTER_EFF,
        charger_eff=CHARGER_EFF,
        geyser_kw=geyser_power_kw,
        geyser_h=geyser_duration_h,
    )

    if start_time:
        st.success(f"✅ AI scheduled geyser start: **{start_time.strftime('%a %d %b %I:%M %p')}**")
        st.write(f"- Battery at start: **{details['battery_at_start_kwh']:.2f} kWh**")
        st.write(f"- Battery required: **{details['battery_needed_kwh']:.2f} kWh**")

        event_kwh, event_saving_r = money_saved_for_geyser(geyser_power_kw, geyser_duration_h, tariff_per_kwh)
        st.write(f"- Geyser energy this run: **{event_kwh:.2f} kWh** → Money saved: **R{event_saving_r:.2f}**")
        st.write(f"- Projected daily/weekly/monthly savings: **R{event_saving_r:.2f}/day**, "
                 f"**R{event_saving_r*7:.2f}/week**, **R{event_saving_r*30:.2f}/month**")

    else:
        st.error("⚠️ No solar-only geyser window found.")
        st.write("Reason:", details["reason"])

# -------------------------
# Graph (24h forecast)
# -------------------------
st.markdown("### ☀️ 24-Hour Solar Forecast")

now = datetime.now().replace(minute=0, second=0, microsecond=0)
df_24 = df_fc[(df_fc["Time"] >= now) & (df_fc["Time"] < now + timedelta(days=1))].copy()

fig = px.line(
    df_24,
    x="Time",
    y="GHI",
    title=f"Forecast — {loc_choice} (24h)",
    labels={"GHI": "Irradiance (W/m²)", "Time": "Hour of Day"},
)
fig.update_traces(line=dict(width=3), hovertemplate="Time: %{x|%H:%M}<br>GHI: %{y:.0f} W/m²")
fig.update_layout(
    template="plotly_white",
    xaxis=dict(
        dtick=3600000,
        tickformat="%H:%M",
        rangeslider=dict(visible=True),
        title="Time of Day"
    ),
    yaxis=dict(title="Solar Irradiance (W/m²)"),
    margin=dict(l=20, r=20, t=40, b=40),
    height=450,
)
st.plotly_chart(fig, use_container_width=True)
