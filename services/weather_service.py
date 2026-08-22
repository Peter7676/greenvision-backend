from datetime import datetime, timedelta
import requests


EKERUM_LATITUDE = 56.747
EKERUM_LONGITUDE = 16.584


def get_weather_context(
    latitude: float = EKERUM_LATITUDE,
    longitude: float = EKERUM_LONGITUDE,
) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/Stockholm",
        "past_days": 7,
        "forecast_days": 1,
        "wind_speed_unit": "ms",
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()

    hourly = data.get("hourly", {})
    daily = data.get("daily", {})

    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    humidity = hourly.get("relative_humidity_2m", [])
    wind = hourly.get("wind_speed_10m", [])

    now_hour = datetime.now().strftime("%Y-%m-%dT%H:00")

    try:
        current_index = times.index(now_hour)
    except ValueError:
        current_index = len(times) - 1 if times else 0

    current_temperature = temperatures[current_index] if temperatures else None
    current_humidity = humidity[current_index] if humidity else None
    current_wind = wind[current_index] if wind else None

    precipitation_days = daily.get("precipitation_sum", [])
    rain_last_7_days = sum(precipitation_days[:7]) if precipitation_days else 0

    dry_risk = 0

    if rain_last_7_days < 5:
        dry_risk += 40
    if current_temperature is not None and current_temperature > 24:
        dry_risk += 30
    if current_humidity is not None and current_humidity < 50:
        dry_risk += 20
    if current_wind is not None and current_wind > 5:
        dry_risk += 10

    dry_risk = min(100, dry_risk)

    disease_risk = 0

    if current_humidity is not None and current_humidity > 85:
        disease_risk += 40
    if rain_last_7_days > 10:
        disease_risk += 30
    if current_temperature is not None and 5 <= current_temperature <= 18:
        disease_risk += 20

    disease_risk = min(100, disease_risk)

    return {
        "source": "Open-Meteo",
        "currentTemperatureC": current_temperature,
        "currentHumidityPercent": current_humidity,
        "currentWindMps": current_wind,
        "rainLast7DaysMm": round(rain_last_7_days, 1),
        "dryRisk": dry_risk,
        "diseaseRisk": disease_risk,
    }