
import base64
import json
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text.replace("```json", "", 1).strip()

    if text.startswith("```"):
        text = text.replace("```", "", 1).strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def _season_context() -> str:
    month = datetime.now().month

    if month in [3, 4, 5]:
        return """
Säsong: vår.
Prioritera vinterskador, kvarvarande snömögelskador, långsam återväxt,
näringsbrist och svag etablering. Skilj mellan aktiv sjukdom och gamla skador.
"""

    if month in [6, 7, 8]:
        return """
Säsong: sommar.
Prioritera torkstress, värmestress, Anthracnose, slitage, packning och
näringsbrister. Microdochium är normalt mindre sannolikt under sommaren.
"""

    if month in [9, 10, 11]:
        return """
Säsong: höst.
Prioritera Microdochium Patch, långvarig bladväta, hög luftfuktighet
och långsam återhämtning.
"""

    return """
Säsong: vinter/lågsäsong.
Var uppmärksam på vinterskador, snömögel, isbränna och svag återväxt.
"""


def _weather_context_text(weather_context: dict | None) -> str:
    if not weather_context:
        return "Väderdata saknas."

    weather = weather_context.get("weather", {})
    disease = weather_context.get("disease", [])
    decision = weather_context.get("decision", {})

    if not isinstance(weather, dict):
        weather = {}

    raw_weather = weather.get("rawWeather", {})

    if not isinstance(raw_weather, dict):
        raw_weather = {}

    disease_lines: list[str] = []

    if isinstance(disease, list):
        for item in disease:
            if not isinstance(item, dict):
                continue

            disease_lines.append(
                f'- {item.get("name", "Okänd sjukdom")}: '
                f'{item.get("probability", 0)} % – '
                f'{item.get("reason", "")}'
            )

    if not disease_lines:
        disease_lines.append("- Inga tydliga sjukdomsrisker beräknade.")

    actions = decision.get("actions", [])
    reasons = decision.get("reasons", [])

    if not isinstance(actions, list):
        actions = []

    if not isinstance(reasons, list):
        reasons = []

    action_lines = [f"- {action}" for action in actions]
    reason_lines = [f"- {reason}" for reason in reasons]

    if not action_lines:
        action_lines.append("- Ingen särskild åtgärd föreslagen.")

    if not reason_lines:
        reason_lines.append("- Ingen särskild riskorsak angiven.")

    return f"""
Aktuellt väder och riskindex:

- Källa: {raw_weather.get("source", "Okänd")}
- Temperatur: {raw_weather.get("currentTemperatureC", 0)} °C
- Luftfuktighet: {raw_weather.get("currentHumidityPercent", 0)} %
- Vind: {raw_weather.get("currentWindMps", 0)} m/s
- Regn senaste 7 dagarna: {raw_weather.get("rainLast7DaysMm", 0)} mm
- Torkrisk: {weather.get("dryRisk", 0)} %
- Sjukdomsrisk: {weather.get("diseaseRisk", 0)} %
- Anthracnose-risk: {weather.get("anthracnoseRisk", 0)} %
- Microdochium-risk: {weather.get("microdochiumRisk", 0)} %

Beräknade sjukdomsrisker:
{chr(10).join(disease_lines)}

Föreslagna åtgärder:
{chr(10).join(action_lines)}

Bakomliggande orsaker:
{chr(10).join(reason_lines)}
"""


def _vision_context_text(vision_context: dict | None) -> str:
    if not vision_context:
        return "Mätvärden från bildmotorn saknas."

    if vision_context.get("status") != "ok":
        return (
            "Bildmotorn kunde inte identifiera tillräckligt stor säker "
            "gräsyta. Var extra försiktig och rekommendera ny bild."
        )

    observations = vision_context.get("observations", [])

    if not isinstance(observations, list):
        observations = []

    observation_lines = [
        f"- {item}"
        for item in observations
    ]

    if not observation_lines:
        observation_lines.append("- Ingen särskild maskinell observation.")

    return f"""
Mätvärden från GreenVision Color Engine:

- Säker identifierad gräsyta:
  {vision_context.get("turfCoveragePercent", 0)} %
- Färgjämnhet:
  {vision_context.get("colorUniformityScore", 0)} / 100
- Färgintensitet:
  {vision_context.get("colorIntensityScore", 0)} / 100
- Stressindex:
  {vision_context.get("stressIndex", 0)} / 100
- Påverkad yta:
  {vision_context.get("affectedAreaPercent", 0)} %
- Textur:
  {vision_context.get("textureScore", 0)} / 100
- Visuell kvalitet:
  {vision_context.get("visualQualityScore", 0)} / 100
- Variationsnivå:
  {vision_context.get("variationLevel", "okänd")}
- Antal större avvikande områden:
  {len(vision_context.get("affectedRegions", []))}

Maskinella observationer:
{chr(10).join(observation_lines)}

Dessa mätvärden är styrande för hur tydlig färgvariationen är.
Du ska tolka möjliga orsaker, men du ska inte skapa eller ändra Health Index.
"""


def _to_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_percent(value: Any, default: float = 0.0) -> float:
    return max(0.0, min(100.0, _to_number(value, default)))


def _normalize_category(items: Any, fallback_names: list[str]) -> list[dict]:
    if not isinstance(items, list):
        items = []

    cleaned: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        cleaned.append(
            {
                "name": str(item.get("name", "Okänt")),
                "probability": _clamp_percent(
                    item.get("probability", 0)
                ),
                "reason": str(item.get("reason", "")),
            }
        )

    existing_names = {
        item["name"].lower()
        for item in cleaned
    }

    for name in fallback_names:
        if name.lower() not in existing_names:
            cleaned.append(
                {
                    "name": name,
                    "probability": 0,
                    "reason": "",
                }
            )

    cleaned.sort(
        key=lambda item: item["probability"],
        reverse=True,
    )

    return cleaned[:6]


def _normalize_result(result: dict) -> dict:
    result["confidence"] = _clamp_percent(
        result.get("confidence", 50),
        50,
    )

    result.setdefault("observation", "")
    result.setdefault("likelyCause", "")
    result.setdefault("recommendation", "")

    result["stressAssessment"] = _normalize_category(
        result.get("stressAssessment"),
        [
            "Torkstress",
            "Värmestress",
            "Packning",
            "Slitage",
            "Syrebrist",
        ],
    )

    result["nutrientAssessment"] = _normalize_category(
        result.get("nutrientAssessment"),
        [
            "Kvävebrist",
            "Järnbrist",
            "Kaliumbrist",
            "Magnesiumbrist",
            "pH-relaterad låsning",
        ],
    )

    result["diseaseAssessment"] = _normalize_category(
        result.get("diseaseAssessment"),
        [
            "Anthracnose",
            "Microdochium Patch",
            "Dollar Spot",
            "Pythium",
            "Red Thread",
            "Snömögel",
        ],
    )

    result.setdefault("diagnosticSummary", "")
    result.setdefault("fieldChecks", [])
    result.setdefault("followUpRecommendation", "")

    if not isinstance(result["fieldChecks"], list):
        result["fieldChecks"] = []

    return result


async def analyze_green_image(
    image_bytes: bytes,
    filename: str,
    course_name: str,
    green_number: int,
    weather_context: dict | None = None,
    vision_context: dict | None = None,
):
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    season_context = _season_context()
    weather_text = _weather_context_text(weather_context)
    vision_text = _vision_context_text(vision_context)

    prompt = f"""
Du är expert på nordiska golfgreener, grässjukdomar, färgförändringar,
torkstress, näringsbrister och praktisk golfbaneskötsel.

Analysera bilden från:
Bana: {course_name}
Green: {green_number}

{season_context}

{weather_text}

{vision_text}

Viktiga regler:
- GreenVision-systemet räknar själv fram GreenVision Score.
- Du får inte skapa fältet healthIndex.
- Du får inte skapa fältet status.
- Tolka varför den uppmätta färgvariationen kan ha uppstått.
- Färgskiftningar och sammanhängande avvikande områden är viktiga även
  när grästäckningen fortfarande är god.
- Skilj mellan torkstress, näringsvariation, slitage, skugga,
  bevattningsmönster och möjlig sjukdom.
- Ge sannolikheter, inte tvärsäkra diagnoser.
- Ge inte säker sjukdomsdiagnos utan tydliga visuella symptom.
- Om en översiktsbild inte räcker för diagnos ska du begära närbilder.

Svara ENDAST som ren JSON, utan markdown och utan kodblock.

Använd exakt dessa fält:
confidence,
observation,
likelyCause,
recommendation,
diagnosticSummary,
stressAssessment,
nutrientAssessment,
diseaseAssessment,
fieldChecks,
followUpRecommendation

stressAssessment, nutrientAssessment och diseaseAssessment ska vara listor:
[
  {{
    "name": "Torkstress",
    "probability": 70,
    "reason": "Mätbar färgvariation och sammanhängande ljusare område."
  }}
]

fieldChecks ska vara en lista med praktiska kontroller på plats.

Alla probability-värden och confidence ska vara 0-100.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:image/jpeg;base64,{image_base64}"
                        ),
                    },
                ],
            }
        ],
    )

    text = _clean_json_text(response.output_text)

    try:
        result = json.loads(text)
        result = _normalize_result(result)
        result["filename"] = filename
        return result
    except Exception:
        return {
            "confidence": 35,
            "observation": text,
            "likelyCause": (
                "AI-svaret kunde inte tolkas som JSON."
            ),
            "recommendation": (
                "Kontrollera analysen manuellt."
            ),
            "diagnosticSummary": (
                "Analysen kunde inte struktureras."
            ),
            "stressAssessment": [],
            "nutrientAssessment": [],
            "diseaseAssessment": [],
            "fieldChecks": [
                "Ta en ny översiktsbild",
                "Ta närbilder av avvikande områden",
                "Kontrollera manuellt på plats",
            ],
            "followUpRecommendation": (
                "Följ upp med en ny analys."
            ),
            "filename": filename,
        }
