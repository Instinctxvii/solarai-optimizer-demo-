# SolarAI Optimizer™ — Multi-cycle geyser scheduling, battery SoC, and solar-only recharge estimates
# Copy to app.py and run: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, time as dtime
import requests

st.set_page_config(page_title="SolarAI Optimizer™", layout="wide")
st.title("☀️ SolarAI Optimizer™")
st.markdown("AI-smart geyser scheduling: multi-cycle heating, battery SoC after heating, and solar-only recharge times.")

# -----------------------
# Simple consumer inputs
# -----------------------
st.markdown("### 1) Tell the AI a little about your home")
c1, c2, c3 = st.columns([1,1,1])
household_size = c1.selectbox("Household size", [1,2,3,4,5,6], index=3)
has_geyser = c2.checkbox("Electric geyser installed?", value=True)
cook_electric = c3.checkbox("Electric cooking?", value=False)
arrival_time = st.time_input("Typical arrival home time", value=dtime(17,0))

# Tariff and optional Solcast key
tariff_per_kwh = st.sidebar.number_input("Electricity cost (R / kWh)", min_value=0.5, max_value=20.0, value=2.50, step=0.1)
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")

# -----------------------
# AI default system sizing (auto-detect-ish)
# -----------------------
# We infer reasonable defaults from household_size:
# - system_kw scaled with household size (typical residential: 3-6 kW)
# - battery_kwh based on 48V 200Ah baseline scaled for household
SYSTEM_BASE_KW = 4.5
BATTERY_BASE_KWH = 9.6  # 48V 200Ah baseline

# scale factors
system_kw = round(SYSTEM_BASE_KW + (household_size - 3) * 0.6, 1)  # e.g. households with more people get slightly larger PV
battery_kwh = round(BATTERY_BASE_KWH * (1 + (household_size - 3) * 0.12), 1)

# Inverter model (assumed)
inverter_model = "Growatt SPF 5000 ES (48V class)"
INVERTER_EFF = 0.90
CHARGER_EFF = 0.95
RESERVE_FRACTION = 0.10  # keep 10% reserve

# geyser defaults
geyser_power_kw = 3.0 if has_geyser else 0.0
geyser_duration_h = 1.5 if has_geyser else 0.0
geyser_event_kwh = geyser_power_kw * geyser_duration_h

st.markdown(f"**AI estimate:** PV ~ **{system_kw} kW**, Battery ~ **{battery_kwh} kWh** (usable before reserve) — hidden from homeowner UI normally")

# -----------------------
# Forecast retrieval (Solcast or synthetic)
# -----------------------
@st.cache_data(ttl=600)
def fetch_solcast_forecast(lat, lon, api_key):
    try:
        url = f"https://api.solcast.com.au/radiation/forecasts?latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        df = pd.DataFrame(js.get("forecasts", []))
        df["Time"] = pd.to_datetime(df["period_end"]).dt.tz_localize(None)
        df["GHI"] = df["ghi"]
        return df[["Time", "GHI"]]
    except Exception:
        return None

# Location selector
loc = st.radio("Select location:", ["Limpopo (Polokwane)", "Nelspruit (Mbombela)"], horizontal=True)
if loc.startswith("Limpopo"):
    lat, lon = -23.8962, 29.4486
else:
    lat, lon = -25.4753, 30.9694

# fetch forecast
df_fc = None
if solcast_key:
    try:
        df_fc = fetch_solcast_forecast(lat, lon, solcast_key)
        if df_fc is None or df_fc.empty:
            st.warning("Solcast key provided but fetch failed — using demo forecast.")
    except Exception:
        df_fc = None

# synthetic fallback
if df_fc is None:
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(now - timedelta(hours=12), periods=72, freq="1h")
    hours = index.hour + index.minute/60.0
    ghi_vals = np.maximum(0, 900 * np.sin((hours - 6) * np.pi / 12) + np.random.normal(0, 40, len(index)))
    df_fc = pd.DataFrame({"Time": index, "GHI": ghi_vals})

# compute Power_kW from GHI and system_kw
SYSTEM_EFFICIENCY = 0.85
df_fc = df_fc.sort_values("Time").reset_index(drop=True)
df_fc["Power_kW"] = (df_fc["GHI"] / 1000.0) * system_kw * SYSTEM_EFFICIENCY

# -----------------------
# Evening load estimate (simple consumer-friendly)
# -----------------------
per_person_kw = 0.35
fridge_kw = 0.15
tv_kw = 0.10
wifi_kw = 0.02
phone_kw = 0.05
cook_kw = 1.2 if cook_electric else 0.0
evening_load_kw = household_size * per_person_kw + fridge_kw + tv_kw + wifi_kw + phone_kw + cook_kw

# -----------------------
# AI scheduler: multi-cycle heating + battery simulation (solar-only charging)
# -----------------------
def simulate_multi_cycle(forecast, now_dt, battery_total_kwh, initial_soc_frac,
                         charger_eff, inverter_eff, geyser_kw, geyser_h):
    """
    Returns schedule_summary and timeline details.
    - forecast: df with Time, Power_kW (hourly or variable intervals)
    - battery_total_kwh: total battery capacity (kWh)
    - initial_soc_frac: starting fraction of battery (0-1)
    - Assumes battery charges only from solar (no grid charging)
    """
    # initialize battery energy (kWh)
    battery_energy = battery_total_kwh * initial_soc_frac
    reserve_kwh = battery_total_kwh * RESERVE_FRACTION
    usable_capacity_kwh = battery_total_kwh - reserve_kwh

    # define cycle windows (morning, midday, evening)
    # morning: 06:00-09:30, midday: 11:00-14:00, evening: 16:30-19:30
    # We'll find the local peak times inside these windows and attempt to schedule there.
    windows = {
        "morning": (6, 9.5),
        "midday": (11, 14),
        "evening": (16.5, 19.5),
    }

    # helper: find best index in a time range that has max Power_kW
    def best_index_in_range(df, start_hour, end_hour, ref_day):
        # consider range across next 2 days to find next occurrence
        candidates = df[(df["Time"] >= ref_day) & (df["Time"] < ref_day + timedelta(days=2))]
        if candidates.empty:
            return None
        # convert to local hour float
        candidates["hour_float"] = candidates["Time"].dt.hour + candidates["Time"].dt.minute / 60.0
        mask = (candidates["hour_float"] >= start_hour) & (candidates["hour_float"] <= end_hour)
        subset = candidates[mask]
        if subset.empty:
            return None
        idx = subset["Power_kW"].idxmax()
        return int(idx)

    # search horizon: now -> now + 48h for scheduling cycles
    now_time = now_dt
    horizon_end = now_dt + timedelta(days=2)
    fut = forecast[(forecast["Time"] >= now_time) & (forecast["Time"] <= horizon_end)].reset_index(drop=True)
    # compute step durations
    durations = []
    for i in range(len(fut)):
        if i < len(fut)-1:
            dh = (fut.loc[i+1,"Time"] - fut.loc[i,"Time"]).total_seconds() / 3600.0
            if dh <= 0:
                dh = 1.0
        else:
            dh = durations[-1] if durations else 1.0
        durations.append(dh)

    schedule = []
    timeline = []  # will collect rows of simulated battery progression
    # Process windows morning -> midday -> evening
    for name, (sh, eh) in windows.items():
        idx = best_index_in_range(forecast, sh, eh, now_time)
        if idx is None:
            continue
        # convert global idx in forecast to fut index
        # find fut index where Time == forecast.loc[idx,"Time"]
        start_time = forecast.loc[idx, "Time"]
        fut_idx = fut.index[fut["Time"] == start_time]
        if len(fut_idx) == 0:
            # maybe index not in fut (out of our local truncated df) -> skip
            continue
        j = int(fut_idx[0])

        # simulate charging from previous last simulated time up to j (store surplus to battery)
        # We'll maintain last_sim_time index pointer; initialize at 0
        last_pointer = timeline[-1]["fut_index"]+1 if timeline else 0
        # collect charging steps from last_pointer to j-1
        for i in range(last_pointer, min(j, len(fut))):
            prod_kwh = float(fut.loc[i, "Power_kW"]) * durations[i]
            # assume daytime non-critical loads negligible for charging; all surplus stored
            storeable = max(0.0, prod_kwh) * charger_eff
            remaining_capacity = max(0.0, battery_total_kwh - battery_energy)
            stored = min(storeable, remaining_capacity)
            battery_energy += stored
            timeline.append({
                "Time": fut.loc[i,"Time"],
                "event": "charge",
                "prod_kwh": prod_kwh,
                "stored_kwh": stored,
                "battery_kwh": battery_energy,
                "fut_index": i
            })

        # now simulate geyser run starting at fut index j for geyser_h hours
        required_from_batt = 0.0
        hours_remaining = geyser_h
        k = j
        # collect run details
        run_blocks = []
        while hours_remaining > 0 and k < len(fut):
            step_h = durations[k]
            use_h = min(step_h, hours_remaining)
            prod_kwh = float(fut.loc[k,"Power_kW"]) * use_h
            geyser_out_kwh = geyser_kw * use_h
            # direct solar covers part of geyser
            if prod_kwh >= geyser_out_kwh:
                direct = geyser_out_kwh
                deficit = 0.0
            else:
                direct = prod_kwh
                deficit = geyser_out_kwh - prod_kwh
            # battery must supply deficit / inverter_eff (discharging loss)
            batt_supply = deficit / inverter_eff
            # ensure battery doesn't go below reserve
            available_for_discharge = max(0.0, battery_energy - reserve_kwh)
            actual_supply = min(batt_supply, available_for_discharge)
            if actual_supply < batt_supply:
                # cannot supply full deficit -> run cannot be fully off-grid here
                required_from_batt = None
                break
            battery_energy -= actual_supply
            run_blocks.append({
                "Time": fut.loc[k,"Time"],
                "prod_kwh": prod_kwh,
                "direct_to_geyser_kwh": direct,
                "batt_supply_kwh": actual_supply,
                "battery_kwh_after": battery_energy,
                "fut_index": k
            })
            hours_remaining -= use_h
            k += 1

        # if run_blocks completed and hours_remaining == 0 -> successful off-grid run
        if hours_remaining <= 0:
            # record schedule and attach run_blocks to timeline
            schedule.append({
                "cycle": name,
                "start_time": fut.loc[j,"Time"],
                "blocks": run_blocks
            })
            # append run_blocks to timeline (already adjusted battery_energy)
            for rb in run_blocks:
                timeline.append({
                    "Time": rb["Time"],
                    "event": "geyser_run",
                    "prod_kwh": rb["prod_kwh"],
                    "stored_kwh": 0.0,
                    "battery_kwh": rb["battery_kwh_after"],
                    "fut_index": rb["fut_index"]
                })
        else:
            # couldn't run off-grid for this window, skip
            continue

    # After scheduling attempts, estimate recharge time to restore battery to usable capacity (battery_total_kwh - reserve)
    target_level = battery_total_kwh - reserve_kwh
    # sim from last timeline index forward until battery_energy reaches target_level or horizon end
    last_idx = timeline[-1]["fut_index"]+1 if timeline else 0
    recharge_start_time = None
    recharge_end_time = None
    simulated_energy = battery_energy
    for i in range(last_idx, len(fut)):
        prod_kwh = float(fut.loc[i,"Power_kW"]) * durations[i]
        # during recharge we must meet ongoing small household daytime loads; we ignore for simplicity (assume minimal)
        storeable = max(0.0, prod_kwh) * charger_eff
        remaining = max(0.0, battery_total_kwh - simulated_energy)
        stored = min(storeable, remaining)
        if stored > 0 and recharge_start_time is None:
            recharge_start_time = fut.loc[i,"Time"]
        simulated_energy += stored
        timeline.append({
            "Time": fut.loc[i,"Time"],
            "event": "recharge",
            "prod_kwh": prod_kwh,
            "stored_kwh": stored,
            "battery_kwh": simulated_energy,
            "fut_index": i
        })
        if simulated_energy >= target_level - 1e-6:
            recharge_end_time = fut.loc[i,"Time"]
            break

    # compute battery SoC percent before & after each scheduled cycle for user-friendly display
    def soc_percent(kwh):
        return max(0.0, min(100.0, (kwh / battery_total_kwh) * 100.0))

    schedule_summary = []
    # To compute battery at start of each cycle, we need to re-simulate from initial to each start_time
    # We'll compute battery at each cycle's start by scanning timeline entries
    for s in schedule:
        # find earliest timeline entry with fut_index == start fut index
        start_idx = s["blocks"][0]["fut_index"]
        # find timeline row with fut_index == start_idx and event either charge or geyser_run before run
        battery_before = None
        for row in timeline:
            if row["fut_index"] == start_idx:
                # battery_kwh stored here is after processing this fut index; we want value before run
                # So find previous row's battery_kwh if exists
                prev_idx = timeline.index(row) - 1
                if prev_idx >= 0:
                    battery_before = timeline[prev_idx]["battery_kwh"]
                else:
                    # no previous, use initial battery energy assumption
                    battery_before = battery_total_kwh * initial_soc_frac
                break
        if battery_before is None:
            battery_before = battery_total_kwh * initial_soc_frac
        battery_after = s["blocks"][-1]["battery_kwh_after"]
        schedule_summary.append({
            "cycle": s["cycle"],
            "start_time": s["start_time"],
            "battery_before_kwh": round(battery_before, 2),
            "battery_after_kwh": round(battery_after, 2),
            "battery_before_pct": round(soc_percent(battery_before), 1),
            "battery_after_pct": round(soc_percent(battery_after), 1)
        })

    # recharge time strings
    if recharge_start_time and recharge_end_time:
        recharge_duration = (recharge_end_time - recharge_start_time).total_seconds() / 3600.0
    else:
        recharge_duration = None

    results = {
        "schedule_summary": schedule_summary,
        "timeline": pd.DataFrame(timeline),
        "battery_at_end_kwh": round(simulated_energy, 2),
        "recharge_start": recharge_start_time,
        "recharge_end": recharge_end_time,
        "recharge_duration_h": recharge_duration
    }
    return results

# -----------------------
# User action: Simulate AI Detection
# -----------------------
st.markdown("### 2) Test AI (Simulate detection & scheduling)")
simulate_btn = st.button("🔎 Simulate AI Detection")

# assume an initial SoC (demo-friendly) — AI could estimate from day history; we'll assume 40% start
initial_soc_frac = 0.40

if simulate_btn:
    now_dt = datetime.now().replace(minute=0, second=0, microsecond=0)
    results = simulate_multi_cycle(df_fc, now_dt, battery_kwh, initial_soc_frac,
                                   CHARGER_EFF, INVERTER_EFF, geyser_power_kw, geyser_duration_h)

    st.subheader("🔆 AI Scheduling Results (multi-cycle)")
    schedule_summary = results["schedule_summary"]
    if schedule_summary:
        for s in schedule_summary:
            st.markdown(f"**{s['cycle'].capitalize()} cycle** — Start: **{s['start_time'].strftime('%a %d %b %I:%M %p')}**")
            st.write(f"- Battery before: {s['battery_before_kwh']} kWh ({s['battery_before_pct']}%)")
            st.write(f"- Battery after: {s['battery_after_kwh']} kWh ({s['battery_after_pct']}%)")
    else:
        st.info("AI did not find any full off-grid cycle windows within the next 48 hours for your geyser size.")

    # Show recharge info
    if results["recharge_duration_h"] is not None:
        rs = results["recharge_start"].strftime("%a %d %b %I:%M %p")
        re = results["recharge_end"].strftime("%a %d %b %I:%M %p")
        st.markdown(f"**Solar-only recharge:** starts ~{rs}, finishes ~{re} (≈ {results['recharge_duration_h']:.1f} hours)")
    else:
        st.markdown("**Solar-only recharge:** not achieved within forecast horizon (insufficient solar surplus).")

    st.markdown("---")
    # battery SoC at end of simulated horizon
    st.write(f"Estimated battery at end of simulation: **{results['battery_at_end_kwh']:.2f} kWh** " +
             f"(Reserve {RESERVE_FRACTION*100:.0f}% not used)")

    # Money saved for each run and projections
    event_kwh = geyser_event_kwh
    if event_kwh > 0:
        saving_per_event = event_kwh * tariff_per_kwh
        st.markdown("### 💰 Estimated Savings")
        st.write(f"- Savings this geyser run: **R{saving_per_event:.2f}**")
        st.write(f"- Projected: **R{saving_per_event:.2f}/day**, **R{saving_per_event*7:.2f}/week**, **R{saving_per_event*30:.2f}/month**")

    # Show simplified evening backup runtime estimate using battery at arrival
    # Compute battery at arrival by simulating charging from now until arrival_time (if arrival later today)
    arrive_dt = datetime.combine(now_dt.date(), arrival_time)
    if arrive_dt <= now_dt:
        arrive_dt += timedelta(days=1)
    # simulate simple charge to arrival from now (no geyser cycles unless scheduled before arrival)
    battery_energy_for_arrival = battery_kwh * initial_soc_frac
    fut_arrival = df_fc[(df_fc["Time"] >= now_dt) & (df_fc["Time"] < arrive_dt)].reset_index(drop=True)
    for i in range(len(fut_arrival)):
        prod_kwh = float(fut_arrival.loc[i,"Power_kW"]) * 1.0
        # store surplus to battery
        storeable = max(0.0, prod_kwh) * CHARGER_EFF
        battery_energy_for_arrival = min(battery_kwh, battery_energy_for_arrival + storeable)
    usable_at_arrival = max(0.0, battery_energy_for_arrival - battery_kwh * RESERVE_FRACTION)
    runtime_h = (usable_at_arrival * INVERTER_EFF) / max(0.01, evening_load_kw)
    st.markdown("### 🏠 Evening backup estimate")
    st.write(f"- Estimated battery at arrival: **{battery_energy_for_arrival:.2f} kWh** (usable ≈ {usable_at_arrival:.2f} kWh after reserve)")
    st.write(f"- Estimated evening load: **{evening_load_kw:.2f} kW**")
    st.write(f"- Estimated backup runtime if outage occurs at arrival: **{runtime_h:.2f} hours** (~{int(runtime_h*60)} minutes)")

    # show timeline preview (small)
    if not results["timeline"].empty:
        st.markdown("### 🔎 Simulation timeline (preview)")
        preview = results["timeline"][["Time","event","prod_kwh","stored_kwh","battery_kwh"]].copy()
        preview["Time"] = preview["Time"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(preview.head(40), use_container_width=True)

# -----------------------
# 24h Forecast graph (hourly ticks + range slider)
# -----------------------
st.markdown("### ☀️ 24-hour forecast")
now = datetime.now().replace(minute=0, second=0, microsecond=0)
df_24 = df_fc[(df_fc["Time"] >= now) & (df_fc["Time"] < now + timedelta(days=1))].copy()
fig = px.line(df_24, x="Time", y="GHI", title=f"Forecast — {loc}", labels={"GHI":"Irradiance (W/m²)"})
fig.update_traces(line=dict(width=3), mode="lines+markers", marker=dict(size=6))
fig.update_layout(xaxis=dict(dtick=3600000, tickformat="%H:%M", rangeslider=dict(visible=True)),
                  margin=dict(l=20,r=20,t=40,b=40), height=460)
st.plotly_chart(fig, use_container_width=True)

# -----------------------
# End (no extra disclaimers)
# -----------------------
