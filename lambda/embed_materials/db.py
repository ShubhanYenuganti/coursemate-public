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
