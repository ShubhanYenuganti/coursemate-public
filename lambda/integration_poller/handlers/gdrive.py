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


def _list_folder_files(folder_id, token):
    """Return list of {id, name, mimeType, modifiedTime} for all non-trashed files in folder."""
    files = []
    page_token = None
    while True:
        params = {
            'q': f"'{folder_id}' in parents and trashed=false",
            'fields': 'nextPageToken,files(id,name,mimeType,modifiedTime)',
            'pageSize': 100,
        }
        if page_token:
            params['pageToken'] = page_token
        resp = _drive_get('files', token, params=params)
        data = resp.json()
        files.extend(data.get('files', []))
        page_token = data.get('nextPageToken')
        if not page_token:
            break
    return files


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

def _upsert_material(user_id, course_id, file_id, file_name, modified_time):
    """
    Return (material_id, is_new_or_changed).
    Creates a new materials row on first ingestion, or returns (id, True) if
    modifiedTime has changed since last ingest (so caller re-runs upload+embed).
    Returns (id, False) if file is unchanged — caller should skip.
    """
    with get_db() as db:
        existing = db.execute(
            "SELECT id, file_url, external_last_edited FROM materials WHERE external_id = %s AND source_type = 'gdrive'",
            (file_id,)
        ).fetchone()

        if existing:
            existing_edited = str(existing.get('external_last_edited') or '')
            if existing_edited == modified_time:
                return existing['id'], False
            return existing['id'], True

        row = db.execute("""
            INSERT INTO materials (
                course_id, name, file_url, uploaded_by, file_type,
                visibility, source_type, external_id, external_last_edited
            )
            VALUES (%s, %s, %s, %s, 'application/pdf', 'private', 'gdrive', %s, %s)
            RETURNING id
        """, (
            course_id,
            file_name or f'Drive file {file_id}',
            f'gdrive/{file_id}.pdf',  # placeholder; updated after S3 upload
            user_id,
            file_id,
            modified_time,
        )).fetchone()
        material_id = row['id']

        # Link material to course via material_ids JSONB array
        db.execute(
            """
            UPDATE courses
            SET material_ids = material_ids || %s::jsonb
            WHERE id = %s
              AND NOT material_ids @> %s::jsonb
            """,
            (json.dumps([material_id]), course_id, json.dumps([material_id]))
        )
    return material_id, True


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

def sync_source_point(source_point: dict, token: str, force_full_sync: bool = False):
    """
    Sync all files in the Drive folder described by source_point.
    source_point['external_id'] is the Drive folder ID.
    token is a valid Google OAuth access token string.
    """
    folder_id = source_point['external_id']
    user_id = source_point['user_id']
    course_id = source_point['course_id']
    print(
        f'[gdrive_handler] Starting sync source_point_id={source_point.get("id")} '
        f'folder_id={folder_id} course_id={course_id} user_id={user_id} '
        f'force_full_sync={force_full_sync} bucket={BUCKET!r} has_state_machine={bool(STATE_MACHINE_ARN)}'
    )

    # List all current files in the folder
    try:
        current_files = _list_folder_files(folder_id, token)
    except Exception as exc:
        print(f'[gdrive_handler] Failed to list folder {folder_id}: {exc}')
        raise

    current_file_ids = {f['id'] for f in current_files}
    print(f'[gdrive_handler] Folder {folder_id} contains {len(current_files)} files')

    # Log files that were previously ingested but are no longer in the folder.
    # We intentionally do not mark them inactive; all synced files remain wanted by default.
    with get_db() as db:
        ingested_rows = db.execute(
            """
            SELECT external_id FROM materials
            WHERE course_id = %s AND source_type = 'gdrive'
              AND file_url LIKE 'https://%%'
            """,
            (course_id,)
        ).fetchall()
    ingested_ids = {r['external_id'] for r in ingested_rows}
    removed_ids = ingested_ids - current_file_ids
    if removed_ids:
        print(f'[gdrive_handler] {len(removed_ids)} previously ingested file(s) no longer present in folder: {removed_ids}')

    # Process each current file
    files_processed = 0
    for file_info in current_files:
        file_id = file_info['id']
        file_name = file_info.get('name', f'Drive file {file_id}')
        mime_type = file_info.get('mimeType', '')
        modified_time = file_info.get('modifiedTime', '')

        # Skip subfolders nested inside the source folder
        if mime_type == 'application/vnd.google-apps.folder':
            print(f'[gdrive_handler] Skipping subfolder file_id={file_id} name={file_name!r}')
            continue

        try:
            material_id, needs_ingest = _upsert_material(
                user_id, course_id, file_id, file_name, modified_time
            )

            if not needs_ingest and not force_full_sync:
                print(f'[gdrive_handler] Skipping unchanged file={file_id} name={file_name!r}')
                continue

            print(f'[gdrive_handler] Ingesting file={file_id} name={file_name!r} mime={mime_type}')

            try:
                pdf_bytes = _get_drive_file_as_pdf(file_id, mime_type, token)
            except ValueError as exc:
                # File exceeds 50 MB or unsupported type
                print(f'[gdrive_handler] Skipping file={file_id}: {exc}')
                continue

            if not needs_ingest:
                # Changed file: clear stale embeddings and old S3 PDF before re-ingest
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
            (source_point['id'],)
        )
    print(
        f'[gdrive_handler] Sync complete source_point_id={source_point.get("id")} '
        f'files_in_folder={len(current_files)} files_ingested={files_processed}'
    )
