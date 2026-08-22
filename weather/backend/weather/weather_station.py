from dataclasses import dataclass
from typing import Optional


@dataclass
class WeatherReading:
    source: str
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    rain_mm: Optional[float] = None
    wind_mps: Optional[float] = None
    soil_moisture_percent: Optional[float] = None
    soil_temperature_c: Optional[float] = None


@dataclass
class WeatherStationConfig:
    name: str
    source_type: str  # open_meteo, home_assistant, custom_api
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    api_url: Optional[str] = None
    api_token: Optional[str] = None