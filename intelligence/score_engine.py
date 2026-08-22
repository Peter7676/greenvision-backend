
from __future__ import annotations

from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _highest_probability(items: Any) -> float:
    if not isinstance(items, list):
        return 0.0

    probabilities: list[float] = []

    for item in items:
        if isinstance(item, dict):
            probabilities.append(
                _clamp(_number(item.get("probability"), 0.0))
            )

    return max(probabilities, default=0.0)


def status_from_score(score: float) -> str:
    if score >= 90:
        return "Mycket bra"
    if score >= 80:
        return "Bra"
    if score >= 65:
        return "Kontrollera"
    if score >= 50:
        return "Måttlig stress"
    if score >= 35:
        return "Dålig"
    if score >= 20:
        return "Allvarlig"
    return "Kritisk"


def display_mode_from_score(score: float) -> str:
    if score >= 80:
        return "compact"
    if score >= 60:
        return "normal"
    return "critical"


def calculate_greenvision_score(
    color_analysis: dict[str, Any] | None,
    ai_result: dict[str, Any] | None,
    weather_intelligence: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Räknar GreenVision Score utan att låta språkmodellen bestämma poängen.

    Viktning:
    - Färgjämnhet: 30 %
    - Påverkad yta: 20 %
    - Stressmönster: 20 %
    - Textur: 10 %
    - AI-diagnostisk risk: 10 %
    - Väderrelaterad risk: 10 %
    """
    color = color_analysis or {}
    ai = ai_result or {}
    weather = weather_intelligence or {}

    if color.get("status") != "ok":
        return {
            "score": 60.0,
            "status": "Kontrollera",
            "displayMode": "normal",
            "confidence": 35.0,
            "components": {
                "colorUniformity": 60.0,
                "affectedAreaQuality": 60.0,
                "stressQuality": 60.0,
                "texture": 60.0,
                "diagnosticQuality": 60.0,
                "weatherQuality": 60.0,
            },
            "reason": (
                "Färgmotorn kunde inte identifiera tillräckligt stor säker "
                "gräsyta. Resultatet behöver kontrolleras manuellt."
            ),
        }

    color_uniformity = _clamp(
        _number(color.get("colorUniformityScore"), 60.0)
    )
    affected_area = _clamp(
        _number(color.get("affectedAreaPercent"), 0.0)
    )
    stress_index = _clamp(
        _number(color.get("stressIndex"), 0.0)
    )
    texture = _clamp(
        _number(color.get("textureScore"), 60.0)
    )

    affected_area_quality = _clamp(100.0 - affected_area * 2.1)
    stress_quality = _clamp(100.0 - stress_index)

    diagnostic_risk = max(
        _highest_probability(ai.get("stressAssessment")),
        _highest_probability(ai.get("nutrientAssessment")),
        _highest_probability(ai.get("diseaseAssessment")),
    )
    diagnostic_quality = _clamp(100.0 - diagnostic_risk * 0.72)

    weather_risk = max(
        _clamp(_number(weather.get("dryRisk"), 0.0)),
        _clamp(_number(weather.get("diseaseRisk"), 0.0)),
        _clamp(_number(weather.get("anthracnoseRisk"), 0.0)),
        _clamp(_number(weather.get("microdochiumRisk"), 0.0)),
    )
    weather_quality = _clamp(100.0 - weather_risk * 0.55)

    score = (
        color_uniformity * 0.30
        + affected_area_quality * 0.20
        + stress_quality * 0.20
        + texture * 0.10
        + diagnostic_quality * 0.10
        + weather_quality * 0.10
    )

    # En stor synlig avvikande yta får inte döljas av höga delpoäng.
    if affected_area >= 25:
        score = min(score, 68.0)
    elif affected_area >= 18:
        score = min(score, 74.0)
    elif affected_area >= 10:
        score = min(score, 82.0)

    if color_uniformity < 65:
        score = min(score, 69.0)
    elif color_uniformity < 75:
        score = min(score, 78.0)

    score = round(_clamp(score), 1)

    confidence = round(
        _clamp(
            _number(color.get("turfCoveragePercent"), 0.0) * 0.65
            + _number(ai.get("confidence"), 50.0) * 0.35
        ),
        1,
    )

    largest_penalty = min(
        {
            "färgjämnhet": color_uniformity,
            "påverkad yta": affected_area_quality,
            "stressmönster": stress_quality,
            "textur": texture,
            "diagnostisk risk": diagnostic_quality,
            "väderrisk": weather_quality,
        },
        key=lambda key: {
            "färgjämnhet": color_uniformity,
            "påverkad yta": affected_area_quality,
            "stressmönster": stress_quality,
            "textur": texture,
            "diagnostisk risk": diagnostic_quality,
            "väderrisk": weather_quality,
        }[key],
    )

    return {
        "score": score,
        "status": status_from_score(score),
        "displayMode": display_mode_from_score(score),
        "confidence": confidence,
        "components": {
            "colorUniformity": round(color_uniformity, 1),
            "affectedAreaQuality": round(affected_area_quality, 1),
            "stressQuality": round(stress_quality, 1),
            "texture": round(texture, 1),
            "diagnosticQuality": round(diagnostic_quality, 1),
            "weatherQuality": round(weather_quality, 1),
        },
        "reason": (
            f"Största poängavdraget kommer från {largest_penalty}. "
            f"Färgmotorn bedömde {affected_area:.1f} % av den säkra "
            "gräsytan som tydligt avvikande."
        ),
    }
