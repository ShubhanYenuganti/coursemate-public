"""
AWS Lambda handler — embed_materials

Triggered by S3 ObjectCreated events on prefix materials/.

Pipeline:
  1. Resolve the S3 key → material DB record (with doc_type, week)
  2. Download raw file bytes from S3
  3. Dispatch to format-specific extractor for chunk_text
  4. Type-specific chunking via chunkers.chunk_by_type() → (parent, children)
  5. Embed parent first via Jina v4 (visual for slides/quiz/exam, text otherwise)
  6. INSERT parent → get DB id
  7. Set parent_id on all children
  8. Embed children
  9. INSERT all children
  10. Update material_embed_jobs status
"""
import boto3
import os

from db import get_db, insert_parent_chunk, insert_child_chunk
from embedder import embed_chunks
from chunkers import chunk_by_type

from extractors.pdf   import extract_pdf
from extractors.docx  import extract_docx
from extractors.txt   import extract_txt
from extractors.image import extract_image
from extractors.svg   import extract_svg
from extractors.xlsx  import extract_xlsx
from extractors.csv_  import extract_csv

EXTRACTOR_MAP = {
    'application/pdf':
        extract_pdf,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        extract_docx,
    'text/plain':
        extract_txt,
    'image/jpeg':
        extract_image,
    'image/png':
        extract_image,
    'image/gif':
        extract_image,
    'image/svg+xml':
        extract_svg,
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        extract_xlsx,
    'text/csv':
        extract_csv,
}

s3 = boto3.client('s3')
BUCKET = os.environ['AWS_S3_BUCKET_NAME']


# ── job status helpers ─────────────────────────────────────────────────────────

def _update_job(conn, material_id: int, status: str,
                error: str = None, chunks_created: int = None) -> None:
    if status == 'processing':
        conn.execute("""
            UPDATE material_embed_jobs
            SET status = 'processing', started_at = CURRENT_TIMESTAMP
            WHERE material_id = %s
        """, (material_id,))
    elif status == 'done':
        conn.execute("""
            UPDATE material_embed_jobs
            SET status = 'done',
                completed_at = CURRENT_TIMESTAMP,
                chunks_created = %s
            WHERE material_id = %s
        """, (chunks_created, material_id))
    elif status in ('failed', 'skipped'):
        conn.execute("""
            UPDATE material_embed_jobs
            SET status = %s, error_message = %s
            WHERE material_id = %s
        """, (status, error, material_id))


def mark_job(material_id: int, status: str,
             error: str = None, chunks_created: int = None, conn=None) -> None:
    """Update the embed job status. Pass conn to reuse an existing transaction."""
    if conn is not None:
        _update_job(conn, material_id, status, error=error, chunks_created=chunks_created)
    else:
        with get_db() as db:
            _update_job(db, material_id, status, error=error, chunks_created=chunks_created)


# ── main handler ───────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    s3_key = event['Records'][0]['s3']['object']['key']

    # 1. Resolve material record from the S3 key embedded in file_url
    with get_db() as db:
        row = db.execute(
            "SELECT id, course_id, file_type, doc_type, week FROM materials WHERE file_url LIKE %s",
            (f'%{s3_key}',)
        ).fetchone()

    if not row:
        return

    material_id = row['id']
    course_id   = row['course_id']
    file_type   = row['file_type']
    doc_type    = row['doc_type'] or 'default'
    week        = row['week']

    extractor = EXTRACTOR_MAP.get(file_type)
    if not extractor:
        mark_job(material_id, 'skipped', error=f'No extractor for file_type: {file_type!r}')
        return

    mark_job(material_id, 'processing')

    try:
        # 2. Download file bytes from S3
        obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
        file_bytes = obj['Body'].read()

        # 3. Pass 1 — format-specific extraction
        raw_chunks = extractor(file_bytes)

        if not raw_chunks:
            mark_job(material_id, 'skipped', error='No extractable text found')
            return

        # 4. Type-specific chunking
        material_meta = {
            'id': material_id,
            'course_id': course_id,
            'doc_type': doc_type,
            'week': week,
        }

        # hw_solution needs DB conn for cross-referencing instruction chunks
        if doc_type == 'hw_solution':
            with get_db() as db:
                parent, children = chunk_by_type(doc_type, raw_chunks, material_meta, conn=db)
        else:
            parent, children = chunk_by_type(doc_type, raw_chunks, material_meta)

        source_type = doc_type
        # Only pass pdf_bytes for visual embedding (slides/quiz/exam from PDF)
        pdf_bytes = file_bytes if file_type == 'application/pdf' else None

        # 5. Embed parent first
        [parent] = embed_chunks([parent], source_type=source_type, pdf_bytes=pdf_bytes)

        # 6. INSERT parent → get DB id
        with get_db() as db:
            parent_db_id = insert_parent_chunk(db, material_id, course_id, 0, parent)

        # 7. Set parent_id on all children
        for child in children:
            child['parent_id'] = parent_db_id

        # 8. Embed children
        children = embed_chunks(children, source_type=source_type, pdf_bytes=pdf_bytes)

        # 9. INSERT all children + mark done in a single transaction
        with get_db() as db:
            for idx, child in enumerate(children):
                insert_child_chunk(db, material_id, course_id, idx + 1, child, parent_db_id)
            mark_job(material_id, 'done', chunks_created=len(children) + 1, conn=db)

    except Exception as exc:
        mark_job(material_id, 'failed', error=str(exc))
        raise
