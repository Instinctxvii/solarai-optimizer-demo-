# solarai_pi5.py — FINAL PRODUCTION CODE
# Runs 24/7 on Raspberry Pi 5 (8GB) — OFF-GRID, AI-DRIVEN, SMS-ONLY
# No mobile app. No WiFi. No Eskom. No battery drain.

import RPi.GPIO as GPIO
import time
import requests
from ina219 import INA219
import logging

# ==================== CONFIG ====================
RELAY_PIN = 17
SOLCAST_API_KEY = "YOUR_SOLCAST_KEY"  # Free tier
LATITUDE = -26.2041   # Johannesburg (auto-detect later)
LONGITUDE = 28.0473
CLICKATELL_API = {
    "api_id": "YOUR_ID",
    "user": "your_user",
    "password": "your_pass",
    "to": "27xxxxxxxxx"  # Mom's number
}

# Solar thresholds
MIN_POWER_WATTS = 800      # Geyser ON only if solar > 800W
MIN_PEAK_HOURS = 4         # Forecast must have 4+ hours >600 W/m²
CHECK_INTERVAL = 60        # Seconds

# Setup logging
logging.basicConfig(filename='/home/pi/solarai.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')

# ==================== HARDWARE SETUP ====================
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, GPIO.LOW)  # Geyser OFF on boot

ina = INA219(0.1)  # 0.1 ohm shunt
ina.configure()

# ==================== FUNCTIONS ====================
def get_solar_power():
    try:
        return ina.power()
    except:
        return 0

def get_peak_forecast():
    try:
        url = "https://api.solcast.com.au/radiation/forecasts"
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "api_key": SOLCAST_API_KEY,
            "format": "json"
        }
        r = requests.get(url, params=params, timeout=10)
        forecasts = r.json().get('forecasts', [])
        peak_hours = sum(1 for h in forecasts if h['ghi'] > 600)
        return peak_hours >= MIN_PEAK_HOURS
    except Exception as e:
        logging.error(f"Forecast error: {e}")
        return False

def send_sms(message):
    try:
        url = "https://api.clickatell.com/http/sendmsg"
        params = CLICKATELL_API.copy()
        params["text"] = message
        requests.get(url, params=params, timeout=5)
        logging.info(f"SMS sent: {message}")
    except Exception as e:
        logging.error(f"SMS failed: {e}")

def control_geyser():
    power = get_solar_power()
    forecast_ok = get_peak_forecast()

    if power > MIN_POWER_WATTS and forecast_ok:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        send_sms("Geyser ON — 2hr hot water (Solar only)")
        logging.info(f"GEYSER ON | Power: {power}W")
    else:
        GPIO.output(RELAY_PIN, GPIO.LOW)
        if power <= MIN_POWER_WATTS:
            logging.info(f"Geyser OFF | Low power: {power}W")
        else:
            logging.info(f"Geyser OFF | Forecast weak")

# ==================== MAIN LOOP ====================
if __name__ == "__main__":
    logging
