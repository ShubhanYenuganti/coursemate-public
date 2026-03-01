"""
AWS Lambda handler — embed_materials

Triggered by S3 ObjectCreated events on prefix materials/.

Pipeline:
  1. Resolve the S3 key → material DB record
  2. Dispatch to the format-specific Pass 1 extractor
  3. Run passes 2–4 (size normalization, overlap stitching, summary chunk)
  4. Generate sentence-transformer embeddings (all-MiniLM-L6-v2, dim=384)
  5. Upsert chunks into material_chunks; update material_embed_jobs status
"""
import boto3
import os

from db import get_db
from embedder import embed_chunks
from chunker import process_chunks

from extractors.pdf   import extract_pdf
from extractors.docx  import extract_docx
from extractors.txt   import extract_txt
from extractors.image import extract_image
from extractors.svg   import extract_svg
from extractors.xlsx  import extract_xlsx
from extractors.csv_  import extract_csv

# (extractor_fn, has_headings)
EXTRACTOR_MAP = {
    'application/pdf':
        (extract_pdf,   True),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        (extract_docx,  True),
    'text/plain':
        (extract_txt,   False),
    'image/jpeg':
        (extract_image, False),
    'image/png':
        (extract_image, False),
    'image/gif':
        (extract_image, False),
    'image/svg+xml':
        (extract_svg,   False),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        (extract_xlsx,  False),
    'text/csv':
        (extract_csv,   False),
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
            "SELECT id, course_id, file_type FROM materials WHERE file_url LIKE %s",
            (f'%{s3_key}',)
        ).fetchone()

    if not row:
        # confirm_upload hasn't run yet (race condition) — Lambda may safely skip.
        # The embed job won't exist either, so there's nothing to mark.
        return

    material_id = row['id']
    course_id   = row['course_id']
    file_type   = row['file_type']

    entry = EXTRACTOR_MAP.get(file_type)
    if not entry:
        mark_job(material_id, 'skipped', error=f'No extractor for file_type: {file_type!r}')
        return

    extractor, has_headings = entry
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

        # 4. Passes 2–4 — size normalization, overlap, summary
        chunks = process_chunks(raw_chunks, has_headings=has_headings)

        # 5. Generate embeddings (adds 'embedding' key to each dict)
        chunks = embed_chunks(chunks)

        # 6. Upsert all chunks and mark done in a single transaction
        with get_db() as db:
            for idx, chunk in enumerate(chunks):
                embedding_str = '[' + ','.join(str(x) for x in chunk['embedding']) + ']'
                db.execute("""
                    INSERT INTO material_chunks
                        (material_id, course_id, chunk_index, chunk_text, chunk_type,
                         page_number, token_count, embedding, model_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (material_id, chunk_index) DO UPDATE
                        SET chunk_text  = EXCLUDED.chunk_text,
                            embedding   = EXCLUDED.embedding,
                            model_name  = EXCLUDED.model_name
                """, (
                    material_id, course_id, idx,
                    chunk['text'], chunk['chunk_type'], chunk.get('page_number'),
                    chunk['token_count'], embedding_str, 'all-MiniLM-L6-v2',
                ))
            mark_job(material_id, 'done', chunks_created=len(chunks), conn=db)

    except Exception as exc:
        mark_job(material_id, 'failed', error=str(exc))
        raise
