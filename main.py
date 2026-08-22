from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import (
    Body,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware

from database.database import (
    delete_journal_entry,
    get_ai_journal_context,
    get_all_analyses,
    get_journal_entries,
    init_db,
    save_analysis,
    save_journal_entry,
)
from intelligence.color_engine import (
    analyze_color_uniformity,
    create_color_heatmap,
)
from intelligence.decision_engine import (
    build_decision_intelligence,
)
from intelligence.disease_engine import (
    build_disease_intelligence,
)
from intelligence.score_engine import (
    calculate_greenvision_score,
)
from intelligence.weather_engine import (
    build_weather_intelligence,
)
from routes.green_locations import (
    initialize_green_locations,
    router as green_locations_router,
)
from services.openai_service import (
    analyze_green_image,
)
from services.weather_service import (
    get_weather_context,
)


app = FastAPI(
    title="GreenVision AI Backend",
    version="0.9.2",
)


app.include_router(
    green_locations_router,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = Path("uploads")


@app.on_event("startup")
def startup() -> None:
    init_db()
    initialize_green_locations()

    UPLOAD_DIR.mkdir(
        exist_ok=True,
    )


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "ok",
        "message": (
            "GreenVision AI Backend är igång"
        ),
        "version": "0.9.2",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }


@app.get("/analyses")
def analyses():
    return get_all_analyses()


@app.get("/journal")
def journal(
    course_name: str | None = None,
    green_number: int | None = None,
    scope: str | None = None,
    limit: int = 100,
):
    return get_journal_entries(
        course_name=course_name,
        green_number=green_number,
        scope=scope,
        limit=limit,
    )


@app.post("/journal")
def create_journal_entry(
    payload: dict[str, Any] = Body(...),
):
    try:
        raw_green_number = payload.get(
            "greenNumber"
        )

        green_number = (
            int(raw_green_number)
            if raw_green_number is not None
            else None
        )

        return save_journal_entry(
            course_name=str(
                payload.get(
                    "courseName",
                    "",
                )
            ),
            scope=str(
                payload.get(
                    "scope",
                    "green",
                )
            ),
            green_number=green_number,
            entry_type=str(
                payload.get(
                    "entryType",
                    "observation",
                )
            ),
            title=str(
                payload.get(
                    "title",
                    "",
                )
            ),
            note=str(
                payload.get(
                    "note",
                    "",
                )
            ),
            event_date=payload.get(
                "eventDate"
            ),
            product_name=payload.get(
                "productName"
            ),
            dose=payload.get(
                "dose"
            ),
            area=payload.get(
                "area"
            ),
            latitude=payload.get(
                "latitude"
            ),
            longitude=payload.get(
                "longitude"
            ),
            created_by=payload.get(
                "createdBy"
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.delete(
    "/journal/{journal_id}"
)
def remove_journal_entry(
    journal_id: int,
):
    deleted = delete_journal_entry(
        journal_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=(
                "Journalposten hittades inte."
            ),
        )

    return {
        "status": "deleted",
        "id": journal_id,
    }


@app.get("/weather")
def weather() -> dict[str, Any]:
    raw_weather = get_weather_context()

    weather_intelligence = (
        build_weather_intelligence(
            raw_weather
        )
    )

    disease_intelligence = (
        build_disease_intelligence(
            weather_intelligence
        )
    )

    decision_intelligence = (
        build_decision_intelligence(
            weather=weather_intelligence,
            disease=disease_intelligence,
        )
    )

    return {
        "weather": weather_intelligence,
        "disease": disease_intelligence,
        "decision": decision_intelligence,
    }


def confidence_to_number(
    value: Any,
) -> float:
    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return float(value)

    if isinstance(
        value,
        str,
    ):
        normalized = (
            value
            .lower()
            .strip()
        )

        if normalized == "hög":
            return 95.0

        if normalized == "medel":
            return 70.0

        if normalized == "låg":
            return 40.0

        try:
            return float(
                normalized
            )

        except ValueError:
            return 0.0

    return 0.0


def save_uploaded_image(
    image_bytes: bytes,
    course_name: str,
    green_number: int,
    original_filename: str,
) -> str:
    now = datetime.now()

    folder = (
        UPLOAD_DIR
        / now.strftime(
            "%Y-%m-%d"
        )
    )

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_course = (
        course_name
        .replace(
            " ",
            "_",
        )
        .replace(
            "å",
            "a",
        )
        .replace(
            "ä",
            "a",
        )
        .replace(
            "ö",
            "o",
        )
        .replace(
            "Å",
            "A",
        )
        .replace(
            "Ä",
            "A",
        )
        .replace(
            "Ö",
            "O",
        )
    )

    extension = (
        Path(
            original_filename
        )
        .suffix
        .lower()
    )

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    if (
        extension
        not in allowed_extensions
    ):
        extension = ".jpg"

    filename = (
        f"{safe_course}"
        f"_green_{green_number}"
        f"_"
        f"{now.strftime('%H%M%S_%f')}"
        f"{extension}"
    )

    filepath = (
        folder
        / filename
    )

    filepath.write_bytes(
        image_bytes
    )

    return str(
        filepath
    )


def save_heatmap(
    image_bytes: bytes,
    image_path: str,
) -> str | None:
    try:
        heatmap_bytes = (
            create_color_heatmap(
                image_bytes
            )
        )

        original_path = Path(
            image_path
        )

        heatmap_path = (
            original_path.with_name(
                f"{original_path.stem}"
                "_heatmap.jpg"
            )
        )

        heatmap_path.write_bytes(
            heatmap_bytes
        )

        return str(
            heatmap_path
        )

    except Exception as error:
        print(
            "Kunde inte skapa heatmap:",
            error,
        )

        return None


@app.post("/analyze")
async def analyze_green(
    image: UploadFile = File(...),
    course_name: str = Form(...),
    green_number: int = Form(...),
):
    image_bytes = (
        await image.read()
    )

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Den uppladdade bilden är tom."
            ),
        )

    original_filename = (
        image.filename
        or "image.jpg"
    )

    image_path = (
        save_uploaded_image(
            image_bytes=image_bytes,
            course_name=course_name,
            green_number=green_number,
            original_filename=(
                original_filename
            ),
        )
    )

    try:
        color_analysis = (
            analyze_color_uniformity(
                image_bytes
            )
        )

    except Exception as error:
        print(
            "Fel i Color Engine:",
            error,
        )

        color_analysis = {
            "status": "error",
            "message": str(error),
        }

    heatmap_path = None

    if (
        color_analysis.get(
            "status"
        )
        == "ok"
    ):
        heatmap_path = (
            save_heatmap(
                image_bytes=(
                    image_bytes
                ),
                image_path=(
                    image_path
                ),
            )
        )

    raw_weather = (
        get_weather_context()
    )

    weather_intelligence = (
        build_weather_intelligence(
            raw_weather
        )
    )

    disease_intelligence = (
        build_disease_intelligence(
            weather_intelligence
        )
    )

    preliminary_decision = (
        build_decision_intelligence(
            weather=(
                weather_intelligence
            ),
            disease=(
                disease_intelligence
            ),
        )
    )

    preliminary_context = {
        "weather": (
            weather_intelligence
        ),
        "disease": (
            disease_intelligence
        ),
        "decision": (
            preliminary_decision
        ),
    }

    journal_entries = (
        get_ai_journal_context(
            course_name=(
                course_name
            ),
            green_number=(
                green_number
            ),
            limit=20,
        )
    )

    ai_result = (
        await analyze_green_image(
            image_bytes=(
                image_bytes
            ),
            filename=(
                image_path
            ),
            course_name=(
                course_name
            ),
            green_number=(
                green_number
            ),
            weather_context=(
                preliminary_context
            ),
            vision_context=(
                color_analysis
            ),
            journal_entries=(
                journal_entries
            ),
        )
    )

    score_result = (
        calculate_greenvision_score(
            color_analysis=(
                color_analysis
            ),
            ai_result=(
                ai_result
            ),
            weather_intelligence=(
                weather_intelligence
            ),
        )
    )

    health_index = float(
        score_result.get(
            "score",
            0,
        )
    )

    final_decision = (
        build_decision_intelligence(
            weather=(
                weather_intelligence
            ),
            disease=(
                disease_intelligence
            ),
        )
    )

    intelligence_context = {
        "weather": (
            weather_intelligence
        ),
        "disease": (
            disease_intelligence
        ),
        "decision": (
            final_decision
        ),
        "vision": (
            color_analysis
        ),
        "score": (
            score_result
        ),
        "journal": (
            journal_entries
        ),
    }

    result = {
        **ai_result,
        "healthIndex": (
            health_index
        ),
        "status": (
            score_result.get(
                "status",
                "Kontrollera",
            )
        ),
        "confidence": (
            score_result.get(
                "confidence",
                50,
            )
        ),
        "displayMode": (
            score_result.get(
                "displayMode",
                "normal",
            )
        ),
        "greenVisionScore": (
            score_result
        ),
        "visionAnalysis": (
            color_analysis
        ),
        "journalEntriesUsed": (
            journal_entries
        ),
        "imagePath": (
            image_path
        ),
        "heatmapPath": (
            heatmap_path
        ),
        "intelligence": (
            intelligence_context
        ),
    }

    save_analysis(
        course_name=(
            course_name
        ),
        green_number=(
            green_number
        ),
        health_index=(
            health_index
        ),
        status=str(
            result.get(
                "status",
                "",
            )
        ),
        observation=str(
            result.get(
                "observation",
                "",
            )
        ),
        likely_cause=str(
            result.get(
                "likelyCause",
                "",
            )
        ),
        recommendation=str(
            result.get(
                "recommendation",
                "",
            )
        ),
        confidence=(
            confidence_to_number(
                result.get(
                    "confidence"
                )
            )
        ),
        image_filename=(
            image_path
        ),
    )

    return result