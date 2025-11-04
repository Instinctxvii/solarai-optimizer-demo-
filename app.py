import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# === LOCATION BUTTON AT TOP ===
st.markdown("### Select Location")
col_loc1, col_loc2 = st.columns(2)
with col_loc1:
    if st.button("Limpopo (Polokwane)", type="secondary", use_container_width=True):
        st.session_state.location = "limpopo"
with col_loc2:
    if st.button("Nelspruit (Mpumalanga)", type="secondary", use_container_width=True):
        st.session_state.location = "nelspruit"

# Default location
if 'location' not in st.session
