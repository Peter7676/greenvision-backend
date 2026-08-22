def build_decision_intelligence(
    weather: dict,
    disease: list,
    health_index: float | None = None,
) -> dict:
    dry_risk = weather.get("dryRisk", 0)
    disease_risk = weather.get("diseaseRisk", 0)

    raw = weather.get("rawWeather", {})
    humidity = raw.get("currentHumidityPercent")
    temperature = raw.get("currentTemperatureC")
    wind = raw.get("currentWindMps")
    rain_7_days = raw.get("rainLast7DaysMm", 0)

    priority_score = 0
    actions = []
    reasons = []

    if health_index is not None and health_index < 60:
        priority_score += 40
        actions.append("Besök greenen idag och kontrollera skadans omfattning.")
        reasons.append("Health Index är lågt.")

    if dry_risk >= 70:
        priority_score += 30
        actions.append("Kontrollera markfukt och kantzoner.")
        reasons.append("Torkrisken är hög.")

    if rain_7_days < 3 and temperature is not None and temperature >= 22:
        priority_score += 20
        actions.append("Kontrollera bevattningsbilden.")
        reasons.append("Låg nederbörd i kombination med hög temperatur.")

    if wind is not None and wind >= 6 and dry_risk >= 50:
        priority_score += 10
        actions.append("Kontrollera vindutsatta delar av greenen.")
        reasons.append("Vind kan öka uttorkning.")

    if disease_risk >= 60:
        priority_score += 25
        actions.append("Inspektera greenen för tidiga sjukdomssymptom.")
        reasons.append("Väderförhållandena ger förhöjd sjukdomsrisk.")

    if humidity is not None and humidity >= 90:
        if temperature is not None and 5 <= temperature <= 18:
            priority_score += 20
            actions.append("Kontrollera mögelfläckar och långvarig bladväta.")
            reasons.append("Hög luftfuktighet och sval temperatur ökar sjukdomsrisk.")

    for item in disease:
        name = item.get("name", "")
        probability = item.get("probability", 0)

        if probability >= 60:
            priority_score += 20
            actions.append(f"Kontrollera symptom kopplade till {name}.")
            reasons.append(f"{name} har förhöjd risk enligt Disease Engine.")

    priority_score = min(100, priority_score)

    if priority_score >= 70:
        priority = "Hög"
    elif priority_score >= 35:
        priority = "Medel"
    else:
        priority = "Låg"

    if not actions:
        actions.append("Ingen akut åtgärd. Följ upp vid nästa ordinarie kontroll.")

    if not reasons:
        reasons.append("Inga tydliga riskfaktorer sticker ut just nu.")

    # Ta bort dubbletter men behåll ordning
    actions = list(dict.fromkeys(actions))
    reasons = list(dict.fromkeys(reasons))

    return {
        "priority": priority,
        "priorityScore": priority_score,
        "actions": actions[:5],
        "reasons": reasons[:5],
    }