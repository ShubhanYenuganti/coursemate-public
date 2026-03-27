"""
Database helpers for the embed_materials Lambda.

- get_db(): sync psycopg context manager (for status updates in handler)
- Async asyncpg helpers are used directly in worker.py
"""
import os
import psycopg
from contextlib import contextmanager


@contextmanager
def get_db():
    """Sync psycopg connection for Lambda handler status updates."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    conn = psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_job_state(material_id: int) -> dict:
    """Return {chunk_cursor, document_id} for a material's embed job."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT chunk_cursor, document_id FROM material_embed_jobs WHERE material_id = %s",
            (material_id,)
        ).fetchone()
    if row is None:
        return {"chunk_cursor": 0, "document_id": None}
    return {
        "chunk_cursor": row["chunk_cursor"],
        "document_id": str(row["document_id"]) if row["document_id"] else None,
    }


def save_first_run_state(material_id: int, document_id: str, total_chunks: int) -> None:
    """Called once (cursor=0) to persist the document_id and total chunk count."""
    with get_db() as conn:
        conn.execute(
            """UPDATE material_embed_jobs
               SET document_id = %s, total_chunks_detected = %s
               WHERE material_id = %s""",
            (document_id, total_chunks, material_id)
        )


def advance_cursor(material_id: int, next_cursor: int) -> None:
    """Persist the next chunk index to resume from on the next invocation."""
    with get_db() as conn:
        conn.execute(
            "UPDATE material_embed_jobs SET chunk_cursor = %s WHERE material_id = %s",
            (next_cursor, material_id)
        )
