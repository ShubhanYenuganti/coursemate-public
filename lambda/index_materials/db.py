import json
import os
import psycopg
from contextlib import contextmanager


@contextmanager
def get_db():
    url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(url, row_factory=psycopg.rows.dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_job(material_id: int, status: str, error: str = None) -> None:
    with get_db() as conn:
        if status == "processing":
            conn.execute(
                """UPDATE material_embed_jobs
                   SET status = 'processing', started_at = NOW()
                   WHERE material_id = %s""",
                (material_id,),
            )
        elif status == "done":
            conn.execute(
                """UPDATE material_embed_jobs
                   SET status = 'done', completed_at = NOW()
                   WHERE material_id = %s""",
                (material_id,),
            )
        elif status in ("failed", "skipped"):
            conn.execute(
                """UPDATE material_embed_jobs
                   SET status = %s, error_message = %s
                   WHERE material_id = %s""",
                (status, error, material_id),
            )


def store_page_texts(conn, material_id: int, page_rows: list[dict]) -> None:
    def _execute_with_savepoint(sql: str, params: tuple) -> None:
        transaction = getattr(conn, "transaction", None)
        if callable(transaction):
            with transaction():
                conn.execute(sql, params)
        else:
            conn.execute(sql, params)

    for row in page_rows:
        params = (
            material_id,
            row["page_number"],
            row.get("text_content"),
            row.get("has_images", False),
            row.get("section_name"),
            json.dumps(row.get("section_path", [])),
        )
        try:
            _execute_with_savepoint(
                """INSERT INTO material_page_text
                       (material_id, page_number, text_content, has_images, section_name,
                        section_path)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (material_id, page_number) DO UPDATE
                   SET text_content = EXCLUDED.text_content,
                       has_images   = EXCLUDED.has_images,
                       section_name = EXCLUDED.section_name,
                       section_path = EXCLUDED.section_path""",
                params,
            )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) != "42703" and exc.__class__.__name__ != "UndefinedColumn":
                raise
            conn.execute(
                """INSERT INTO material_page_text
                       (material_id, page_number, text_content, has_images, section_name)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (material_id, page_number) DO UPDATE
                   SET text_content = EXCLUDED.text_content,
                       has_images   = EXCLUDED.has_images,
                       section_name = EXCLUDED.section_name""",
                params[:-1],
            )


def store_page_index(conn, material_id: int, index_dict: dict) -> None:
    conn.execute(
        """INSERT INTO material_page_index (material_id, doc_type, index_json, page_count)
           VALUES (%s, %s, %s::jsonb, %s)
           ON CONFLICT (material_id) DO UPDATE
           SET doc_type    = EXCLUDED.doc_type,
               index_json  = EXCLUDED.index_json,
               page_count  = EXCLUDED.page_count,
               updated_at  = now()""",
        (
            material_id,
            index_dict["doc_type"],
            json.dumps(index_dict),
            index_dict.get("page_count"),
        ),
    )


def store_course_index(
    conn,
    material_id: int,
    course_id: int,
    material_title: str,
    doc_type: str,
    page_count: int,
    summary: str,
) -> None:
    conn.execute(
        """INSERT INTO course_material_index
               (course_id, material_id, material_title, doc_type, page_count, material_summary)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (course_id, material_id) DO UPDATE
               SET material_title   = EXCLUDED.material_title,
                   doc_type         = EXCLUDED.doc_type,
                   page_count       = EXCLUDED.page_count,
                   material_summary = EXCLUDED.material_summary,
                   updated_at       = now()""",
        (course_id, material_id, material_title, doc_type, page_count, summary),
    )


def store_metadata_tags(conn, course_id: int, material_id: int, tags: list[str]) -> None:
    conn.execute(
        """UPDATE course_material_index
           SET metadata_tags = %s::jsonb, updated_at = now()
           WHERE course_id = %s AND material_id = %s""",
        (json.dumps(tags), course_id, material_id),
    )


def load_course_materials_for_relations(conn, course_id: int) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        """SELECT material_id, material_title, doc_type, material_summary, metadata_tags
           FROM course_material_index
           WHERE course_id = %s""",
        (course_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def store_material_relations(conn, relations: list[dict]) -> None:
    for rel in relations:
        conn.execute(
            """INSERT INTO course_material_relations
                   (course_id, source_id, target_id, relation_type, shared_tags, similarity_score)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s)
               ON CONFLICT (course_id, source_id, target_id) DO UPDATE
               SET relation_type    = EXCLUDED.relation_type,
                   shared_tags      = EXCLUDED.shared_tags,
                   similarity_score = EXCLUDED.similarity_score""",
            (
                rel["course_id"],
                rel["source_id"],
                rel["target_id"],
                rel["relation_type"],
                json.dumps(rel.get("shared_tags", [])),
                rel.get("similarity_score"),
            ),
        )
