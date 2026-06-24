import sqlite3
from datetime import datetime

from app.core.config import settings


def connect() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(settings.database_path)


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                document_kind TEXT NOT NULL,
                model TEXT NOT NULL,
                entities_found INTEGER NOT NULL,
                replacements_applied INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_job(
    job_id: str,
    filename: str,
    document_kind: str,
    model: str,
    entities_found: int,
    replacements_applied: int,
    sha256: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs
            (id, filename, document_kind, model, entities_found, replacements_applied, sha256, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                filename,
                document_kind,
                model,
                entities_found,
                replacements_applied,
                sha256,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )


def list_jobs() -> list[dict]:
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(row) for row in rows]
