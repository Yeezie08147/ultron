"""
weather_radar.py — ULTRON Real-Time Atmospheric & Weather Radar.

Capabilities:
- Sub-second weather telemetry via Open-Meteo & Nominatim (100% free, no API keys)
- Temperature, humidity, wind speed, precipitation, weather conditions worldwide
"""

import httpx
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.weather")

WMO_CODE_MAP = {
    0: "Clear skies",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}


def get_live_weather(city: str = "") -> Dict[str, Any]:
    """Fetch live weather conditions for a city or default to Tokyo/London/local."""
    target_city = city.strip() or "Tokyo"

    try:
        with httpx.Client(verify=False, timeout=5.0) as client:
            # 1. Geocode city name to lat/lon via Open-Meteo geocoding API
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={target_city}&count=1&language=en&format=json"
            geo_resp = client.get(geo_url)
            
            if geo_resp.status_code == 200 and geo_resp.json().get("results"):
                loc = geo_resp.json()["results"][0]
                lat = loc["latitude"]
                lon = loc["longitude"]
                resolved_name = loc.get("name", target_city)
                country = loc.get("country", "")

                # 2. Get real-time forecast
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                w_resp = client.get(weather_url)
                
                if w_resp.status_code == 200:
                    w_data = w_resp.json().get("current", {})
                    temp_c = w_data.get("temperature_2m", "--")
                    humidity = w_data.get("relative_humidity_2m", "--")
                    wind = w_data.get("wind_speed_10m", "--")
                    w_code = w_data.get("weather_code", 0)
                    desc = WMO_CODE_MAP.get(w_code, "Clear conditions")

                    temp_f = round((temp_c * 9/5) + 32, 1) if isinstance(temp_c, (int, float)) else "--"

                    msg = f"Atmospheric report for {resolved_name} ({country}): {desc}, {temp_c} degrees Celsius ({temp_f} degrees Fahrenheit). Humidity at {humidity}%, wind speed {wind} km/h."
                    return {
                        "success": True,
                        "city": resolved_name,
                        "country": country,
                        "temp_c": temp_c,
                        "desc": desc,
                        "message": msg
                    }
    except Exception as e:
        log.warning(f"Open-Meteo failed for '{city}': {e}")

    return {
        "success": False,
        "message": f"Unable to acquire atmospheric telemetry for {target_city}, sir."
    }
