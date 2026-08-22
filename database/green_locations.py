import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "greenvision.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_green_locations() -> None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS green_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            green_number INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(course_name, green_number)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_green_locations_course
        ON green_locations (
            course_name,
            green_number
        )
        """
    )

    connection.commit()
    connection.close()


def save_green_location(
    course_name: str,
    green_number: int,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    init_green_locations()

    course_name = course_name.strip()

    if not course_name:
        raise ValueError("Bana saknas.")

    if green_number <= 0:
        raise ValueError("Ogiltigt greennummer.")

    if latitude < -90 or latitude > 90:
        raise ValueError("Ogiltig latitud.")

    if longitude < -180 or longitude > 180:
        raise ValueError("Ogiltig longitud.")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO green_locations (
            course_name,
            green_number,
            latitude,
            longitude,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(course_name, green_number)
        DO UPDATE SET
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            updated_at = excluded.updated_at
        """,
        (
            course_name,
            green_number,
            latitude,
            longitude,
            _utc_now_iso(),
        ),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT *
        FROM green_locations
        WHERE course_name = ?
          AND green_number = ?
        """,
        (
            course_name,
            green_number,
        ),
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        raise RuntimeError(
            "Greenpositionen kunde inte läsas tillbaka."
        )

    return dict(row)


def get_green_locations(
    course_name: str | None = None,
) -> list[dict[str, Any]]:
    init_green_locations()

    connection = get_connection()
    cursor = connection.cursor()

    if course_name:
        cursor.execute(
            """
            SELECT *
            FROM green_locations
            WHERE course_name = ?
            ORDER BY green_number
            """,
            (course_name,),
        )
    else:
        cursor.execute(
            """
            SELECT *
            FROM green_locations
            ORDER BY course_name, green_number
            """
        )

    rows = cursor.fetchall()
    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_green_location(
    course_name: str,
    green_number: int,
) -> dict[str, Any] | None:
    init_green_locations()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM green_locations
        WHERE course_name = ?
          AND green_number = ?
        """,
        (
            course_name,
            green_number,
        ),
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return dict(row)


def delete_green_location(
    course_name: str,
    green_number: int,
) -> bool:
    init_green_locations()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM green_locations
        WHERE course_name = ?
          AND green_number = ?
        """,
        (
            course_name,
            green_number,
        ),
    )

    deleted = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return deleted