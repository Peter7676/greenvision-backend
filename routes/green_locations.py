from typing import Any

from fastapi import APIRouter, Body, HTTPException

from database.green_locations import (
    delete_green_location,
    get_green_location,
    get_green_locations,
    init_green_locations,
    save_green_location,
)


router = APIRouter(
    prefix="/green-locations",
    tags=["Green locations"],
)


@router.get("")
def list_green_locations(
    course_name: str | None = None,
):
    return get_green_locations(
        course_name=course_name,
    )


@router.get("/{course_name}/{green_number}")
def read_green_location(
    course_name: str,
    green_number: int,
):
    location = get_green_location(
        course_name=course_name,
        green_number=green_number,
    )

    if location is None:
        raise HTTPException(
            status_code=404,
            detail="Greenpositionen hittades inte.",
        )

    return location


@router.post("")
def create_or_update_green_location(
    payload: dict[str, Any] = Body(...),
):
    try:
        course_name = str(
            payload.get("courseName", "")
        ).strip()

        green_number = int(
            payload.get("greenNumber", 0)
        )

        latitude = float(
            payload.get("latitude")
        )

        longitude = float(
            payload.get("longitude")
        )

        return save_green_location(
            course_name=course_name,
            green_number=green_number,
            latitude=latitude,
            longitude=longitude,
        )

    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.delete("/{course_name}/{green_number}")
def remove_green_location(
    course_name: str,
    green_number: int,
):
    deleted = delete_green_location(
        course_name=course_name,
        green_number=green_number,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Greenpositionen hittades inte.",
        )

    return {
        "status": "deleted",
        "courseName": course_name,
        "greenNumber": green_number,
    }


def initialize_green_locations() -> None:
    init_green_locations()