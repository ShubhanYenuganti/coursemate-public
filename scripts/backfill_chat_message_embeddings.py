"""
Backfill chat_messages.message_embedding from legacy messages.embedding.

Matching strategy:
1) chats.session_uuid = messages.session_id
2) role equality
3) nearest created_at within a configurable time window
4) optional normalized-content hash exact match

Usage:
  DATABASE_URL=... python scripts/backfill_chat_message_embeddings.py
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import timedelta

import psycopg

TIME_WINDOW_MINUTES = int(os.environ.get("BACKFILL_TIME_WINDOW_MINUTES", "60"))
DRY_RUN = os.environ.get("BACKFILL_DRY_RUN", "false").lower() == "true"

_WS_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip()).lower()


def _hash_text(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


@dataclass
class Stats:
    matched: int = 0
    unmatched: int = 0
    ambiguous: int = 0
    skipped_no_embedding: int = 0
    skipped_existing_embedding: int = 0


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    stats = Stats()
    window = timedelta(minutes=TIME_WINDOW_MINUTES)

    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT m.id, m.session_id, m.role, m.content, m.embedding, m.created_at
                FROM messages m
                WHERE m.embedding IS NOT NULL
                ORDER BY m.created_at ASC
            """)
            legacy_rows = cursor.fetchall()

        for row in legacy_rows:
            legacy_id = row["id"]
            session_id = row["session_id"]
            role = row["role"]
            content = row["content"] or ""
            embedding = row["embedding"]
            created_at = row["created_at"]

            if embedding is None:
                stats.skipped_no_embedding += 1
                continue

            content_hash = _hash_text(content)

            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT cm.id, cm.content, cm.created_at, cm.message_embedding
                    FROM chat_messages cm
                    JOIN chats c ON c.id = cm.chat_id
                    WHERE c.session_uuid = %s
                      AND cm.role = %s
                      AND cm.created_at BETWEEN %s AND %s
                      AND cm.is_deleted = FALSE
                    ORDER BY ABS(EXTRACT(EPOCH FROM (cm.created_at - %s))) ASC
                    LIMIT 10
                """, (
                    session_id,
                    role,
                    created_at - window,
                    created_at + window,
                    created_at,
                ))
                candidates = cursor.fetchall()

            if not candidates:
                stats.unmatched += 1
                continue

            # Prefer exact normalized content match among nearest candidates.
            exact = [c for c in candidates if _hash_text(c["content"] or "") == content_hash]
            if len(exact) > 1:
                stats.ambiguous += 1
                continue
            chosen = exact[0] if len(exact) == 1 else candidates[0]

            if chosen["message_embedding"] is not None:
                stats.skipped_existing_embedding += 1
                continue

            if not DRY_RUN:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE chat_messages
                        SET message_embedding = %s::vector
                        WHERE id = %s
                    """, (embedding, chosen["id"]))

            stats.matched += 1

        if DRY_RUN:
            conn.rollback()
        else:
            conn.commit()

    print("Backfill complete")
    print(f"matched={stats.matched}")
    print(f"unmatched={stats.unmatched}")
    print(f"ambiguous={stats.ambiguous}")
    print(f"skipped_no_embedding={stats.skipped_no_embedding}")
    print(f"skipped_existing_embedding={stats.skipped_existing_embedding}")
    print(f"dry_run={DRY_RUN}")


if __name__ == "__main__":
    main()
