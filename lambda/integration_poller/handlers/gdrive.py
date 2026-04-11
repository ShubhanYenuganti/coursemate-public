"""
Google Drive source point handler for integration_poller.

sync_source_point(source_point, token):
  - Lists all files in the Drive folder (source_point['external_id'] is the folder ID)
  - Exports/downloads each file as PDF (Drive export API for native Google types, direct download for PDFs)
  - Uploads each file to S3 and upserts into `materials`
  - Triggers the embed_materials Step Function per file
  - Updates last_synced_at on success
"""
import io
import json
import os
import traceback

import boto3
import requests

from db import get_db
from .utils import _needs_ingest

DRIVE_API_BASE = 'https://www.googleapis.com/drive/v3'
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

GOOGLE_DOC_MIME = 'application/vnd.google-apps.document'
GOOGLE_SHEET_MIME = 'application/vnd.google-apps.spreadsheet'
GOOGLE_SLIDES_MIME = 'application/vnd.google-apps.presentation'
GOOGLE_NATIVE_TYPES = frozenset([GOOGLE_DOC_MIME, GOOGLE_SHEET_MIME, GOOGLE_SLIDES_MIME])

s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sfn = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

BUCKET = os.environ.get('AWS_S3_BUCKET_NAME', '')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', '')


# ─── Drive API helpers ───────────────────────────────────────────────────────

def _drive_get(path, token, params=None, stream=False):
    resp = requests.get(
        f'{DRIVE_API_BASE}/{path}',
        headers={'Authorization': f'Bearer {token}'},
        params=params,
        timeout=60,
        stream=stream,
    )
    resp.raise_for_status()
    return resp



def _fetch_file_metadata(file_id: str, token: str) -> dict | None:
    """Fetch metadata for a single Drive file. Returns None on error."""
    try:
        resp = _drive_get(
            f'files/{file_id}',
            token,
            params={'fields': 'id,name,mimeType,modifiedTime'},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f'[gdrive_handler] Failed to fetch metadata for file_id={file_id}: {exc}')
        return None


def _get_drive_file_as_pdf(file_id, mime_type, token):
    """
    Export or download a Drive file as PDF bytes.
    Uses files.export for Google-native types; files.get?alt=media for native PDFs.
    Raises ValueError if the result exceeds 50 MB.
    """
    if mime_type in GOOGLE_NATIVE_TYPES:
        resp = _drive_get(
            f'files/{file_id}/export',
            token,
            params={'mimeType': 'application/pdf'},
            stream=True,
        )
    else:
        resp = _drive_get(
            f'files/{file_id}',
            token,
            params={'alt': 'media'},
            stream=True,
        )

    content = resp.content
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f'File {file_id} exceeds 50 MB limit ({len(content)} bytes)')
    return content


# ─── Ingestion helpers ───────────────────────────────────────────────────────

def _upsert_material(
    user_id, course_id, source_point_id, file_id, file_name, modified_time
):
    """
    Return (material_id, needs_ingest).
    All materials are pre-registered via bulk_upsert_sync before the poller runs.
    Returns (id, False) if modifiedTime is unchanged — caller should check doc_type drift then skip.
    Returns (id, True) if modifiedTime has advanced since last ingest.
    Returns (None, False) if no materials row exists (should not happen in normal flow).
    """
    with get_db() as db:
        existing = db.execute(
            "SELECT id, external_last_edited, file_type FROM materials WHERE external_id = %s AND source_type = 'gdrive'",
            (file_id,)
        ).fetchone()

        if not existing:
            print(f'[gdrive_handler] No material row for file_id={file_id} — skipping')
            return None, False

        if existing.get('file_type') != 'application/pdf':
            db.execute(
                "UPDATE materials SET file_type = 'application/pdf' WHERE id = %s",
                (existing['id'],)
            )
        db.execute(
            "UPDATE materials SET integration_source_point_id = %s WHERE id = %s",
            (source_point_id, existing['id'])
        )
        if not _needs_ingest(modified_time, existing.get('external_last_edited')):
            return existing['id'], False
        return existing['id'], True


def _doc_type_changed(material_id: int) -> bool:
    """Return True if materials.doc_type differs from the doc_type used in the last ingest.

    Compares materials.doc_type (current user setting) against documents.source_type
    (the doc_type that was active when chunks were last generated). Returns False if
    no documents row exists — no prior ingest means no drift to detect.
    """
    with get_db() as db:
        row = db.execute(
            """
            SELECT m.doc_type, d.source_type AS last_doc_type
            FROM materials m
            LEFT JOIN documents d ON d.material_id = m.id
            WHERE m.id = %s
            ORDER BY d.ingested_at DESC NULLS LAST
            LIMIT 1
            """,
            (material_id,)
        ).fetchone()
    if not row or not row.get('last_doc_type'):
        return False
    return row['doc_type'] != row['last_doc_type']


def _delete_old_chunks(material_id):
    """Delete all embedding chunks for a material before re-ingestion."""
    with get_db() as db:
        db.execute("""
            DELETE FROM chunks
            WHERE document_id IN (
                SELECT id FROM documents WHERE material_id = %s
            )
        """, (material_id,))
        db.execute("DELETE FROM documents WHERE material_id = %s", (material_id,))


def _upload_pdf_to_s3(file_id, pdf_bytes):
    """Upload PDF bytes to S3 and return the S3 key."""
    if not BUCKET:
        raise ValueError('AWS_S3_BUCKET_NAME is not set')
    s3_key = f'gdrive/{file_id}.pdf'
    print(f'[gdrive_handler] Uploading PDF to S3 bucket={BUCKET} key={s3_key} bytes={len(pdf_bytes)}')
    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType='application/pdf',
    )
    return s3_key


def _update_material_after_upload(material_id, s3_key, modified_time):
    bucket = BUCKET
    region = os.environ.get('AWS_REGION', 'us-east-1')
    file_url = f'https://{bucket}.s3.{region}.amazonaws.com/{s3_key}'
    with get_db() as db:
        db.execute("""
            UPDATE materials
            SET file_url = %s, external_last_edited = %s
            WHERE id = %s
        """, (file_url, modified_time, material_id))
    print(f'[gdrive_handler] Updated material after upload material_id={material_id} file_url={file_url}')


def _enqueue_embed_job(material_id):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO material_embed_jobs (material_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (material_id,)
        )
    inserted = cur.rowcount == 1
    print(f'[gdrive_handler] material_embed_jobs upsert material_id={material_id} inserted={inserted}')


def _trigger_embed(s3_key):
    if not STATE_MACHINE_ARN:
        print(f'[gdrive_handler] STATE_MACHINE_ARN not set, skipping embed trigger for key={s3_key}')
        return
    print(f'[gdrive_handler] Triggering embed Step Function arn={STATE_MACHINE_ARN} key={s3_key}')
    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps({'s3_key': s3_key, 'cursor': 0}),
    )


# ─── Main entry point ────────────────────────────────────────────────────────

def sync_source_point(source_point: dict, token: str, force_full_sync: bool = False, external_ids: list | None = None):
    """
    Sync Drive files described by source_point.

    When external_ids is provided (Sync Now path), only those file IDs are processed.
    When external_ids is None (background sweep), all sync=TRUE materials for this
    source point are fetched from the DB and processed.

    token is a valid Google OAuth access token string.
    """
    user_id = source_point['user_id']
    course_id = source_point['course_id']
    source_point_id = source_point['id']
    print(
        f'[gdrive_handler] Starting sync source_point_id={source_point_id} '
        f'course_id={course_id} user_id={user_id} '
        f'force_full_sync={force_full_sync} external_ids={external_ids} '
        f'bucket={BUCKET!r} has_state_machine={bool(STATE_MACHINE_ARN)}'
    )

    # Determine which file IDs to process
    if external_ids is not None:
        # Sync Now path: caller already knows which files to process
        work_ids = external_ids
        print(f'[gdrive_handler] Sync Now path: processing {len(work_ids)} targeted file(s)')
    else:
        # Background sweep path: query DB for all sync=TRUE materials for this source point
        with get_db() as db:
            rows = db.execute(
                """
                SELECT external_id FROM materials
                WHERE integration_source_point_id = %s
                  AND sync = TRUE
                """,
                (source_point_id,)
            ).fetchall()
        work_ids = [r['external_id'] for r in rows]
        print(f'[gdrive_handler] Background sweep path: processing {len(work_ids)} sync=TRUE file(s)')

    # Process each file by fetching its metadata individually
    files_processed = 0
    for file_id in work_ids:
        file_info = _fetch_file_metadata(file_id, token)
        if file_info is None:
            print(f'[gdrive_handler] Skipping file_id={file_id}: metadata fetch failed')
            continue

        file_name = file_info.get('name', f'Drive file {file_id}')
        mime_type = file_info.get('mimeType', '')
        modified_time = file_info.get('modifiedTime', '')

        # Skip subfolders
        if mime_type == 'application/vnd.google-apps.folder':
            print(f'[gdrive_handler] Skipping subfolder file_id={file_id} name={file_name!r}')
            continue

        try:
            material_id, needs_ingest = _upsert_material(
                user_id, course_id, source_point_id, file_id, file_name, modified_time
            )

            if material_id is None:
                continue

            doc_type_drifted = (not needs_ingest and not force_full_sync
                                and _doc_type_changed(material_id))

            if not needs_ingest and not force_full_sync and not doc_type_drifted:
                print(f'[gdrive_handler] Skipping unchanged file={file_id} name={file_name!r}')
                if external_ids is not None:
                    with get_db() as db:
                        db.execute(
                            "UPDATE material_embed_jobs SET status = 'up_to_date' WHERE material_id = %s",
                            (material_id,)
                        )
                        db.execute(
                            "UPDATE materials SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (material_id,)
                        )
                continue

            if doc_type_drifted:
                print(f'[gdrive_handler] doc_type changed for file={file_id} name={file_name!r} — re-ingesting')

            print(f'[gdrive_handler] Ingesting file={file_id} name={file_name!r} mime={mime_type}')

            try:
                pdf_bytes = _get_drive_file_as_pdf(file_id, mime_type, token)
            except ValueError as exc:
                # File exceeds 50 MB or unsupported type
                print(f'[gdrive_handler] Skipping file={file_id}: {exc}')
                continue

            if not needs_ingest:
                # force_full_sync or doc_type changed: clear stale embeddings before re-ingest
                _delete_old_chunks(material_id)
                try:
                    s3.delete_object(Bucket=BUCKET, Key=f'gdrive/{file_id}.pdf')
                except Exception:
                    pass

            s3_key = _upload_pdf_to_s3(file_id, pdf_bytes)
            _update_material_after_upload(material_id, s3_key, modified_time)
            _enqueue_embed_job(material_id)
            _trigger_embed(s3_key)
            files_processed += 1

        except Exception as exc:
            print(f'[gdrive_handler] Failed to ingest file={file_id}: {exc}')
            print(traceback.format_exc())
            # Continue with remaining files

    # Update last_synced_at for this source point
    with get_db() as db:
        db.execute(
            "UPDATE integration_source_points SET last_synced_at = CURRENT_TIMESTAMP WHERE id = %s",
            (source_point_id,)
        )
    print(
        f'[gdrive_handler] Sync complete source_point_id={source_point_id} '
        f'files_in_work_list={len(work_ids)} files_ingested={files_processed}'
    )
