"""
AWS Lambda handler — embed_materials (Voyage AI pipeline)

Triggered by S3 ObjectCreated events on prefix materials/.

Pipeline:
  1. Resolve S3 key → material DB record (with doc_type)
  2. Skip non-PDF files
  3. Mark job as processing
  4. Download file bytes from S3
  5. Run asyncio.run(ingest_document(...)) — async Voyage AI + asyncpg worker
  6. Mark job done/failed
"""
import asyncio
import os

import boto3

from db import get_db
from worker import ingest_document

s3 = boto3.client('s3')
BUCKET = os.environ['AWS_S3_BUCKET_NAME']


def _mark_job(material_id: int, status: str,
              error: str = None, chunks_created: int = None) -> None:
    with get_db() as db:
        if status == 'processing':
            db.execute("""
                UPDATE material_embed_jobs
                SET status = 'processing', started_at = CURRENT_TIMESTAMP
                WHERE material_id = %s
            """, (material_id,))
        elif status == 'done':
            db.execute("""
                UPDATE material_embed_jobs
                SET status = 'done', completed_at = CURRENT_TIMESTAMP,
                    chunks_created = %s
                WHERE material_id = %s
            """, (chunks_created, material_id))
        elif status in ('failed', 'skipped'):
            db.execute("""
                UPDATE material_embed_jobs
                SET status = %s, error_message = %s
                WHERE material_id = %s
            """, (status, error, material_id))


def lambda_handler(event, context):
    s3_key = event['Records'][0]['s3']['object']['key']

    # 1. Resolve material record
    with get_db() as db:
        row = db.execute(
            "SELECT id, course_id, file_type, doc_type FROM materials WHERE file_url LIKE %s",
            (f'%{s3_key}',)
        ).fetchone()

    if not row:
        # confirm_upload hasn't run yet (race condition) — safe to skip
        return

    material_id = row['id']
    course_id   = str(row['course_id']) if row['course_id'] else None
    file_type   = row['file_type']
    doc_type    = row['doc_type'] or 'general'

    # 2. New pipeline only handles PDFs
    if file_type != 'application/pdf':
        _mark_job(material_id, 'skipped',
                  error=f'Non-PDF not supported in Voyage pipeline: {file_type!r}')
        return

    _mark_job(material_id, 'processing')

    try:
        # 3. Download from S3
        obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
        file_bytes = obj['Body'].read()

        # 4. Run async ingestion
        total = asyncio.run(ingest_document(
            material_id=material_id,
            course_id=course_id,
            s3_key=s3_key,
            doc_type=doc_type,
            file_bytes=file_bytes,
        ))

        _mark_job(material_id, 'done', chunks_created=total)

    except Exception as exc:
        _mark_job(material_id, 'failed', error=str(exc))
        raise
