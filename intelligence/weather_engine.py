def _level(value: float) -> str:
    if value >= 75:
        return "Hög"
    if value >= 40:
        return "Medel"
    return "Låg"


def build_weather_intelligence(weather: dict) -> dict:
    temperature = weather.get("currentTemperatureC")
    humidity = weather.get("currentHumidityPercent")
    wind = weather.get("currentWindMps")
    rain_7_days = weather.get("rainLast7DaysMm", 0)

    dry_risk = weather.get("dryRisk", 0)
    disease_risk = weather.get("diseaseRisk", 0)

    anthracnose_risk = 0
    microdochium_risk = 0

    if temperature is not None and temperature >= 22:
        anthracnose_risk += 25

    if dry_risk >= 60:
        anthracnose_risk += 25

    if rain_7_days < 5:
        anthracnose_risk += 15

    if humidity is not None and humidity >= 85:
        microdochium_risk += 30

    if temperature is not None and 5 <= temperature <= 18:
        microdochium_risk += 25

    if rain_7_days > 10:
        microdochium_risk += 20

    anthracnose_risk = min(100, anthracnose_risk)
    microdochium_risk = min(100, microdochium_risk)

    summary_parts = []

    if dry_risk >= 75:
        summary_parts.append("Hög torkrisk baserat på senaste väderdata.")
    elif dry_risk >= 40:
        summary_parts.append("Måttlig torkrisk.")

    if anthracnose_risk >= 50:
        summary_parts.append("Förhöjd risk för Anthracnose vid stressade greener.")

    if microdochium_risk >= 50:
        summary_parts.append("Förhöjd risk för Microdochium/mögelfläckar.")

    if not summary_parts:
        summary_parts.append("Inga tydliga väderbaserade risker just nu.")

    return {
        "dryRisk": dry_risk,
        "dryLevel": _level(dry_risk),
        "diseaseRisk": disease_risk,
        "diseaseLevel": _level(disease_risk),
        "anthracnoseRisk": anthracnose_risk,
        "anthracnoseLevel": _level(anthracnose_risk),
        "microdochiumRisk": microdochium_risk,
        "microdochiumLevel": _level(microdochium_risk),
        "summary": " ".join(summary_parts),
        "rawWeather": weather,
    }