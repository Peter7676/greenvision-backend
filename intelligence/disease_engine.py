from datetime import datetime


def build_disease_intelligence(weather: dict) -> dict:
    month = datetime.now().month

    dry_risk = weather.get("dryRisk", 0)
    disease_risk = weather.get("diseaseRisk", 0)

    humidity = weather.get("rawWeather", {}).get("currentHumidityPercent")
    temperature = weather.get("rawWeather", {}).get("currentTemperatureC")

    anthracnose = 0
    microdochium = 0
    dollar_spot = 0
    pythium = 0
    snow_mold = 0

    # -----------------------------
    # SOMMAR
    # -----------------------------

    if month in [6, 7, 8]:

        if dry_risk >= 70:
            anthracnose += 35

        if temperature is not None and temperature >= 24:
            anthracnose += 20

        if humidity is not None and humidity < 60:
            anthracnose += 10

        if humidity is not None and humidity > 80:
            dollar_spot += 25

    # -----------------------------
    # HÖST
    # -----------------------------

    if month in [9, 10, 11]:

        if humidity is not None and humidity >= 90:
            microdochium += 40

        if disease_risk >= 60:
            microdochium += 20

    # -----------------------------
    # VÅR
    # -----------------------------

    if month in [3, 4, 5]:

        snow_mold += 40

        if disease_risk >= 50:
            snow_mold += 20

    # -----------------------------
    # PYTHIUM
    # -----------------------------

    if temperature is not None and temperature > 25:
        if humidity is not None and humidity > 85:
            pythium += 40

    diseases = [
        {
            "name": "Anthracnose",
            "probability": min(100, anthracnose),
            "reason": "Risk beräknad från väder, årstid och stress.",
        },
        {
            "name": "Microdochium Patch",
            "probability": min(100, microdochium),
            "reason": "Risk beräknad från väder och årstid.",
        },
        {
            "name": "Dollar Spot",
            "probability": min(100, dollar_spot),
            "reason": "Risk beräknad från luftfuktighet.",
        },
        {
            "name": "Pythium",
            "probability": min(100, pythium),
            "reason": "Risk beräknad från värme och hög luftfuktighet.",
        },
        {
            "name": "Snömögel",
            "probability": min(100, snow_mold),
            "reason": "Risk eller kvarvarande skador efter vinter.",
        },
    ]

    diseases.sort(key=lambda x: x["probability"], reverse=True)

    return diseases