"""
AWS Lambda handler — embed_materials (Voyage AI pipeline)

Two modes, selected by event shape:

  Launcher mode  (S3 ObjectCreated event — "Records" key present)
    Starts a Step Functions execution and returns immediately.
    The execution passes {s3_key, cursor: 0} to the first worker invocation.

  Worker mode  (Step Functions task event — "s3_key" key present)
    Downloads the PDF, embeds chunks starting from `cursor`, stops before
    the Lambda timeout, and returns {status, s3_key, cursor} to Step Functions.
    Step Functions loops until status == "done".
"""
import asyncio
import json
import os

import boto3

from db import get_db
from worker import ingest_document

s3 = boto3.client('s3')
sfn_client = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

BUCKET = os.environ['AWS_S3_BUCKET_NAME']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']


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
                SET status = 'done', completed_at = CURRENT_TIMESTAMP
                WHERE material_id = %s
            """, (material_id,))
        elif status in ('failed', 'skipped'):
            db.execute("""
                UPDATE material_embed_jobs
                SET status = %s, error_message = %s
                WHERE material_id = %s
            """, (status, error, material_id))


def _resolve_material(s3_key: str):
    """Return the material DB row for the given S3 key, or None."""
    with get_db() as db:
        return db.execute(
            "SELECT id, course_id, file_type, doc_type FROM materials WHERE file_url LIKE %s",
            (f'%{s3_key}',)
        ).fetchone()


def lambda_handler(event, context):
    # ── Launcher mode: S3 ObjectCreated ──────────────────────────────────────
    if 'Records' in event:
        s3_key = event['Records'][0]['s3']['object']['key']
        sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps({'s3_key': s3_key, 'cursor': 0}),
        )
        return {'status': 'launched'}

    # ── Worker mode: invoked by Step Functions ────────────────────────────────
    return _worker(event, context)


def _worker(event: dict, context) -> dict:
    s3_key = event['s3_key']
    cursor = int(event.get('cursor', 0))

    # 1. Resolve material record
    row = _resolve_material(s3_key)
    if not row:
        # confirm_upload hasn't run yet (race condition) — nothing to do
        return {'status': 'done', 's3_key': s3_key, 'cursor': 0}

    material_id = row['id']
    course_id   = str(row['course_id']) if row['course_id'] else None
    file_type   = row['file_type']
    doc_type    = row['doc_type'] or 'general'

    # 2. Only PDFs are supported
    if file_type != 'application/pdf':
        _mark_job(material_id, 'skipped',
                  error=f'Non-PDF not supported in Voyage pipeline: {file_type!r}')
        return {'status': 'done', 's3_key': s3_key, 'cursor': 0}

    # 3. Mark processing on the very first invocation
    if cursor == 0:
        _mark_job(material_id, 'processing')

    try:
        # 4. Download from S3
        obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
        file_bytes = obj['Body'].read()

        # 5. Run async ingestion (resumable)
        result = asyncio.run(ingest_document(
            material_id=material_id,
            course_id=course_id,
            s3_key=s3_key,
            doc_type=doc_type,
            file_bytes=file_bytes,
            cursor=cursor,
            lambda_context=context,
        ))

        if result['needs_continuation']:
            # Step Functions will reinvoke us with the new cursor
            return {
                'status': 'needs_continuation',
                's3_key': s3_key,
                'cursor': result['next_cursor'],
            }

        # All chunks embedded
        _mark_job(material_id, 'done')
        return {'status': 'done', 's3_key': s3_key, 'cursor': result['next_cursor']}

    except Exception as exc:
        _mark_job(material_id, 'failed', error=str(exc))
        return {'status': 'failed', 's3_key': s3_key, 'cursor': cursor, 'error': str(exc)}
