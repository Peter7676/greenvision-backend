import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "greenvision.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            green_number INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            health_index REAL NOT NULL,
            status TEXT NOT NULL,
            observation TEXT NOT NULL,
            likely_cause TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            image_filename TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS green_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            green_number INTEGER,
            scope TEXT NOT NULL DEFAULT 'green',
            created_at TEXT NOT NULL,
            event_date TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            title TEXT NOT NULL,
            product_name TEXT,
            dose TEXT,
            area TEXT,
            note TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            created_by TEXT
        )
        """
    )

    columns = {
        row["name"]: row
        for row in cur.execute(
            "PRAGMA table_info(green_journal)"
        ).fetchall()
    }

    needs_migration = (
        "scope" not in columns
        or int(columns["green_number"]["notnull"]) == 1
    )

    if needs_migration:
        cur.execute(
            """
            CREATE TABLE green_journal_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_name TEXT NOT NULL,
                green_number INTEGER,
                scope TEXT NOT NULL DEFAULT 'green',
                created_at TEXT NOT NULL,
                event_date TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                title TEXT NOT NULL,
                product_name TEXT,
                dose TEXT,
                area TEXT,
                note TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                created_by TEXT
            )
            """
        )

        if "scope" in columns:
            cur.execute(
                """
                INSERT INTO green_journal_new
                SELECT
                    id,
                    course_name,
                    green_number,
                    scope,
                    created_at,
                    event_date,
                    entry_type,
                    title,
                    product_name,
                    dose,
                    area,
                    note,
                    latitude,
                    longitude,
                    created_by
                FROM green_journal
                """
            )
        else:
            cur.execute(
                """
                INSERT INTO green_journal_new (
                    id, course_name, green_number, scope,
                    created_at, event_date, entry_type, title,
                    product_name, dose, area, note,
                    latitude, longitude, created_by
                )
                SELECT
                    id, course_name, green_number, 'green',
                    created_at, event_date, entry_type, title,
                    product_name, dose, area, note,
                    latitude, longitude, created_by
                FROM green_journal
                """
            )

        cur.execute("DROP TABLE green_journal")
        cur.execute(
            "ALTER TABLE green_journal_new RENAME TO green_journal"
        )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_journal_course
        ON green_journal(course_name, scope, event_date DESC)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_journal_green
        ON green_journal(
            course_name,
            green_number,
            scope,
            event_date DESC
        )
        """
    )

    conn.commit()
    conn.close()


def save_analysis(
    course_name: str,
    green_number: int,
    health_index: float,
    status: str,
    observation: str,
    likely_cause: str,
    recommendation: str,
    confidence: float = 0,
    image_filename: str | None = None,
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO analyses (
            course_name, green_number, created_at,
            health_index, status, observation,
            likely_cause, recommendation, confidence,
            image_filename
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            course_name,
            green_number,
            _now(),
            health_index,
            status,
            observation,
            likely_cause,
            recommendation,
            confidence,
            image_filename,
        ),
    )
    row_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return row_id


def get_all_analyses() -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM analyses
        ORDER BY created_at DESC
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_journal_entry(
    *,
    course_name: str,
    scope: str,
    title: str,
    note: str,
    green_number: int | None = None,
    entry_type: str = "observation",
    event_date: str | None = None,
    product_name: str | None = None,
    dose: str | None = None,
    area: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    scope = scope.strip().lower()
    course_name = course_name.strip()
    title = title.strip()
    note = note.strip()

    if scope not in {"course", "green"}:
        raise ValueError("scope måste vara course eller green.")

    if not course_name:
        raise ValueError("Bana saknas.")

    if not title:
        raise ValueError("Rubrik saknas.")

    if not note:
        raise ValueError("Anteckning saknas.")

    if scope == "course":
        green_number = None
        entry_type = "action"
    else:
        if green_number is None or green_number <= 0:
            raise ValueError(
                "Green-nummer krävs för en observation."
            )
        entry_type = "observation"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO green_journal (
            course_name, green_number, scope,
            created_at, event_date, entry_type,
            title, product_name, dose, area,
            note, latitude, longitude, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            course_name,
            green_number,
            scope,
            _now(),
            event_date or _now(),
            entry_type,
            title,
            product_name or None,
            dose or None,
            area or None,
            note,
            latitude,
            longitude,
            created_by or None,
        ),
    )
    row_id = int(cur.lastrowid)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM green_journal WHERE id = ?",
        (row_id,),
    ).fetchone()
    conn.close()
    return dict(row)


def get_journal_entries(
    *,
    course_name: str | None = None,
    green_number: int | None = None,
    scope: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM green_journal"
    conditions: list[str] = []
    params: list[Any] = []

    if course_name is not None:
        conditions.append("course_name = ?")
        params.append(course_name)

    if green_number is not None:
        conditions.append("green_number = ?")
        params.append(green_number)

    if scope is not None:
        conditions.append("scope = ?")
        params.append(scope)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY event_date DESC, created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))

    conn = get_connection()
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_ai_journal_context(
    course_name: str,
    green_number: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM green_journal
        WHERE course_name = ?
          AND (
                scope = 'course'
                OR (
                    scope = 'green'
                    AND green_number = ?
                )
              )
        ORDER BY event_date DESC, created_at DESC
        LIMIT ?
        """,
        (
            course_name,
            green_number,
            max(1, min(limit, 100)),
        ),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_journal_entry(journal_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM green_journal WHERE id = ?",
        (journal_id,),
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
