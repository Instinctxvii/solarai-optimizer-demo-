import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
import random

# === CONFIG ===
st.set_page_config(page_title="SolarcallAI™", layout="wide")

# === REFRESH BUTTON ===
if st.button("Refresh Demo (See Latest Changes)", type="primary", use_container_width=True):
    st.success("Refreshing... Page will reload in 2 seconds.")
    time.sleep(2)
    st.rerun()

# === TITLE ===
st.title("SolarcallAI™")
st.markdown("**AI Solar Geyser Control | R149/month | R0 Upfront**")

# === FULL SA STREET + SUBURB SEARCH ===
st.markdown("### Enter Your Street or Suburb")

search_query = st.text_input(
    "Search any street or suburb in South Africa",
    placeholder="Type street or suburb...",
    key="search_input"
)

# === LIVE SEARCH LOGIC ===
if search_query and len(search_query) > 2:
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": search_query,
                "format": "json",
                "limit": 10,
                "countrycodes": "za",
                "addressdetails": 1
            },
            headers={"User-Agent": "SolarcallAI/1.0"},
            timeout=5
        )
        results = response.json()
        
        if results:
            options = []
            seen = set()
            for r in results:
                addr = r.get("address", {})
                house = addr.get("house_number", "")
                road = addr.get("road", addr.get("pedestrian", ""))
                suburb = addr.get("suburb", addr.get("neighbourhood", addr.get("village", addr.get("hamlet", ""))))
                city = addr.get("city", addr.get("town", addr.get("municipality", "")))
                province = addr.get("province", addr.get("state", ""))
                
                parts = [p for p in [house, road, suburb, city, province] if p]
                display = ", ".join(parts) if parts else r.get("display_name", "Unknown")
                
                if display not in seen:
                    seen.add(display)
                    lat = float(r["lat"])
                    lon = float(r["lon"])
                    options.append((display, lat, lon))
            
            # === CUSTOM FULL-TEXT DROPDOWN ===
            if options:
                # Create a unique key for this session
                dropdown_key = f"location_select_{hash(search_query)}"
                
                # Use HTML + JS for full-width, scrollable dropdown
                dropdown_html = """
                <style>
                .full-dropdown {
                    width: 100%;
                    max-height: 300px;
                    overflow-y: auto;
                    border: 1px solid #444;
                    border-radius: 8px;
                    background: #1e1e1e;
                    padding: 8px;
                    font-size: 14px;
                    color: white;
                }
                .dropdown-option {
                    padding: 10px;
                    border-bottom: 1px solid #333;
                    cursor: pointer;
                    white-space: normal;
                    word-wrap: break-word;
                }
                .dropdown-option:hover {
                    background: #333;
                }
                .dropdown-option:last-child {
                    border-bottom: none;
                }
                </style>
                <div class="full-dropdown" id="dropdown">
                """
                
                for i, (name, lat, lon) in enumerate(options):
                    js_action = f"window.parent.postMessage({{type: 'select_location', index: {i}}}, '*');"
                    dropdown_html += f"""
                    <div class="dropdown-option" onclick="{js_action}">
                        {name}
                    </div>
                    """
                
                dropdown_html += "</div>"
                
                # Render dropdown
                dropdown_component = st.components.v1.html(
                    dropdown_html + f"""
                    <script>
                    // Listen for selection
                    window.addEventListener('message', function(event) {{
                        if (event.data.type === 'select_location') {{
                            const index = event.data.index;
                            const locations = {options};
                            const selected = locations[index];
                            // Send to Streamlit
                            window.parent.postMessage({{
                                type: 'streamlit:setComponentValue',
                                key: '{dropdown_key}',
                                value: selected[0] + '|' + selected[1] + '|' + selected[2]
                            }}, '*');
                        }}
                    }});
                    </script>
                    """,
                    height=320
                )
                
                # Capture selection via session state
                if st.session_state.get(dropdown_key):
                    value = st.session_state[dropdown_key]
                    name, lat, lon = value.split('|')
                    lat, lon = float(lat), float(lon)
                    st.session_state.location_name = name
                    st.session_state.lat = lat
                    st.session_state.lon = lon
                    st.success(f"Selected: {name}")
                    del st.session_state[dropdown_key]
                    st.rerun()
                    
        else:
            st.warning("No SA locations found. Try 'Clivia', 'Soweto', or '123 Main St'.")
    except Exception as e:
        st.error(f"Search failed: {e}")

# === FALLBACK LOCATION ===
if 'location_name' not in st.session_state:
    st.session_state.location_name = "Limpopo (Polokwane)"
    st.session_state.lat = -23.8962
    st.session_state.lon = 29.4486

st.markdown(f"**Current Location: {st.session_state.location_name}**")

# === FORECAST RANGE & RESET ===
col_range, col_reset = st.columns([1, 1])
with col_range:
    days = st.radio("Forecast Range", [7, 14], horizontal=True, index=1)
with col_reset:
    if st.button("Reset Graph View", type="secondary"):
        st.success("Graph reset!")
        st.rerun()

# === REAL SOLAR FORECAST ===
@st.cache_data(ttl=3600)
def get_real_solar_forecast(lat, lon, days=14):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "direct_normal_irradiance",
        "forecast_days": days,
        "timezone": "Africa/Johannesburg"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        df = pd.DataFrame({
            "Time": pd.to_datetime(data["hourly"]["time"]),
            "Solar Yield (W/m²)": data["hourly"]["direct_normal_irradiance"]
        })
        return df
    except:
        now = datetime.now()
        index = pd.date_range(now, periods=days*24, freq='h')
        hours = index.hour
        ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) + np.random.normal(0, 50, len(index)))
        return pd.DataFrame({'Time': index, 'Solar Yield (W/m²)': ghi})

df = get_real_solar_forecast(st.session_state.lat, st.session_state.lon, days=days)

# === SIMULATED POWER ===
def get_current_power():
    hour = datetime.now().hour
    return random.randint(850, 1200) if 11 <= hour <= 14 else random.randint(100, 500)

# === CONTROL ===
def control_geyser():
    power = get_current_power()
    if power > 800:
        st.success("GEYSER ON — 100% Solar Power!")
        st.success("SMS SENT: Geyser ON — 2hr hot water (free!)")
    else:
        st.warning("Geyser OFF — Low sun")

# === SIDEBAR ===
st.sidebar.header("Your Solar Setup")
system_size_kw = st.sidebar.slider("Panel Size (kW)", 1, 10, 5)
hours_used_per_day = st.sidebar.slider("Geyser Usage (hours/day)", 4, 12, 6)
tariff_per_kwh = st.sidebar.number_input("Electricity Cost (R/kWh)", 2.0, 6.0, 2.50)

# === CALCULATIONS ===
avg_ghi = df['Solar Yield (W/m²)'].mean()
daily_solar_kwh = (avg_ghi / 1000) * system_size_kw * 5
total_solar_kwh = daily_solar_kwh * days
used_kwh = system_size_kw * hours_used_per_day * days
saved_kwh = min(total_solar_kwh, used_kwh)
saved_r = saved_kwh * tariff_per_kwh
weekly_savings = saved_r / days

next_24h = df.head(24)
best_hour = next_24h['Solar Yield (W/m²)'].idxmax()
best_time = pd.Timestamp(df.loc[best_hour, 'Time']).strftime("%I:%M %p")

# === INTERACTIVE GRAPH ===
fig = px.line(
    df, x='Time', y='Solar Yield (W/m²)',
    title=f"{days}-Day AI Solar Forecast — {st.session_state.location_name}",
    labels={'Solar Yield (W/m²)': 'Sunlight (W/m²)'}
)
fig.update_layout(
    height=450,
    hovermode='x unified',
    dragmode='zoom',
    title_x=0.5,
    xaxis=dict(
        rangeselector=dict(buttons=[
            dict(count=1, label="1d", step="day", stepmode="backward"),
            dict(count=7, label="7d", step="day", stepmode="backward"),
            dict(step="all")
        ]),
        rangeslider=dict(visible=True),
        type="date"
    )
)

config = {
    'toImageButtonOptions': {
        'format': 'png',
        'filename': f'SolarcallAI_{st.session_state.location_name.replace(", ", "_").replace(" ", "_")}'
    },
    'displaylogo': False
}

st.plotly_chart(fig, use_container_width=True, config=config)

if st.button("Simulate Geyser Control", type="primary", use_container_width=True):
    control_geyser()

st.markdown("**Controls:** Drag to zoom • Double-tap to reset • Save PNG (top-right)")

# === INSIGHTS ===
col1, col2 = st.columns(2)
with col1:
    st.metric("Best Charge Time", best_time)
    st.metric("Money Saved", f"R{saved_r:.0f}", f"R{weekly_savings:.0f}/week")
with col2:
    st.metric(f"{days}-Day Solar", f"{total_solar_kwh:.1f} kWh", f"{daily_solar_kwh:.1f} kWh/day")
    st.metric("Current Solar", f"{get_current_power()}W", "Peak Sun")

st.info(f"AI says: **Charge at {best_time}** in **{st.session_state.location_name}** — Save R{saved_r:.0f} in {days} days!")

st.caption("© 2025 SolarcallAI (Pty) Ltd | info@solarcallai.co.za | Powered by Open-Meteo")
