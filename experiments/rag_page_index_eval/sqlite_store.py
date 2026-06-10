from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS material_page_text (
            material_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            text_content TEXT,
            has_images INTEGER NOT NULL DEFAULT 0,
            section_name TEXT,
            section_path TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (material_id, page_number)
        );

        CREATE TABLE IF NOT EXISTS material_page_index (
            material_id INTEGER PRIMARY KEY,
            doc_type TEXT NOT NULL,
            index_json TEXT NOT NULL,
            page_count INTEGER,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS course_material_index (
            course_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            material_title TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            page_count INTEGER,
            material_summary TEXT,
            metadata_tags TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (course_id, material_id)
        );

        CREATE TABLE IF NOT EXISTS course_material_relations (
            course_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            shared_tags TEXT NOT NULL DEFAULT '[]',
            similarity_score REAL,
            PRIMARY KEY (course_id, source_id, target_id)
        );

        CREATE TABLE IF NOT EXISTS qasper_material_map (
            paper_id TEXT PRIMARY KEY,
            material_id INTEGER NOT NULL UNIQUE,
            course_id INTEGER NOT NULL,
            title TEXT
        );
        """
    )
    conn.commit()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def upsert_material_map(
    conn: sqlite3.Connection,
    *,
    paper_id: str,
    material_id: int,
    course_id: int,
    title: str,
) -> None:
    conn.execute(
        """
        INSERT INTO qasper_material_map (paper_id, material_id, course_id, title)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(paper_id) DO UPDATE SET
            material_id = excluded.material_id,
            course_id = excluded.course_id,
            title = excluded.title
        """,
        (paper_id, material_id, course_id, title),
    )


def store_page_texts(conn: sqlite3.Connection, material_id: int, page_rows: list[dict]) -> None:
    for row in page_rows:
        conn.execute(
            """
            INSERT INTO material_page_text
                (material_id, page_number, text_content, has_images, section_name, section_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(material_id, page_number) DO UPDATE SET
                text_content = excluded.text_content,
                has_images = excluded.has_images,
                section_name = excluded.section_name,
                section_path = excluded.section_path
            """,
            (
                material_id,
                row["page_number"],
                row.get("text_content"),
                1 if row.get("has_images", False) else 0,
                row.get("section_name"),
                _json(row.get("section_path", [])),
            ),
        )


def store_page_index(conn: sqlite3.Connection, material_id: int, index_dict: dict) -> None:
    conn.execute(
        """
        INSERT INTO material_page_index (material_id, doc_type, index_json, page_count, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(material_id) DO UPDATE SET
            doc_type = excluded.doc_type,
            index_json = excluded.index_json,
            page_count = excluded.page_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            material_id,
            index_dict["doc_type"],
            _json(index_dict),
            index_dict.get("page_count"),
        ),
    )


def store_course_index(
    conn: sqlite3.Connection,
    *,
    material_id: int,
    course_id: int,
    material_title: str,
    doc_type: str,
    page_count: int,
    summary: str,
    metadata_tags: list[str] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO course_material_index
            (course_id, material_id, material_title, doc_type, page_count, material_summary, metadata_tags, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(course_id, material_id) DO UPDATE SET
            material_title = excluded.material_title,
            doc_type = excluded.doc_type,
            page_count = excluded.page_count,
            material_summary = excluded.material_summary,
            metadata_tags = excluded.metadata_tags,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            course_id,
            material_id,
            material_title,
            doc_type,
            page_count,
            summary,
            _json(metadata_tags or []),
        ),
    )


def store_material_relation(
    conn: sqlite3.Connection,
    *,
    course_id: int,
    source_id: int,
    target_id: int,
    relation_type: str,
    shared_tags: list[str] | None = None,
    similarity_score: float | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO course_material_relations
            (course_id, source_id, target_id, relation_type, shared_tags, similarity_score)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(course_id, source_id, target_id) DO UPDATE SET
            relation_type = excluded.relation_type,
            shared_tags = excluded.shared_tags,
            similarity_score = excluded.similarity_score
        """,
        (
            course_id,
            source_id,
            target_id,
            relation_type,
            _json(shared_tags or []),
            similarity_score,
        ),
    )


def paper_to_material_map(conn: sqlite3.Connection, course_id: int | None = None) -> dict[str, int]:
    if course_id is None:
        rows = conn.execute("SELECT paper_id, material_id FROM qasper_material_map").fetchall()
    else:
        rows = conn.execute(
            "SELECT paper_id, material_id FROM qasper_material_map WHERE course_id = ?",
            (course_id,),
        ).fetchall()
    return {str(row["paper_id"]): int(row["material_id"]) for row in rows}


def material_to_paper_map(conn: sqlite3.Connection, course_id: int | None = None) -> dict[int, str]:
    return {material_id: paper_id for paper_id, material_id in paper_to_material_map(conn, course_id).items()}
