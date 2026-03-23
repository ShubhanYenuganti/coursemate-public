"""
Lightweight database connection for Lambda (no pooling — Lambda manages lifecycle).
Provides upsert helpers for parent and child material_chunks.
"""
import json
import os
import psycopg
from contextlib import contextmanager


@contextmanager
def get_db():
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


def insert_parent_chunk(conn, material_id: int, course_id: int, chunk_index: int,
                        chunk: dict) -> int:
    """
    Insert a parent chunk (is_parent=True) and return the DB-assigned id.
    Used first so children can reference parent_id.
    """
    embedding_str = '[' + ','.join(str(x) for x in chunk['embedding']) + ']'
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO material_chunks
            (material_id, course_id, chunk_index, chunk_text, chunk_type,
             page_number, token_count, embedding, model_name,
             is_parent, source_type, week, section_title,
             position_in_doc, problem_id, related_chunk_ids)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s,
                TRUE, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (material_id, chunk_index) DO UPDATE
            SET chunk_text        = EXCLUDED.chunk_text,
                embedding         = EXCLUDED.embedding,
                model_name        = EXCLUDED.model_name,
                is_parent         = TRUE,
                source_type       = EXCLUDED.source_type,
                week              = EXCLUDED.week,
                section_title     = EXCLUDED.section_title,
                position_in_doc   = EXCLUDED.position_in_doc,
                problem_id        = EXCLUDED.problem_id,
                related_chunk_ids = EXCLUDED.related_chunk_ids
        RETURNING id
    """, (
        material_id, course_id, chunk_index,
        chunk['chunk_text'], chunk.get('chunk_type', 'paragraph'),
        chunk.get('page_number'), chunk.get('token_count', 0),
        embedding_str, 'jina-embeddings-v4',
        chunk.get('source_type'), chunk.get('week'),
        chunk.get('section_title'), chunk.get('position_in_doc'),
        chunk.get('problem_id'),
        json.dumps(chunk.get('related_chunk_ids', [])),
    ))
    row = cursor.fetchone()
    cursor.close()
    return row['id']


def insert_child_chunk(conn, material_id: int, course_id: int, chunk_index: int,
                       chunk: dict, parent_db_id: int) -> None:
    """Insert a child chunk referencing the parent's DB id."""
    embedding_str = '[' + ','.join(str(x) for x in chunk['embedding']) + ']'
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO material_chunks
            (material_id, course_id, chunk_index, chunk_text, chunk_type,
             page_number, token_count, embedding, model_name,
             parent_id, is_parent, source_type, week, section_title,
             position_in_doc, problem_id, related_chunk_ids)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s,
                %s, FALSE, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (material_id, chunk_index) DO UPDATE
            SET chunk_text        = EXCLUDED.chunk_text,
                embedding         = EXCLUDED.embedding,
                model_name        = EXCLUDED.model_name,
                parent_id         = EXCLUDED.parent_id,
                is_parent         = FALSE,
                source_type       = EXCLUDED.source_type,
                week              = EXCLUDED.week,
                section_title     = EXCLUDED.section_title,
                position_in_doc   = EXCLUDED.position_in_doc,
                problem_id        = EXCLUDED.problem_id,
                related_chunk_ids = EXCLUDED.related_chunk_ids
    """, (
        material_id, course_id, chunk_index,
        chunk['chunk_text'], chunk.get('chunk_type', 'paragraph'),
        chunk.get('page_number'), chunk.get('token_count', 0),
        embedding_str, 'jina-embeddings-v4',
        parent_db_id,
        chunk.get('source_type'), chunk.get('week'),
        chunk.get('section_title'), chunk.get('position_in_doc'),
        chunk.get('problem_id'),
        json.dumps(chunk.get('related_chunk_ids', [])),
    ))
    cursor.close()
