# SolarAI Optimizer™ — Simple Demo (consumer-friendly)
# Copy this file into app.py and run: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, time as dtime

st.set_page_config(page_title="SolarAI Optimizer™", layout="wide")

# -------------------------
# UI (simple)
# -------------------------
st.title("☀️ SolarAI Optimizer™")
st.markdown("AI-powered solar suggestions — simple, friendly, and practical.")

st.markdown("### 1) Tell us about your home (quick)")
col1, col2, col3 = st.columns(3)
household_size = col1.selectbox("Household size", options=[1,2,3,4,5,6], index=2, help="Number of people living in home")
has_geyser = col2.checkbox("Do you have an electric geyser?", value=True)
cook_electric = col3.checkbox("Do you cook with electricity (stove/plate)?", value=False)

col4, col5 = st.columns(2)
panel_kw = col4.slider("Solar panel system (approx. peak kW)", 1.0, 10.0, 5.0, 0.5)
battery_kwh = col5.slider("Battery size (kWh) — approximate usable capacity", 1.0, 30.0, 2.4, 0.1,
                          help="Enter the battery usable energy in kWh (e.g. 200Ah@12V ≈ 2.4 kWh)")

st.markdown("### 2) Schedule & loadshedding")
arrival_time = st.time_input("What time do you usually arrive home?", value=dtime(17,0))
# assumed loadshedding start shortly after arrival (common), allow editing
ls_hours = st.slider("Expected loadshedding duration (hours)", 1, 24, 6)
ls_start_offset_min = st.number_input("If loadshedding typically starts minutes after you arrive (e.g. 10):", 0, 120, 10)

st.markdown("Optional: paste Solcast API key in sidebar to use live forecasts (demo data used otherwise).")

# Advanced (hidden) — show if user wants
with st.expander("Advanced (for power users) — internal assumptions (click to view)"):
    st.write("""
    These assumptions are internal to the demo:
    - Inverter efficiency = 90%  
    - Charger efficiency = 95%  
    - Reserve battery kept = 10% (we don't recommend fully draining battery)  
    - Average per-person baseline evening consumption estimated automatically (see below)
    """)

# -------------------------
# Forecast (demo synthetic; optional Solcast)
# -------------------------
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")
# For demo we generate hourly synthetic 48-hour forecast centered on today
now = datetime.now().replace(minute=0, second=0, microsecond=0)
start = now - timedelta(hours=24)
hours = pd.date_range(start, start + timedelta(hours=48), freq="1h")
# synthetic GHI pattern (0..1000-ish)
hours_float = hours.hour + hours.minute/60.0
seasonal = 1.0  # keep neutral
ghi = np.maximum(0, 900 * np.sin((hours_float - 6) * np.pi / 12) * seasonal + np.random.normal(0, 40, len(hours)))
df = pd.DataFrame({"Time": hours, "GHI": ghi})
# approximate instantaneous solar power (kW) = (GHI/1000) * panel_kw * system_efficiency(0.85)
df["Power_kW"] = (df["GHI"] / 1000.0) * panel_kw * 0.85

# If user supplied solcast_key, we could call API (omitted here because demo offline), but keep placeholder
if solcast_key:
    st.sidebar.success("Solcast key provided — in production this would enable live forecasts.")

# -------------------------
# Internal estimates (consumer-friendly)
# -------------------------
# Estimate evening baseline load (lights, fridge, wifi, phone) from household size
# Use simple rules: baseline per person ~0.35 kW evening average (lights, devices), fridge ~0.15 kW
per_person_evening = 0.35  # kW
fridge_kW_avg = 0.15
phone_kW = 0.05
tv_kW = 0.10
wifi_kW = 0.02
cooking_kW = 1.2 if cook_electric else 0.0
# Evening baseline = per person * household_size + fridge + tv + wifi + phone
evening_baseline_kw = household_size * per_person_evening + fridge_kW_avg + tv_kW + wifi_kW + phone_kW + cooking_kW

# Geyser defaults (consumer-friendly)
geyser_power_kw = 3.0 if has_geyser else 0.0
geyser_duration_h = 1.5 if has_geyser else 0.0

# internal efficiencies (not shown in UI unless expanded)
INVERTER_EFF = 0.90
CHARGER_EFF = 0.95
RESERVE_FRACTION = 0.10  # keep 10% buffer of battery total

# -------------------------
# Find best peak (AI simple heuristic = highest GHI near midday)
# -------------------------
# Use next day's peak: find maximum GHI in the next 24-hour window starting today midnight
today_mid = now.replace(hour=0)
window = df[(df["Time"] >= today_mid) & (df["Time"] < today_mid + timedelta(days=1))]
peak_row = window.loc[window["GHI"].idxmax()]
peak_time = peak_row["Time"]
peak_power_kw = float(peak_row["Power_kW"])

# -------------------------
# Simulate charging from peak until arrival time
# -------------------------
# We'll simulate hourly steps between peak_time and arrival_time (today's arrival) to estimate battery SoC at arrival
# For clarity we assume geyser is heated at peak_time (if user has geyser) and consumes energy immediately (so battery may be used)
# Timeline:
#  - At peak_time: optionally schedule geyser to run and consume geyser_energy (we assume AI chooses to heat at peak if beneficial)
#  - After geyser run, remaining solar charges battery until arrival_time
arrive_dt = datetime.combine(now.date(), arrival_time)
# if arrival before peak (rare) assume peak happens earlier same day; use next peak:
if arrive_dt <= peak_time:
    # use next peak (peak in the window after arrival)
    window_after = df[(df["Time"] >= arrive_dt) & (df["Time"] < arrive_dt + timedelta(hours=24))]
    if not window_after.empty:
        peak_row = window_after.loc[window_after["GHI"].idxmax()]
        peak_time = peak_row["Time"]
        peak_power_kw = float(peak_row["Power_kW"])

# battery capacity kWh is given
battery_total_kwh = battery_kwh
battery_usable_kwh = battery_total_kwh * (1.0 - RESERVE_FRACTION)

# Start simulation: battery state before peak — assume some initial moderate SoC (50%) unless battery is charged in day:
# To keep demo simple and helpful, assume morning battery SoC is 40% (typical after night)
initial_soc_frac = 0.40
battery_energy = battery_total_kwh * initial_soc_frac

# If geyser heats at peak, subtract geyser consumption from either direct solar (preferred) or battery
def simulate_charge_and_geyser(df, peak_time, geyser_on, geyser_kw, geyser_h, battery_energy_kwh):
    """Simulates one-hour steps after peak_time to arrival, returns battery energy at arrival (kWh) and details."""
    # copy df and start from peak_time
    future = df[df["Time"] >= peak_time].copy().reset_index(drop=True)
    # we'll simulate until arrival_dt (if arrival before last sample, stop)
    battery = battery_energy_kwh
    timeline = []
    # step through rows until arrival
    for i in range(len(future)):
        t = future.loc[i, "Time"]
        if t >= arrive_dt:
            break
        # determine step duration to next row (hours)
        if i < len(future) - 1:
            step_h = (future.loc[i+1, "Time"] - future.loc[i, "Time"]).total_seconds() / 3600.0
            if step_h <= 0:
                step_h = 1.0
        else:
            step_h = 1.0
        prod_kwh = float(future.loc[i, "Power_kW"]) * step_h
        # first, if geyser_on and this is within the geyser window starting at peak_time, consume geyser energy
        geyser_out_kwh = 0.0
        if geyser_on:
            # try to allocate geyser schedule starting at peak_time for geyser_h hours
            # simple approach: if t >= peak_time and t < peak_time + geyser_h -> geyser running now
            if (t >= peak_time) and (t < peak_time + timedelta(hours=geyser_h)):
                geyser_out_kwh = geyser_kw * step_h
        # net production after meeting instant household baseline during daytime (we assume daytime baseline small)
        # in demo we assume daytime household draw is small compared to evening; we ignore daytime household draw for simplicity
        net_surplus = max(0.0, prod_kwh - geyser_out_kwh)
        # storeable energy after charger efficiency
        store_kwh = net_surplus * CHARGER_EFF
        # charge battery up to max
        battery = min(battery_total_kwh, battery + store_kwh)
        timeline.append({"Time": t, "prod_kwh": prod_kwh, "geyser_out_kwh": geyser_out_kwh, "battery_kwh": battery})
    return battery, timeline

# Decide AI: heat geyser at peak if user has geyser — simplified heuristic: if peak power >= geyser_kw*0.8 then yes
heat_at_peak = False
if has_geyser and (peak_power_kw >= geyser_power_kw*0.8):
    heat_at_peak = True

battery_after_arrival, timeline = simulate_charge_and_geyser(
    df=df,
    peak_time=peak_time,
    geyser_on=heat_at_peak,
    geyser_kw=geyser_power_kw,
    geyser_h=geyser_duration_h,
    battery_energy_kwh=battery_energy,
)

# -------------------------
# Estimate available runtime during loadshedding (starting arrival + offset)
# -------------------------
ls_start = datetime.combine(arrive_dt.date(), arrival_time) + timedelta(minutes=ls_start_offset_min)
usable_at_ls = max(0.0, battery_after_arrival - battery_total_kwh * RESERVE_FRACTION)  # already applied reserve
# inverter losses: runtime = usable_at_ls * inverter_eff / evening_load
evening_load = evening_baseline_kw
if has_geyser:
    # If geyser would be turned on during loadshedding, add to evening load (but typically geyser is hot from earlier)
    # We assume geyser not run during evening loadshedding unless user triggers it.
    pass

# runtime hours
if evening_load <= 0:
    runtime_hours = 0.0
else:
    runtime_hours = (usable_at_ls * INVERTER_EFF) / evening_load

# If runtime < expected loadshedding, recommend larger battery
if runtime_hours < ls_hours:
    # simple recommended total kWh = evening_load * ls_hours / inverter_eff, then add reserve and margin
    required_batt_for_ls_kwh = (evening_load * ls_hours) / INVERTER_EFF
    # add reserve fraction and small safety margin 10%
    recommended_total_kwh = required_batt_for_ls_kwh / (1.0 - RESERVE_FRACTION) * 1.1
    recommended_total_kwh = round(recommended_total_kwh, 1)
else:
    recommended_total_kwh = None

# -------------------------
# Present simplified outputs to user
# -------------------------
st.markdown("## Results — simple, helpful summary")

colA, colB = st.columns(2)
with colA:
    st.subheader("Best solar window (AI)")
    st.write(f"**Peak solar detected:** {peak_time.strftime('%a %d %b %I:%M %p')}  — expected panel output around **{peak_power_kw:.2f} kW** at peak.")
    if heat_at_peak:
        st.success(f"AI would pre-heat your geyser at that peak (approx {geyser_duration_h} h of heating).")
    else:
        st.info("AI did not schedule geyser heating at peak automatically (insufficient solar).")

    st.markdown("---")
    st.subheader("Estimated battery at arrival")
    st.write(f"Assumed morning SoC: 40% (demo).")
    st.write(f"Estimated battery after solar & geyser at {arrival_time.strftime('%H:%M')}: **{battery_after_arrival:.2f} kWh** total.")
    st.write(f"Usable (after 10% reserve): **{usable_at_ls:.2f} kWh**.")

with colB:
    st.subheader("Evening load & backup estimate")
    st.write(f"Estimated evening household load (lights, TV, Wi-Fi, phones{', cooking' if cook_electric else ''}): **{evening_load:.2f} kW**.")
    st.write(f"If loadshedding starts at {ls_start.strftime('%I:%M %p')}, estimated backup runtime: **{runtime_hours:.2f} hours** ({int(runtime_hours*60)} minutes).")
    if recommended_total_kwh:
        st.warning(f"To cover {ls_hours} hours you would need ~**{recommended_total_kwh} kWh** battery capacity (total).")
    else:
        st.success("Your battery appears sufficient for the expected outage length.")

st.markdown("---")
st.subheader("Graph — forecast & slider")
fig = px.line(df[(df["Time"] >= today_mid) & (df["Time"] < today_mid + timedelta(days=1))],
              x="Time", y="GHI",
              labels={"GHI": "Global Horizontal Irradiance (W/m²)"},
              title="Forecast (24 hours)")
fig.update_layout(xaxis=dict(dtick=3600000, tickformat="%H:%M", rangeslider=dict(visible=True)))
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.info("This demo keeps the UI simple for homeowners. If you'd like the full technical breakdown (Ah, voltages, charge/discharge efficiencies), open 'Advanced' at the top.")
st.caption("Estimates are illustrative. For precise system design consult a solar installer or an electrician.")
