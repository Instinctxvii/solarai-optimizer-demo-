# === SolarAI Optimizer™ (Complete, Fixed, Polished) ===
import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
import plotly.express as px

# ======================================================
# === 🌞 APP CONFIG ===
# ======================================================
st.set_page_config(
    page_title="☀️ SolarAI Optimizer™",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ **SolarAI Optimizer™**")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# ======================================================
# === ⚙️ INPUT SECTIONS ===
# ======================================================

with st.expander("## ⚙️ System, Battery & Loads", expanded=True):
    st.subheader("### ⚙️ Your Solar System")
    col1, col2, col3 = st.columns(3)
    panel_kw = col1.number_input("Panel Size (kW)", 0.5, 20.0, 5.0, 0.5)
    daily_usage = col2.number_input("Daily Usage (hours)", 1, 24, 6)
    elec_cost = col3.number_input("Electricity Cost (R/kWh)", 0.5, 10.0, 2.5)

    st.text_input("Solcast API Key (optional)")

    st.subheader("### 🔋 Battery & Inverter")
    c1, c2, c3, c4, c5 = st.columns(5)
    battery_capacity = c1.number_input("Battery Capacity (Ah)", 50, 2000, 200)
    battery_voltage = c2.number_input("Battery Nominal Voltage (V)", 12, 96, 48)
    soc_now = c3.slider("Current Battery SoC (%)", 0, 100, 50)
    inverter_eff = c4.slider("Inverter Efficiency (%)", 70, 98, 90)
    charger_eff = c5.slider("Charger Efficiency (%)", 70, 98, 95)
    reserve_soc = st.slider("Reserve SoC (%) — keep this much as buffer", 0, 50, 10)

    st.subheader("### ⚡ Geyser")
    g1, g2, g3 = st.columns(3)
    geyser_kw = g1.number_input("Geyser Power (kW)", 1.0, 5.0, 3.0)
    geyser_hours = g2.number_input("Geyser Duration (hours)", 0.5, 5.0, 1.5)
    geyser_use_during_loadshedding = g3.checkbox("Allow geyser during loadshedding?", False)

    st.subheader("### 🏠 Household Loads")
    h1, h2, h3, h4 = st.columns(4)
    base_load_kw = h1.number_input("Baseline load (lights/fridge/etc.) (kW)", 0.1, 3.0, 0.6)
    fridge_kw = h2.number_input("Fridge (kW) estimate (peak)", 0.05, 1.0, 0.25)
    phone_kw = h3.number_input("Phone charging (kW)", 0.01, 1.0, 0.1)
    cooking_kw = h4.number_input("Cooking (kW)", 0.1, 5.0, 1.0)

    st.subheader("### ⏱️ Loadshedding Scenario")
    l1, l2 = st.columns(2)
    shedding_hours = l1.number_input("Expected loadshedding duration (hours)", 2, 24, 6)
    safety_margin = l2.slider("Sizing safety margin (%)", 0, 100, 20)

# ======================================================
# === 🌍 LOCATION SELECTION ===
# ======================================================
st.subheader("### 🌍 Select Location")
location = st.radio("Choose location:", ["📍 Limpopo (Polokwane)", "🌞 Nelspruit (Mbombela)"])
if location.startswith("📍"):
    loc = {"name": "Limpopo (Polokwane)", "lat": -23.9, "lon": 29.45}
else:
    loc = {"name": "Nelspruit (Mbombela)", "lat": -25.47, "lon": 30.98}

if st.button("🔄 Reset / Refresh"):
    st.rerun()

st.markdown(f"**📡 Current Location:** {loc['name']}")

# ======================================================
# === GENERATE SOLAR FORECAST (Mock) ===
# ======================================================
now = dt.datetime.now().replace(minute=0, second=0, microsecond=0)
times = [now - dt.timedelta(hours=12) + dt.timedelta(hours=i) for i in range(0, 49)]

solar_yield = [max(0, np.sin((t.hour - 6) / 12 * np.pi) * 900 + np.random.uniform(-50, 50)) for t in times]
df = pd.DataFrame({"Time": times, "Solar Yield (W/m²)": solar_yield})
df["Power_kW"] = (df["Solar Yield (W/m²)"] / 1000) * panel_kw * 0.8  # 80% system efficiency

# ======================================================
# === 🔍 AI LOGIC FOR NEXT BEST GEYSER TIME ===
# ======================================================
def find_next_run_with_loads(forecast_df, battery_capacity, battery_voltage,
                             soc_now, reserve_soc, inverter_eff,
                             geyser_kw, geyser_hours,
                             base_load_kw, fridge_kw, phone_kw, cooking_kw,
                             allow_geyser_during_loadshedding):
    # Total battery energy available in kWh
    usable_kwh = (battery_capacity * battery_voltage / 1000) * ((soc_now - reserve_soc) / 100)
    total_load = base_load_kw + fridge_kw + phone_kw + cooking_kw
    forecast_df = forecast_df.copy()
    forecast_df["Available_kW"] = forecast_df["Power_kW"] * (inverter_eff / 100)

    # Best geyser run time where solar + battery > total loads
    for i in range(len(forecast_df)):
        prod_kw = forecast_df.loc[i, "Available_kW"]
        if prod_kw > (total_load + geyser_kw * 0.9):
            next_time = forecast_df.loc[i, "Time"]
            return next_time, {
                "available_power_kw": round(prod_kw, 2),
                "total_load_kw": round(total_load, 2),
                "battery_kwh": round(usable_kwh, 2)
            }

    # If nothing found, fall back to when battery can supply it
    if usable_kwh > geyser_kw * geyser_hours:
        return now + dt.timedelta(hours=1), {
            "available_power_kw": round(0, 2),
            "total_load_kw": round(total_load, 2),
            "battery_kwh": round(usable_kwh, 2)
        }
    return None, None

next_time, details = find_next_run_with_loads(
    forecast_df=df,
    battery_capacity=battery_capacity,
    battery_voltage=battery_voltage,
    soc_now=soc_now,
    reserve_soc=reserve_soc,
    inverter_eff=inverter_eff,
    geyser_kw=geyser_kw,
    geyser_hours=geyser_hours,
    base_load_kw=base_load_kw,
    fridge_kw=fridge_kw,
    phone_kw=phone_kw,
    cooking_kw=cooking_kw,
    allow_geyser_during_loadshedding=geyser_use_during_loadshedding
)

# Battery sizing suggestion
total_kwh_needed = (base_load_kw + fridge_kw + phone_kw + cooking_kw + geyser_kw) * shedding_hours * (1 + safety_margin/100)
suggested_ah = (total_kwh_needed * 1000) / battery_voltage
if suggested_ah > battery_capacity:
    st.warning(f"💡 Your 200 Ah battery may be too small for {shedding_hours} h outages. Suggested: **{int(suggested_ah)} Ah** or more.")

# ======================================================
# === GRAPH (Smooth + Slider + Hourly Labels) ===
# ======================================================
fig = px.line(
    df,
    x="Time",
    y="Solar Yield (W/m²)",
    title=f"☀️ Global Horizontal Irradiance — {loc['name']} (24 Hours View)",
    labels={"Solar Yield (W/m²)": "Yield (W/m²)", "Time": "Hour of Day"},
)

fig.update_traces(
    line=dict(color="rgba(0, 123, 255, 0.6)", width=3),
    mode="lines+markers",
    marker=dict(size=7, color="rgba(0, 123, 255, 0.8)", line=dict(width=1, color="white")),
    hovertemplate="Time: %{x|%H:%M}<br>Yield: %{y:.0f} W/m²<extra></extra>",
    line_shape="spline"
)

fig.update_layout(
    height=460,
    margin=dict(l=30, r=30, t=60, b=60),
    title_x=0.5,
    plot_bgcolor="white",
    paper_bgcolor="white",
    hovermode="x unified",
    xaxis=dict(
        dtick=3600000 * 3,  # every 3 hours
        tickformat="%H:%M",
        rangeslider=dict(visible=True, bgcolor="rgba(240,240,255,0.5)", thickness=0.05),
        showgrid=False,
        tickfont=dict(size=13),
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(200,200,200,0.3)",
        zeroline=False,
        tickfont=dict(size=13),
    ),
    dragmode="pan"
)

config = {"displayModeBar": True, "scrollZoom": True}

st.plotly_chart(fig, use_container_width=True, config=config)

# ======================================================
# === 🔆 RESULTS ===
# ======================================================
st.subheader("### 🔆 Solar Yield Forecast")
if next_time:
    st.success(f"✅ **Optimal geyser run time:** {next_time.strftime('%H:%M')} — "
               f"Available Power: {details['available_power_kw']} kW | "
               f"Battery Energy: {details['battery_kwh']} kWh")
else:
    st.error("No suitable solar window found — consider increasing battery or shifting loads.")
