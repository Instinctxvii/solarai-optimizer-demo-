import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests

# Test Solcast integration
def get_solcast_forecast(lat=-26.2041, lon=28.0473, api_key='demo'):
    if api_key == 'demo':
        # Fallback to demo data for test
        now = datetime.now()
        index = pd.date_range(now, periods=336, freq='H')
        hours = index.hour
        seasonal = 1.2 if now.month in [11,12,1,2] else 0.8
        ghi = np.maximum(0, 800 * np.sin((hours - 12) * np.pi / 12) * seasonal + np.random.normal(0, 50, len(index)))
        df = pd.DataFrame({'ghi': ghi}, index=index).resample('H').mean()
        return df.reset_index().head(5)  # Test 5 rows

    # Real API call (for future)
    url = f"https://api.solcast.com.au/radiation/forecasts?latitude={lat}&longitude={lon}&api_key={api_key}&format=json"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()['forecasts']
            df = pd.DataFrame(data)
            df['period_end'] = pd.to_datetime(df['period_end'])
            return df[['period_end', 'ghi']].set_index('period_end').tail(336).reset_index()
    except:
        pass
    return pd.DataFrame({'period_end': [], 'ghi': []})

# Test run
df_test = get_solcast_forecast()
print(df_test)
