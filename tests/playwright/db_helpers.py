"""
Thin read/write helpers for accessing the CourseMate Postgres database in tests.

Reuses api/db.py (psycopg3, connection pool, dict rows) — just loads .env first.

Usage:
    from tests.playwright.db_helpers import query, query_one, dev_user_id

    rows = query("SELECT * FROM courses WHERE created_by = %s", (dev_user_id(),))
    row  = query_one("SELECT * FROM users WHERE google_id = %s", (dev_user_id(),))
"""

import os
import sys
from pathlib import Path

# Ensure project root and api/ are importable before touching api.db
_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load .env so DATABASE_URL (and DEV_USER_GOOGLE_ID) are available
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from api.db import get_db  # noqa: E402 — must follow load_dotenv


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SQL query and return all rows as dicts."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    """Run a SQL query and return the first row as a dict, or None."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()


def dev_user_id() -> str:
    """Return the google_id of the local dev bypass user."""
    gid = os.environ.get("DEV_USER_GOOGLE_ID")
    if not gid:
        raise EnvironmentError("DEV_USER_GOOGLE_ID not set in .env")
    return gid


def dev_user_db_id() -> int:
    """Return the integer PK of the dev user in the users table."""
    row = query_one("SELECT id FROM users WHERE google_id = %s", (dev_user_id(),))
    if not row:
        raise LookupError(f"Dev user {dev_user_id()} not found in users table")
    return row["id"]
