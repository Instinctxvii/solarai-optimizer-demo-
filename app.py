# SolarAI Optimizer™ — AI finds absolute next best peak to run geyser off solar+inverter (no grid)
# Replace app.py and run: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, time as dtime

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="SolarAI Optimizer™", layout="wide")
st.title("☀️ SolarAI Optimizer™")
st.markdown("AI-smart geyser scheduling to avoid grid usage (Growatt 5kW ES class assumed).")

# -------------------------
# USER INPUTS (simple)
# -------------------------
st.markdown("### 1) Your home (simple inputs)")
c1, c2, c3 = st.columns(3)
household_size = c1.selectbox("Household size", [1,2,3,4,5,6], index=2)
has_geyser = c2.checkbox("Electric geyser?", value=True)
cook_electric = c3.checkbox("Electric cooking?", value=False)

c4, c5 = st.columns(2)
panel_kw = c4.slider("Solar system peak (kW)", min_value=1.0, max_value=10.0, value=5.0, step=0.5)
battery_kwh = c5.slider("Battery usable capacity (kWh) — approx", min_value=1.0, max_value=50.0, value=9.6, step=0.1)

arrival_time = st.time_input("Usual arrival time home", value=dtime(17,0))

# tariff and solcast key
tariff_per_kwh = st.sidebar.number_input("Electricity cost (R / kWh)", min_value=0.1, max_value=20.0, value=2.5, step=0.1)
solcast_key = st.sidebar.text_input("Solcast API key (optional)", type="password")

# -------------------------
# FORECAST fetching (Solcast or synthetic fallback)
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
    return df[["Time","GHI"]]

# choose location
loc_choice = st.radio("Location", ["Limpopo (Polokwane)", "Nelspruit (Mbombela)"])
if loc_choice.startswith("Limpopo"):
    lat, lon = -23.8962, 29.4486
else:
    lat, lon = -25.4753, 30.9694

# get forecast (24-48h hourly samples preferred)
if solcast_key:
    try:
        df_fc = fetch_solcast(lat, lon, solcast_key)
    except Exception as e:
        st.warning(f"Solcast failed: {e}. Using demo forecast.")
        df_fc = None
else:
    df_fc = None

if df_fc is None:
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(now - timedelta(hours=12), periods=72, freq="1h")
    hours = index.hour + index.minute/60.0
    ghi = np.maximum(0, 900 * np.sin((hours - 6) * np.pi / 12) + np.random.normal(0,40,len(index)))
    df_fc = pd.DataFrame({"Time": index, "GHI": ghi})

# compute approximate instantaneous PV power (kW)
SYSTEM_EFFICIENCY = 0.85
df_fc["Power_kW"] = (df_fc["GHI"] / 1000.0) * panel_kw * SYSTEM_EFFICIENCY

# -------------------------
# SIMPLE INTERNAL ESTIMATES (hidden complexity)
# -------------------------
# evening baseline uses household size
per_person_kw = 0.35
fridge_kw = 0.15
tv_kw = 0.10
wifi_kw = 0.02
phone_kw = 0.05
cook_kw = 1.2 if cook_electric else 0.0
evening_load_kw = household_size * per_person_kw + fridge_kw + tv_kw + wifi_kw + phone_kw + cook_kw

# geyser params
geyser_power_kw = 3.0 if has_geyser else 0.0
geyser_duration_h = 1.5 if has_geyser else 0.0

# device/inverter assumptions (internal)
INVERTER_EFF = 0.90
CHARGER_EFF = 0.95
RESERVE_FRACTION = 0.10  # keep 10% as reserve

# -------------------------
# AI function: find absolute next time to run geyser using only solar-charged inverter (no grid)
# Algorithm overview:
#  - simulate forward from "now" up to N days (default 7) in hourly steps
#  - at each forecast timestamp t, compute cumulative solar energy that can be stored in battery BEFORE t
#    (charging only from solar; battery cannot be charged from grid)
#  - also allow direct solar during geyser run to offset battery draw
#  - identify earliest t where combined (battery_at_t + expected_direct_solar_during_run) >= geyser_required_from_batt
#  - return that t and timeline details
# -------------------------
def find_next_geyser_time(forecast_df, now_dt, battery_total_kwh, battery_soc_frac,
                          inverter_eff, charger_eff, geyser_kw, geyser_h):
    # prepare
    horizon = now_dt + timedelta(days=7)  # search up to 7 days
    fut = forecast_df[(forecast_df["Time"] >= now_dt) & (forecast_df["Time"] <= horizon)].copy().reset_index(drop=True)
    if fut.empty:
        return None, {"reason":"No forecast data available in search window."}

    # battery current energy (kWh)
    battery_energy = battery_total_kwh * battery_soc_frac

    # amount battery can store = battery_total - battery_energy
    # We'll step through fut and compute how much can be stored before each candidate start time
    timeline = []
    # precompute step durations (hours) for each row
    durations = []
    for i in range(len(fut)):
        if i < len(fut) - 1:
            dh = (fut.loc[i+1,"Time"] - fut.loc[i,"Time"]).total_seconds() / 3600.0
            if dh <= 0:
                dh = 1.0
        else:
            dh = durations[-1] if durations else 1.0
        durations.append(dh)

    # cumulative stored energy array: energy that gets added to battery from now until start_time
    # We'll iterate candidate start indices j; for each, compute stored energy in hours before j
    for j in range(len(fut)):
        # simulate charging from now index 0 up to index j-1
        stored_by_j = 0.0
        batt_at_start = battery_energy
        for i in range(0, j):
            prod_kwh = float(fut.loc[i,"Power_kW"]) * durations[i]
            # storeable (after meeting any negligible daytime loads) -> charger eff applies
            storeable = max(0.0, prod_kwh) * charger_eff
            # remaining capacity
            remaining_cap = max(0.0, battery_total_kwh - batt_at_start - stored_by_j)
            to_store = min(storeable, remaining_cap)
            stored_by_j += to_store
        batt_at_start += stored_by_j

        # Now simulate geyser run starting at fut.loc[j,"Time"] for geyser_h hours, stepping through future rows
        # Compute direct solar during run and battery draw required
        hours_needed = geyser_h
        k = j
        battery_needed = 0.0  # energy to be supplied by battery (kWh) over run to supplement direct solar, BEFORE inverter ineff
        while hours_needed > 0 and k < len(fut):
            step_h = durations[k]
            use_h = min(step_h, hours_needed)
            prod_kwh = float(fut.loc[k,"Power_kW"]) * use_h
            # direct solar used to power geyser first (no battery)
            geyser_out_kwh = geyser_kw * use_h
            # if prod_kwh >= geyser_out -> surplus can store (but storage during run isn't relevant for starting)
            if prod_kwh >= geyser_out_kwh:
                # direct solar covers this block; battery not needed for it
                pass
            else:
                # deficit must be provided by battery via inverter: deficit / inverter_eff
                deficit = geyser_out_kwh - prod_kwh
                batt_supply = deficit / inverter_eff
                battery_needed += batt_supply
            hours_needed -= use_h
            k += 1

        # If battery_at_start >= battery_needed then we can run at fut.loc[j]["Time"]
        if batt_at_start >= battery_needed:
            # found earliest time
            # construct a short timeline summary for display (few rows before and during run)
            start_time = fut.loc[j,"Time"]
            timeline_rows = []
            pre_start_idx = max(0, j-6)
            for ii in range(pre_start_idx, min(len(fut), j+int(np.ceil(geyser_h))+3)):
                timeline_rows.append({
                    "Time": fut.loc[ii,"Time"],
                    "Power_kW": float(fut.loc[ii,"Power_kW"]),
                    "Duration_h": durations[ii],
                })
            details = {
                "start_time": start_time,
                "battery_at_start_kwh": round(batt_at_start, 3),
                "battery_needed_kwh": round(battery_needed, 3),
                "timeline": pd.DataFrame(timeline_rows)
            }
            return start_time, details

    return None, {"reason":"No suitable time in forecast window where battery+direct-solar can fully run geyser without grid."}

# -------------------------
# Money saved calculation
# -------------------------
def money_saved_for_geyser(geyser_kw, geyser_h, tariff_rpkwh):
    energy_kwh = geyser_kw * geyser_h
    saving = energy_kwh * tariff_rpkwh
    return energy_kwh, saving

# -------------------------
# UI: Test AI button
# -------------------------
st.markdown("### 2) Test AI — Simulate outage now (AI will find the absolute next best peak/time to run geyser using solar-charged inverter only)")
simulate_now = st.button("🔎 Test AI (Simulate outage now)")

# We assume a reasonable initial SoC (battery charged partially) — to keep demo friendly we assume 40% start
initial_soc_frac = 0.40

# When user presses simulate_now, run the search & show results
if simulate_now:
    st.subheader("Results — AI Scheduling (simulate live)")
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

    if start_time is not None:
        st.success(f"✅ AI-scheduled start time (no-grid): **{start_time.strftime('%a %d %b %I:%M %p')}**")
        st.write(f"- Battery energy at start (kWh): **{details['battery_at_start_kwh']:.2f}**")
        st.write(f"- Battery energy required for geyser run (kWh): **{details['battery_needed_kwh']:.2f}**")
        # Money saved for one geyser heat event
        event_kwh, event_saving_r = money_saved_for_geyser(geyser_power_kw, geyser_duration_h, tariff_per_kwh)
        st.write(f"- Geyser energy this run: **{event_kwh:.2f} kWh** → Money saved if from solar: **R{event_saving_r:.2f}**")
        # project daily/weekly/monthly savings (if run daily)
        st.write(f"- Projected savings if repeated daily: **R{event_saving_r*1:.2f}/day**, **R{event_saving_r*7:.2f}/week**, **R{event_saving_r*30:.2f}/month**")

        # Show evening backup runtime estimate at arrival using battery state after charging until arrival
        # Simulate battery from now until arrival_time (player assumed arrival today; if arrival in past, use tomorrow)
        arrive_dt = datetime.combine(now_dt.date(), arrival_time)
        if arrive_dt <= now_dt:
            arrive_dt += timedelta(days=1)
        # quick simulate charging from now until arrival (not pre-heating unless start_time happens before arrival)
        # We'll simulate day production from now to arrive_dt and compute battery energy at arrival
        def simulate_to_arrival(df, start, end, battery_energy):
            fut = df[(df["Time"] >= start) & (df["Time"] < end)].reset_index(drop=True)
            for i in range(len(fut)):
                step_h = 1.0
                prod = float(fut.loc[i,"Power_kW"]) * step_h
                # assume daytime loads small; all surplus stored
                if prod > 0:
                    storeable = prod * CHARGER_EFF
                    battery_energy = min(battery_kwh, battery_energy + storeable)
            return battery_energy

        battery_at_arrival = simulate_to_arrival(df_fc, now_dt, arrive_dt, battery_kwh * initial_soc_frac)
        usable_at_arrival = max(0.0, battery_at_arrival - battery_kwh * RESERVE_FRACTION)
        # estimated evening runtime using inverter_eff and evening load
        if evening_load_kw > 0:
            runtime_h = (usable_at_arrival * INVERTER_EFF) / evening_load_kw
        else:
            runtime_h = 0.0

        st.markdown("---")
        st.subheader("Simple helpful summary")
        st.write(f"- Best time to heat geyser (AI): **{start_time.strftime('%a %d %b %I:%M %p')}**")
        st.write(f"- Estimated battery at arrival: **{battery_at_arrival:.2f} kWh** total ({usable_at_arrival:.2f} kWh usable after reserve)")
        st.write(f"- Estimated evening load: **{evening_load_kw:.2f} kW**")
        st.write(f"- Estimated backup runtime (if outage at arrival): **{runtime_h:.2f} hours** (~{int(runtime_h*60)} minutes)")

        with st.expander("Show detailed simulated timeline (preview)"):
            st.dataframe(details["timeline"])

    else:
        st.error("⚠️ AI could not find a fully off-grid (solar+battery only) window to run the geyser within the forecast horizon.")
        if "reason" in details:
            st.write("Reason:", details["reason"])

# -------------------------
# Graph: show 24h forecast and a range slider
# -------------------------
st.markdown("### Forecast — 24 hours")
now = datetime.now().replace(minute=0, second=0, microsecond=0)
df_24 = df_fc[(df_fc["Time"] >= now) & (df_fc["Time"] < now + timedelta(days=1))].copy()
fig = px.line(df_24, x="Time", y="GHI", title=f"Forecast — {loc_choice} (24 h)", labels={"GHI":"Irradiance (W/m²)"})
fig.update_layout(xaxis=dict(dtick=3600000, tickformat="%H:%M", rangeslider=dict(visible=True)))
st.plotly_chart(fig, use_container_width=True)

# -------------------------
# End — no extra footer text as requested
# -------------------------
