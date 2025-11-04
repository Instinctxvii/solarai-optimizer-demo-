import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# === PAGE CONFIG ===
st.set_page_config(page_title="SolarAI Optimizer™", layout="wide")

# === STYLING (kept polished look) ===
st.markdown(
    """
<style>
html, body, [class*="css"] { font-family: "Inter", sans-serif; color: #222; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #fdfdfd 0%, #f5f7fa 100%); border-right: 1px solid #e5e5e5; }
section[data-testid="stSidebar"] h2, h3, label { color: #1e3a8a; font-weight: 600; }
[data-baseweb="slider"] > div { background: linear-gradient(90deg, #007bff 0%, #00c6ff 100%) !important; height: 6px !important; border-radius: 10px !important; }
[data-baseweb="slider"] [role="slider"] { height: 22px !important; width: 22px !important; background: radial-gradient(circle at 30% 30%, #fff 0%, #e6f0ff 70%, #007bff 100%) !important; border: 2px solid #007bff !important; box-shadow: 0px 0px 6px rgba(0, 123, 255, 0.5); }
.js-plotly-plot .plotly .rangeslider { fill: #e9f3ff !important; stroke: #007bff !important; stroke-width: 0.6; }
.js-plotly-plot .plotly .rangeslider .handle { fill: #007bff !important; stroke: #004aad !important; }
h1, h2, h3 { font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)

# === LOCATION BUTTONS ===
st.markdown("### 🌍 Select Location")
col_loc1, col_loc2 = st.columns(2)
with col_loc1:
    if st.button("📍 Limpopo (Polokwane)", use_container_width=True):
        st.session_state.location = "limpopo"
with col_loc2:
    if st.button("🌞 Nelspruit (Mbombela)", use_container_width=True):
        st.session_state.location = "nelspruit"

if "location" not in st.session_state:
    st.session_state.location = "limpopo"

# === RESET / REFRESH BUTTON ===
if st.button("🔄 Reset / Refresh", use_container_width=True):
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

# === HEADER ===
st.title("☀️ SolarAI Optimizer™")
st.markdown("**AI-Powered Solar Intelligence | R99/month**")

# === LOCATION COORDINATES ===
locations = {
    "limpopo": {"name": "Limpopo (Polokwane)", "lat": -23.8962, "lon": 29.4486},
    "nelspruit": {"name": "Nelspruit (Mbombela)", "lat": -25.4753, "lon": 30.9694},
}
loc = locations[st.session_state.location]
st.markdown(f"**📡 Current Location:** {loc['name']}")

# === FETCH DATA ===
@st.cache_data(ttl=3600, show_spinner=False)
def get_solcast_forecast(lat: float, lon: float, api_key: str = "demo") -> pd.DataFrame:
    """Return solar irradiance (GHI) forecast for 14 days (hourly)."""
    try:
        if api_key and api_key != "demo":
            url = (
                f"https://api.solcast.com.au/radiation/forecasts?"
                f"latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
            )
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()["forecasts"]
            df = pd.DataFrame(data)
            df["Time"] = pd.to_datetime(df["period_end"])
            df["Solar Yield (W/m²)"] = df["ghi"]
            return df[["Time", "Solar Yield (W/m²)"]].tail(336)
    except Exception:
        st.warning("⚠️ API unavailable — using demo data.")

    # demo synthetic hourly data (14 days)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(now - timedelta(days=14), now + timedelta(days=1), freq="1h")
    hours = index.hour + index.minute / 60
    seasonal = 1.2 if now.month in [11, 12, 1, 2] else 0.8
    ghi = np.maximum(
        0,
        800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 40, len(index)),
    )
    return pd.DataFrame({"Time": index, "Solar Yield (W/m²)": ghi})

# === SIDEBAR: System, Battery, Geyser, Household loads, Loadshedding scenario ===
st.sidebar.header("⚙️ System, Battery & Loads")

# System & rates
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.5)
solcast_key = st.sidebar.text_input("Solcast API Key (optional)", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("🔋 Battery & Inverter")
battery_ah = st.sidebar.number_input("Battery Capacity (Ah)", min_value=50, max_value=5000, value=200, step=10)
battery_voltage = st.sidebar.selectbox("Battery Nominal Voltage (V)", options=[12, 24, 48], index=2)
battery_soc_percent = st.sidebar.slider("Current Battery SoC (%)", 0, 100, 50)
inverter_eff_percent = st.sidebar.slider("Inverter Efficiency (%)", 70, 98, 90)
charger_eff_percent = st.sidebar.slider("Charger Efficiency (%)", 70, 98, 95)
reserve_soc_percent = st.sidebar.slider("Reserve SoC (%) — keep this much as buffer (%)", 0, 50, 10)

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Geyser")
geyser_power_kw = st.sidebar.number_input("Geyser Power (kW)", min_value=0.5, max_value=8.0, value=3.5, step=0.1)
geyser_duration_h = st.sidebar.number_input("Geyser Duration (hours)", min_value=0.25, max_value=4.0, value=1.0, step=0.25)
geyser_use_during_loadshedding = st.sidebar.checkbox("Allow geyser to run during loadshedding?", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🏠 Household Loads")
baseline_load_kw = st.sidebar.number_input("Baseline household load (kW) — lights/fridge/phones", min_value=0.0, max_value=10.0, value=0.5, step=0.1)
fridge_kw = st.sidebar.number_input("Fridge (kW) estimate (peak)", min_value=0.0, max_value=2.0, value=0.15, step=0.01)
phone_charging_kw = st.sidebar.number_input("Phone charging (kW) estimate", min_value=0.0, max_value=1.0, value=0.05, step=0.01)
cooking_kw = st.sidebar.number_input("Cooking (kW) estimate (if using electric cooking)", min_value=0.0, max_value=3.0, value=0.0, step=0.1)

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Loadshedding Scenario (for sizing)")
loadshedding_hours = st.sidebar.slider("Expected loadshedding duration (hours)", 1, 24, (6), step=1)
safety_margin_percent = st.sidebar.slider("Sizing safety margin (%)", 0, 100, 20)

# Convert percents
inverter_eff = inverter_eff_percent / 100.0
charger_eff = charger_eff_percent / 100.0
battery_soc = battery_soc_percent / 100.0
reserve_soc = reserve_soc_percent / 100.0
safety_margin = safety_margin_percent / 100.0

# === FETCH FORECAST DATA ===
df = get_solcast_forecast(loc["lat"], loc["lon"], api_key=solcast_key)

# === VIEW TOGGLE ===
view_mode = st.radio("📊 Select View:", ["24 Hours (Today)", "14-Day Forecast"], horizontal=True)

# === FILTER VIEW ===
now = datetime.now()
today = now.date()
start_of_day = datetime.combine(today, datetime.min.time())
end_of_day = start_of_day + timedelta(days=1)

if view_mode == "24 Hours (Today)":
    df_view = df[(df["Time"] >= start_of_day) & (df["Time"] < end_of_day)].reset_index(drop=True)
else:
    df_view = df.copy().reset_index(drop=True)

# === Add instantaneous production (kW) and an estimated household load profile per interval ===
df_view["Power_kW"] = (df_view["Solar Yield (W/m²)"] / 1000.0) * system_size_kw

# For simplicity we'll assume household load is mostly steady, with small additions:
# total household load (kW) used in simulation:
household_load_kw = baseline_load_kw + fridge_kw + phone_charging_kw + cooking_kw

# === SIMPLE AGGREGATE CALCULATIONS FOR DASHBOARD ===
avg_ghi = df_view["Solar Yield (W/m²)"].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * 14
used_kwh = system_size_kw * 6 * 14  # approximate
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh

# === Helper: battery capacity & conversions ===
def battery_capacity_kwh(ah: float, voltage: float) -> float:
    return (ah * voltage) / 1000.0

def ah_from_kwh(kwh: float, voltage: float) -> float:
    return (kwh * 1000.0) / voltage

# === SIZING HELPER: Recommend battery given loadshedding duration & loads ===
def recommend_battery(baseload_kw, extra_kw, duration_h, inverter_eff, voltage, reserve_soc, safety_margin):
    """
    Compute required kWh to run baseload + extra load for duration_h, then recommend Ah.
    - baseload_kw: baseline household
    - extra_kw: optional extra loads (e.g., geyser if included)
    """
    total_load_kw = baseload_kw + extra_kw
    # energy drawn from battery inclusive of inverter loss
    required_out_kwh = total_load_kw * duration_h
    # battery must provide required_out_kwh / inverter_eff (accounting for inverter loss)
    required_from_battery_kwh = required_out_kwh / inverter_eff
    # add reserve and safety margin
    required_from_battery_kwh *= (1.0 + safety_margin)
    # ensure reserve SoC is available after discharge: we will recommend capacity so usable portion excludes reserve
    usable_fraction = max(0.01, 1.0 - reserve_soc)  # fraction of battery you can use safely
    recommended_kwh_total = required_from_battery_kwh / usable_fraction
    recommended_ah = ah_from_kwh(recommended_kwh_total, voltage)
    return {
        "required_from_battery_kwh": required_from_battery_kwh,
        "recommended_kwh_total": recommended_kwh_total,
        "recommended_ah": recommended_ah,
        "usable_fraction": usable_fraction,
        "total_load_kw": total_load_kw,
    }

# === Simulation & Scheduling: include household loads in the forward simulation ===
def find_next_run_with_loads(forecast_df: pd.DataFrame,
                             now_dt: datetime,
                             batt_ah: float,
                             batt_v: float,
                             batt_soc_frac: float,
                             reserve_soc_frac: float,
                             inverter_eff: float,
                             charger_eff: float,
                             geyser_kw: float,
                             geyser_h: float,
                             household_load_kw: float,
                             allow_geyser_during_loadshedding: bool):
    """
    Simulate forward through forecast_df and find earliest timestamp where battery+forecast charging can:
      - cover baseline household loads continuously (no grid draw)
      - AND (if scheduling geyser) have enough to run geyser for geyser_h hours (while still sustaining household loads).
    Returns: (start_time or None, details)
    """
    # battery capacity and current energy
    batt_kwh = battery_capacity_kwh(batt_ah, batt_v)
    current_kwh = batt_kwh * batt_soc_frac

    # reserve: we will not discharge battery below reserve fraction of capacity
    reserve_kwh = batt_kwh * reserve_soc_frac
    usable_min_kwh = reserve_kwh  # battery must stay >= this

    # energy needed for geyser output (kWh)
    geyser_energy_out = geyser_kw * geyser_h
    # battery must supply more than geyser output to cover inverter inefficiency when discharging:
    geyser_required_from_batt_kwh = geyser_energy_out / inverter_eff

    # We'll step through future intervals (>= now_dt)
    future = forecast_df[forecast_df["Time"] >= now_dt].copy().reset_index(drop=True)
    if future.empty:
        return None, {"reason": "No future forecast available."}

    timeline = []
    # We'll maintain dynamic battery_kwh variable representing energy in battery at the start of each slot
    battery_kwh = current_kwh

    # For each step, simulate production -> serve load -> charge battery or discharge if net negative (still not allowed to go below reserve)
    for i in range(len(future)):
        t = future.loc[i, "Time"]
        # compute delta hours
        if i < len(future) - 1:
            delta_hours = (future.loc[i + 1, "Time"] - future.loc[i, "Time"]).total_seconds() / 3600.0
            if delta_hours <= 0:
                delta_hours = 1.0
        else:
            # assume same delta as previous or 1 hour
            delta_hours = (future.loc[i, "Time"] - future.loc[i - 1, "Time"]).total_seconds() / 3600.0 if i > 0 else 1.0
            if delta_hours <= 0:
                delta_hours = 1.0

        prod_kw = float(future.loc[i, "Power_kW"])
        prod_kwh = prod_kw * delta_hours

        # household consumption during interval (kWh)
        load_kwh = household_load_kw * delta_hours

        # If production >= load: surplus can charge battery (after charger eff)
        if prod_kwh >= load_kwh:
            surplus = prod_kwh - load_kwh
            storeable = surplus * charger_eff
            # store only up to remaining capacity
            remaining_cap = max(0.0, batt_kwh - battery_kwh)
            stored = min(storeable, remaining_cap)
            battery_kwh += stored
            grid_drawn = 0.0
            net_to_batt = stored
        else:
            # production less than load: deficit must be supplied from battery (discharging through inverter)
            deficit = load_kwh - prod_kwh
            # battery must discharge to cover deficit accounting for inverter efficiency (i.e. battery supplies deficit / inverter_eff)
            required_from_batt_for_load = deficit / inverter_eff
            # limit available discharge to battery_kwh - reserve
            available_for_discharge = max(0.0, battery_kwh - usable_min_kwh)
            discharged = min(required_from_batt_for_load, available_for_discharge)
            battery_kwh -= discharged
            grid_drawn = (required_from_batt_for_load - discharged)  # if >0 indicates grid would be needed
            net_to_batt = -discharged

        timeline.append({
            "Time": t,
            "prod_kwh": prod_kwh,
            "load_kwh": load_kwh,
            "battery_kwh": battery_kwh,
            "grid_drawn_kwh": grid_drawn,
            "delta_hours": delta_hours,
        })

        # If grid_drawn > 0 at any point before we run geyser, battery can't sustain loads alone — keep sim but note that true "no-grid" is violated
        # Now check if starting geyser at time t is possible:
        # To start geyser, battery must be able to supply geyser_required_from_batt_kwh plus keep household loads during geyser run without dropping below reserve.
        if allow_geyser_during_loadshedding:
            # We'll simulate a hypothetical geyser run starting at t: simulate intervals forward covering geyser_h hours
            # For simplicity, step through future rows from current i, accumulating production and loads and battery impact.
            batt_snapshot = battery_kwh
            hours_remaining = geyser_h
            j = i
            can_run = True
            # iterate while hours_remaining > 0
            while hours_remaining > 0 and j < len(future):
                # determine this interval duration (may be partial on final)
                if j < len(future) - 1:
                    step_hours = (future.loc[j + 1, "Time"] - future.loc[j, "Time"]).total_seconds() / 3600.0
                    if step_hours <= 0:
                        step_hours = 1.0
                else:
                    step_hours = delta_hours  # last known step
                use_hours = min(step_hours, hours_remaining)
                prod_kwh_j = float(future.loc[j, "Power_kW"]) * use_hours
                load_kwh_j = household_load_kw * use_hours
                geyser_out_kwh = geyser_kw * use_hours

                # energy for loads + geyser (output)
                total_out_kwh = load_kwh_j + geyser_out_kwh
                # battery must supply total_out_kwh / inverter_eff; production first, then battery covers remainder
                if prod_kwh_j >= total_out_kwh:
                    # production alone covers everything this interval -> battery unchanged (but can be charged)
                    # any surplus after loads+geyser could be stored (apply charger eff)
                    surplus_after = prod_kwh_j - total_out_kwh
                    storeable = surplus_after * charger_eff
                    remaining_cap = max(0.0, batt_kwh - batt_snapshot)
                    stored = min(storeable, remaining_cap)
                    batt_snapshot += stored
                else:
                    # production insufficient: deficit must be provided by battery (account for inverter eff)
                    deficit_j = total_out_kwh - prod_kwh_j
                    required_from_batt = deficit_j / inverter_eff
                    # if batt_snapshot - required_from_batt < usable_min_kwh -> cannot run
                    if batt_snapshot - required_from_batt < usable_min_kwh:
                        can_run = False
                        break
                    else:
                        batt_snapshot -= required_from_batt
                hours_remaining -= use_hours
                j += 1

            if can_run:
                # we found an earliest time t where starting the geyser won't drop battery below reserve throughout run
                return t, {"timeline": timeline, "battery_kwh_at_start": battery_kwh, "batt_kwh_total": batt_kwh}
        else:
            # if geyser not allowed during loadshedding, we only ensure battery can sustain household loads (no grid) — we may not schedule geyser
            pass

    # finished loop: not found
    return None, {"reason": "Insufficient forecasted solar+battery to run geyser without grid in forecast window.", "timeline": timeline, "battery_kwh_total": batt_kwh}

# === Run scheduling simulation ===
next_time, details = find_next_run_with_loads(
    forecast_df=df,
    now_dt=now,
    batt_ah=battery_ah,
    batt_v=battery_voltage,
    batt_soc_frac=battery_soc,
    reserve_soc_frac=reserve_soc,
    inverter_eff=inverter_eff,
    charger_eff=charger_eff,
    geyser_kw=geyser_power_kw,
    geyser_h=geyser_duration_h,
    household_load_kw=household_load_kw,
    allow_geyser_during_loadshedding=geyser_use_during_loadshedding,
)

if next_time is not None:
    best_time_str = pd.Timestamp(next_time).strftime("%a %d %b %I:%M %p")
else:
    best_time_str = "Not found in forecast"

# === Battery size recommendation for loadshedding scenario ===
# If user expects loadshedding for loadshedding_hours, compute required battery to run household_load and optionally geyser during that time.
extra_for_geyser = geyser_power_kw if geyser_use_during_loadshedding else 0.0
rec = recommend_battery(
    baseload_kw=baseline_load_kw,
    extra_kw=extra_for_geyser,
    duration_h=loadshedding_hours,
    inverter_eff=inverter_eff,
    voltage=battery_voltage,
    reserve_soc=reserve_soc,
    safety_margin=safety_margin,
)

# For user-friendly messages
current_batt_kwh = battery_capacity_kwh(battery_ah, battery_voltage)
current_usable_kwh = current_batt_kwh * (1.0 - reserve_soc)
rec_kwh = rec["recommended_kwh_total"]
rec_ah = rec["recommended_ah"]

# === GRAPH (3-hour ticks + slider) ===
fig = px.line(
    df_view,
    x="Time",
    y="Solar Yield (W/m²)",
    title=f"☀️ Global Horizontal Irradiance — {loc['name']} ({view_mode})",
    labels={"Solar Yield (W/m²)": "Yield (W/m²)", "Time": "Hour of Day"},
)
fig.update_traces(
    line=dict(color="rgba(0,123,255,0.75)", width=3),
    mode="lines+markers",
    marker=dict(size=6, color="rgba(0,123,255,0.8)", line=dict(width=1, color="white")),
    hovertemplate="Time: %{x|%H:%M}<br>Yield: %{y:.0f} W/m²<extra></extra>",
    line_shape="spline",
)
fig.update_layout(
    height=480,
    width=1050,
    margin=dict(l=30, r=30, t=60, b=80),
    title_x=0.5,
    plot_bgcolor="white",
    paper_bgcolor="white",
    hovermode="x unified",
    transition_duration=600,
    xaxis=dict(
        tickformat="%H:%M",
        dtick=3 * 3600000,
        showgrid=False,
        tickfont=dict(size=13),
        rangeslider=dict(visible=True, thickness=0.07, bgcolor="#e9f3ff"),
        range=[start_of_day, end_of_day],
        automargin=True,
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(200,200,200,0.3)",
        tickfont=dict(size=13),
    ),
)

# === MAIN LAYOUT ===
col1, col2 = st.columns([1.8, 1.2], gap="large")

with col1:
    st.subheader("🔆 Solar Yield Forecast")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
    st.markdown(
        """
**📘 Reading the Graph**
- **X-axis:** Time (hourly, every 3 h shown by default)  
- **Y-axis:** Sunlight intensity (W/m²)  
- Use the **slider below** to zoom to 2 h or 1 h windows for fine detail.
"""
    )

with col2:
    st.subheader("🤖 Live AI Insights (Battery-aware Scheduling)")

    if next_time is not None:
        st.metric("Next Best Time (AI)", best_time_str)
        st.success(
            f"AI: Battery + forecast charging will be sufficient by {best_time_str} to run geyser for {geyser_duration_h} h "
            f"without grid draw while covering household loads."
        )
    else:
        st.metric("Next Best Time (AI)", "Not found in forecast")
        st.warning(details.get("reason", "Insufficient energy in forecast window."))

    st.markdown("**Battery & loads summary**")
    st.write(f"- Current battery capacity: **{current_batt_kwh:.2f} kWh** ({battery_ah} Ah @ {battery_voltage} V)")
    st.write(f"- Current usable energy (after reserve {reserve_soc_percent}%): **{current_usable_kwh:.2f} kWh**")
    st.write(f"- Household load used in simulation: **{household_load_kw:.2f} kW** (baseline + fridge + phones + cooking)")
    st.write(f"- Geyser: **{geyser_power_kw:.2f} kW** for **{geyser_duration_h:.2f} h**, included during loadshedding: **{geyser_use_during_loadshedding}**")

    st.markdown("**Loadshedding sizing recommendation**")
    st.write(
        f"To sustain **{household_load_kw + (geyser_power_kw if geyser_use_during_loadshedding else 0):.2f} kW** "
        f"for **{loadshedding_hours} h**, recommended battery: **{rec_kwh:.2f} kWh total capacity" 
        f" ({rec_ah:.0f} Ah @ {battery_voltage} V)** including safety margin."
    )
    if rec["recommended_ah"] > battery_ah:
        st.warning(
            f"Your current {battery_ah} Ah battery is likely too small for the selected loadshedding scenario. "
            f"Consider upgrading to ~**{int(rec['recommended_ah'])} Ah** @ {battery_voltage} V or larger."
        )
    else:
        st.success("Your current battery is likely sufficient for the selected loadshedding scenario (per these assumptions).")

    st.metric("14-Day Solar", f"{total_solar_kwh:.1f} kWh", delta=f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Money Saved", f"R{saved_r:.0f}", delta=f"≈ R{saved_r/14:.0f}/day")

    # Debug timeline
    if st.checkbox("Show scheduling timeline (debug)", value=False):
        if "timeline" in details:
            st.dataframe(pd.DataFrame(details["timeline"]))
        else:
            st.write(details.get("reason", "No timeline available."))

    if st.button("⚡ Simulate Charge Now", use_container_width=True):
        if next_time is not None:
            st.success(f"Geyser scheduled for {best_time_str}. Mini-inverter + battery will supply it (per simulation).")
        else:
            st.error("No suitable run time found in forecast window; consider increasing battery size or shifting usage.")

# === FOOTER ===
st.markdown("---")
if next_time is not None:
    st.info(f"💡 AI Suggestion: Start geyser at **{best_time_str}** (battery + inverter) to avoid grid draw.")
else:
    st.info(
        "💡 AI Suggestion: No suitable time found in forecast window — consider charging battery earlier, increasing capacity, "
        "or reducing household loads during loadshedding."
    )
st.caption("R1 200 Raspberry Pi + AI | R99/month | Contact: **Keanu.kruger05@gmail.com**")
