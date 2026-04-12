# Vercel Python Serverless Function — Materials
# GET    /api/material?course_id=<id>               → list course materials
# POST   /api/material  action="request_upload"     → get presigned S3 upload URL
# POST   /api/material  action="confirm_upload"     → confirm S3 upload, create record
# POST   /api/material  action="update_visibility"  → change public/private
# POST   /api/material  action="bulk_upsert_sync"   → upsert sync state for integration source point files
# DELETE /api/material                              → delete material (server-side tombstone for synced materials)

import json
import math
import os
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import boto3

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .models import User, Material
    from .courses import Course
    from .db import get_db
    from .document_types import VALID_DOC_TYPES, DEFAULT_DOC_TYPE
    from .s3_utils import (
        PART_SIZE,
        validate_file_type, get_file_extension,
        generate_upload_presigned_url, generate_download_presigned_url,
        verify_file_exists, delete_file,
        create_multipart_upload, generate_multipart_part_url,
        complete_multipart_upload, abort_multipart_upload,
    )
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from models import User, Material
    from courses import Course
    from db import get_db
    from document_types import VALID_DOC_TYPES, DEFAULT_DOC_TYPE
    from s3_utils import (
        PART_SIZE,
        validate_file_type, get_file_extension,
        generate_upload_presigned_url, generate_download_presigned_url,
        verify_file_exists, delete_file,
        create_multipart_upload, generate_multipart_part_url,
        complete_multipart_upload, abort_multipart_upload,
    )


_INTEGRATION_POLLER_ARN = os.environ.get("INTEGRATION_POLLER_LAMBDA_ARN", "")
_AWS_REGION = (
    os.environ.get("COURSEMATE_AWS_REGION")
    or os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or "us-east-1"
)


def _trigger_poller(source_point_id, user_id, course_id, external_ids: list | None = None):
    """Fire-and-forget Lambda invoke for the integration poller."""
    if not _INTEGRATION_POLLER_ARN:
        return
    try:
        import boto3
        lmbd = boto3.client("lambda", region_name=_AWS_REGION)
        payload = {
            "source_point_id": int(source_point_id),
            "user_id": user_id,
            "course_id": int(course_id),
        }
        if external_ids is not None:
            payload["external_ids"] = external_ids
        lmbd.invoke(
            FunctionName=_INTEGRATION_POLLER_ARN,
            InvocationType="Event",
            Payload=json.dumps(payload).encode(),
        )
    except Exception as exc:
        print(f"[material] poller invoke failed: {exc}")


def _s3_key_from_url(file_url: str) -> str:
    return urlparse(file_url).path.lstrip('/')


# Maps generated-artifact URL prefixes to their generation table names.
_GENERATION_URL_TABLES = {
    'report://generation/':     'report_generations',
    'quiz://generation/':       'quiz_generations',
    'flashcards://generation/': 'flashcard_generations',
}


def _delete_generation_for_material(file_url: str) -> bool:
    """
    If file_url is a generated-artifact URL (e.g. 'report://generation/42'),
    delete the corresponding row from the generation table and return True.
    Returns False for regular S3 uploads.
    """
    for prefix, table in _GENERATION_URL_TABLES.items():
        if file_url.startswith(prefix):
            gen_id_str = file_url[len(prefix):]
            if not gen_id_str.isdigit():
                return True  # Malformed URL — skip S3 delete, nothing to clean up
            gen_id = int(gen_id_str)
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", (gen_id,))
                cursor.close()
            return True
    return False


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ------------------------------------------------------------------ GET --
    def do_GET(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        action = params.get('action', [None])[0]

        if action == 'selections':
            self._get_selections(google_id, params)
            return

        course_id_raw = params.get('course_id', [None])[0]

        if not course_id_raw or not course_id_raw.isdigit():
            send_json(self, 400, {"error": "course_id query parameter is required"})
            return

        course_id = int(course_id_raw)

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        materials = Material.get_by_course(course_id, user['id'])
        for m in materials:
            try:
                m['download_url'] = generate_download_presigned_url(_s3_key_from_url(m['file_url']))
            except Exception:
                m['download_url'] = None

        send_json(self, 200, {"materials": materials})

    # ----------------------------------------------------------------- POST --
    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
            return

        action = data.get('action', 'request_upload')

        try:
            if action == 'request_upload':
                self._request_upload(google_id, data)
            elif action == 'confirm_upload':
                self._confirm_upload(google_id, data)
            elif action == 'update_visibility':
                self._update_visibility(google_id, data)
            elif action == 'set_selection':
                self._set_selection(google_id, data)
            elif action == 'bulk_upsert_sync':
                self._bulk_upsert_sync(google_id, data)
            else:
                send_json(self, 400, {"error": f"Unknown action '{action}'"})
        except Exception as exc:
            print(f"[material] action={action} failed: {exc}")
            send_json(self, 500, {"error": "material action failed", "action": action, "detail": str(exc)})

    # ---------------------------------------------------- bulk_upsert_sync --

    def _bulk_upsert_sync(self, google_id: str, data: dict):
        """Bulk upsert sync state for a list of integration source point files.

        Body: {
            course_id: int,
            source_point_id: int,
            source_type: "gdrive" | "notion",
            files: [{external_id: str, name: str, sync: bool}]
        }

        Performs INSERT ... ON CONFLICT (external_id, course_id) DO UPDATE SET sync = excluded.sync
        so existing rows get their sync flag updated and new rows are inserted with sync set.
        After writing, triggers the integration poller Lambda for the source point.
        """
        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        course_id = data.get('course_id')
        source_point_id = data.get('source_point_id')
        source_type = data.get('source_type')
        files = data.get('files', [])

        if not course_id or not source_point_id or not source_type:
            send_json(self, 400, {"error": "course_id, source_point_id, and source_type are required"})
            return
        if source_type not in ('gdrive', 'notion'):
            send_json(self, 400, {"error": "source_type must be 'gdrive' or 'notion'"})
            return
        if not isinstance(files, list):
            send_json(self, 400, {"error": "files must be an array"})
            return

        if not Course.verify_access(int(course_id), user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        if not files:
            send_json(self, 200, {"upserted": 0})
            return

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                # Verify source point belongs to this user and course
                cursor.execute(
                    "SELECT id FROM integration_source_points WHERE id = %s AND user_id = %s AND course_id = %s",
                    (source_point_id, user['id'], course_id),
                )
                if not cursor.fetchone():
                    cursor.close()
                    send_json(self, 403, {"error": "Source point not found or access denied"})
                    return

                upserted = 0
                for f in files:
                    external_id = f.get('external_id')
                    name = f.get('name') or ''
                    sync_val = bool(f.get('sync', True))
                    raw_doc_type = f.get('doc_type', DEFAULT_DOC_TYPE)
                    doc_type = raw_doc_type if raw_doc_type in VALID_DOC_TYPES else DEFAULT_DOC_TYPE
                    if not external_id:
                        continue
                    # Keep file_url non-null until poller ingests and replaces with final HTTPS URL.
                    placeholder_file_url = f"{source_type}/{external_id}.pdf"
                    # Use a CTE so we can detect doc_type drift in a single round-trip.
                    # `pre` reads the old doc_type before the upsert (same snapshot), then
                    # `reset_embed` resets the embed job to pending only when doc_type changed.
                    # embed_status is NOT a column on materials — it lives in material_embed_jobs.
                    cursor.execute("""
                        WITH pre AS (
                            SELECT id, doc_type AS old_doc_type
                            FROM materials
                            WHERE external_id = %s AND course_id = %s
                        ),
                        upserted AS (
                            INSERT INTO materials
                                (course_id, name, file_url, uploaded_by, file_type, source_type,
                                 external_id, integration_source_point_id, sync, doc_type)
                            VALUES (%s, %s, %s, %s, 'application/pdf', %s, %s, %s, %s, %s)
                            ON CONFLICT (external_id, course_id)
                            DO UPDATE SET file_type = 'application/pdf',
                                          sync = EXCLUDED.sync,
                                          doc_type = EXCLUDED.doc_type,
                                          updated_at = CURRENT_TIMESTAMP
                            RETURNING id
                        ),
                        reset_embed AS (
                            UPDATE material_embed_jobs
                            SET status = 'pending',
                                started_at = NULL,
                                completed_at = NULL,
                                error_message = NULL,
                                chunks_created = NULL
                            FROM upserted u
                            JOIN pre p ON p.id = u.id
                            WHERE material_embed_jobs.material_id = u.id
                              AND p.old_doc_type IS DISTINCT FROM %s
                        )
                        SELECT id FROM upserted
                    """, (
                        external_id, course_id,  # pre
                        course_id, name, placeholder_file_url, user['id'], source_type,
                        external_id, source_point_id, sync_val, doc_type,  # upserted
                        doc_type,  # reset_embed: new doc_type to compare against old
                    ))
                    upserted += 1
                cursor.close()
        except Exception as exc:
            send_json(self, 500, {"error": "bulk_upsert_sync failed", "detail": str(exc)})
            return

        # Trigger the integration poller Lambda so sync=true files get ingested
        external_ids = [f['external_id'] for f in files if f.get('sync') and f.get('external_id')]
        _trigger_poller(source_point_id, user['id'], course_id, external_ids=external_ids)

        send_json(self, 200, {"upserted": upserted})

    # --------------------------------------------------------------- DELETE --
    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
            return

        material_id = data.get('material_id')
        course_id = data.get('course_id')
        if not material_id or not course_id:
            send_json(self, 400, {"error": "material_id and course_id are required"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        material = Material.get_by_id(material_id)
        if not material:
            send_json(self, 404, {"error": "Material not found"})
            return

        course = Course.get_by_id(course_id)
        if not course:
            send_json(self, 404, {"error": "Course not found"})
            return

        is_uploader = material['uploaded_by'] == user['id']
        is_course_creator = course['primary_creator'] == user['id']
        if not (is_uploader or is_course_creator):
            send_json(self, 403, {"error": "You do not have permission to delete this material"})
            return

        file_url = material['file_url'] or ''
        is_generated = _delete_generation_for_material(file_url)

        if not is_generated:
            source_type = material.get('source_type', '')
            if source_type == 'notion':
                # Best-effort S3 delete for Notion materials — the file may not yet
                # exist (placeholder URL) or may have already been cleaned up.
                try:
                    delete_file(_s3_key_from_url(file_url))
                except Exception as e:
                    print(f"[material] S3 delete skipped for Notion material {material_id}: {e}")
            else:
                try:
                    delete_file(_s3_key_from_url(file_url))
                except Exception as e:
                    send_json(self, 500, {"error": "Failed to delete file from S3", "detail": str(e)})
                    return

        is_synced_material = material.get('integration_source_point_id') is not None
        if is_synced_material:
            # Retain synced rows as tombstones so the poller won't re-ingest.
            # The active materials query filters sync=false rows from UI.
            Material.tombstone(material_id)
            send_json(self, 200, {"success": True, "tombstoned": True})
            return

        Course.remove_material(course_id, material_id)
        Material.delete(material_id)

        send_json(self, 200, {"success": True, "tombstoned": False})

    # --------------------------------------------------------- GET helpers ---

    def _get_selections(self, google_id, params):
        course_id_raw = params.get('course_id', [None])[0]
        context = params.get('context', [None])[0]

        if not course_id_raw or not course_id_raw.isdigit():
            send_json(self, 400, {"error": "course_id query parameter is required"})
            return
        if not context:
            send_json(self, 400, {"error": "context query parameter is required"})
            return

        course_id = int(course_id_raw)

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            # Fetch all accessible materials (own + public collaborator) with selection state.
            # Default: own materials → selected=true, collaborator materials → selected=false.
            cursor.execute("""
                SELECT
                    m.id,
                    m.name,
                    m.file_url,
                    m.file_type,
                    m.visibility,
                    m.uploaded_by,
                    m.source_type,
                    m.external_id,
                    m.outsourced_url,
                    COALESCE(ms.selected, (m.uploaded_by = %s)) AS selected,
                    ms.provider AS selection_provider,
                    CASE WHEN m.uploaded_by != %s THEN u.name  ELSE NULL END AS collaborator_name,
                    CASE WHEN m.uploaded_by != %s THEN u.email ELSE NULL END AS collaborator_email
                FROM materials m
                LEFT JOIN material_selections ms
                    ON ms.material_id = m.id
                    AND ms.user_id = %s
                    AND ms.context = %s
                LEFT JOIN users u ON u.id = m.uploaded_by
                WHERE m.course_id = %s
                  AND (m.visibility = 'public' OR m.uploaded_by = %s)
                ORDER BY (m.uploaded_by = %s) DESC, m.id
            """, (
                user['id'], user['id'], user['id'],  # CASE expressions
                user['id'], context,                  # material_selections join
                course_id,                            # WHERE course_id
                user['id'], user['id'],               # WHERE visibility / ORDER
            ))
            rows = cursor.fetchall()
            cursor.close()

        materials = []
        for row in rows:
            m = dict(row)
            collaborator_name = m.pop('collaborator_name', None)
            collaborator_email = m.pop('collaborator_email', None)
            m.pop('selection_provider', None)
            try:
                m['download_url'] = generate_download_presigned_url(_s3_key_from_url(m['file_url']))
            except Exception:
                m['download_url'] = None
            if collaborator_name or collaborator_email:
                m['collaborator'] = {'name': collaborator_name, 'email': collaborator_email}
            else:
                m['collaborator'] = None
            materials.append(m)

        send_json(self, 200, {"materials": materials})

    # --------------------------------------------------------- POST helpers --

    def _set_selection(self, google_id, data):
        material_id = data.get('material_id')
        course_id = data.get('course_id')
        context = data.get('context')
        selected = data.get('selected')
        provider = data.get('provider')  # optional

        if not material_id or not course_id or not context or selected is None:
            send_json(self, 400, {"error": "material_id, course_id, context, and selected are required"})
            return

        if not isinstance(selected, bool):
            send_json(self, 400, {"error": "selected must be a boolean"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO material_selections (user_id, course_id, material_id, context, provider, selected, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, course_id, material_id, context)
                DO UPDATE SET selected = EXCLUDED.selected,
                              provider = EXCLUDED.provider,
                              updated_at = CURRENT_TIMESTAMP
                RETURNING *
            """, (user['id'], course_id, material_id, context, provider, selected))
            row = cursor.fetchone()
            cursor.close()

        send_json(self, 200, {"selection": dict(row)})

    def _request_upload(self, google_id, data):
        course_id = data.get('course_id')
        filename = sanitize_string(data.get('filename', ''), max_length=255)
        file_type = sanitize_string(data.get('file_type', ''), max_length=100)
        visibility = data.get('visibility', 'private')
        file_size = data.get('file_size')  # bytes, optional — required for multipart routing

        if not course_id or not filename or not file_type:
            send_json(self, 400, {"error": "course_id, filename, and file_type are required"})
            return

        if visibility not in ('public', 'private'):
            send_json(self, 400, {"error": "visibility must be 'public' or 'private'"})
            return

        if not validate_file_type(file_type):
            send_json(self, 400, {"error": "Unsupported file type"})
            return

        if file_size is not None:
            try:
                file_size = int(file_size)
                if file_size < 0:
                    raise ValueError
            except (ValueError, TypeError):
                send_json(self, 400, {"error": "file_size must be a non-negative integer (bytes)"})
                return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        ext = get_file_extension(filename)
        s3_key = f"materials/{uuid.uuid4()}.{ext}" if ext else f"materials/{uuid.uuid4()}"

        # Large file: use S3 multipart upload so each part stays within PART_SIZE.
        if file_size is not None and file_size > PART_SIZE:
            num_parts = math.ceil(file_size / PART_SIZE)
            try:
                upload_id = create_multipart_upload(s3_key, file_type)
                parts = [
                    {
                        "part_number": i,
                        "upload_url": generate_multipart_part_url(s3_key, upload_id, i),
                    }
                    for i in range(1, num_parts + 1)
                ]
            except Exception as e:
                send_json(self, 500, {"error": "Failed to initiate multipart upload", "detail": str(e)})
                return

            send_json(self, 200, {
                "multipart": True,
                "upload_id": upload_id,
                "s3_key": s3_key,
                "parts": parts,
                "part_size": PART_SIZE,
            })
            return

        # Small file (or no file_size provided): single presigned POST.
        try:
            presigned = generate_upload_presigned_url(s3_key, file_type)
        except Exception as e:
            send_json(self, 500, {"error": "Failed to generate upload URL", "detail": str(e)})
            return

        send_json(self, 200, {
            "multipart": False,
            "upload_url": presigned['url'],
            "fields": presigned['fields'],
            "s3_key": s3_key,
        })

    def _confirm_upload(self, google_id, data):
        s3_key = sanitize_string(data.get('s3_key', ''), max_length=500)
        course_id = data.get('course_id')
        filename = sanitize_string(data.get('filename', ''), max_length=255)
        file_type = sanitize_string(data.get('file_type', ''), max_length=100)
        visibility = data.get('visibility', 'private')
        # Multipart-only fields
        upload_id = data.get('upload_id')
        parts = data.get('parts')  # [{'part_number': n, 'etag': '...'}, ...]

        if not s3_key or not course_id or not filename or not file_type:
            send_json(self, 400, {"error": "s3_key, course_id, filename, and file_type are required"})
            return

        if visibility not in ('public', 'private'):
            send_json(self, 400, {"error": "visibility must be 'public' or 'private'"})
            return

        if upload_id and not parts:
            send_json(self, 400, {"error": "parts is required when upload_id is provided"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        # Complete multipart upload before verifying existence.
        if upload_id:
            try:
                s3_parts = [
                    {'PartNumber': p['part_number'], 'ETag': p['etag']}
                    for p in parts
                ]
                complete_multipart_upload(s3_key, upload_id, s3_parts)
            except Exception as e:
                try:
                    abort_multipart_upload(s3_key, upload_id)
                except Exception:
                    pass
                send_json(self, 500, {"error": "Failed to complete multipart upload", "detail": str(e)})
                return

        try:
            if not verify_file_exists(s3_key):
                send_json(self, 400, {"error": "File not found in S3; upload may have failed"})
                return
        except Exception as e:
            send_json(self, 500, {"error": "Failed to verify file in S3", "detail": str(e)})
            return

        bucket = os.environ.get('AWS_S3_BUCKET_NAME')
        region = os.environ.get('AWS_REGION')
        file_url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"

        doc_type = data.get('source_type', DEFAULT_DOC_TYPE)
        if doc_type not in VALID_DOC_TYPES:
            doc_type = DEFAULT_DOC_TYPE

        material = Material.create(
            course_id=course_id,
            name=filename,
            file_url=file_url,
            uploaded_by=user['id'],
            file_type=file_type,
            visibility=visibility,
            source_type='upload',
            doc_type=doc_type,
        )
        Course.add_material(course_id, material['id'])

        # Create a pending embed job and immediately start the Step Functions execution
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO material_embed_jobs (material_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (material['id'],)
            )
            cursor.close()

        if file_type == 'application/pdf':
            state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
            if state_machine_arn:
                try:
                    sfn = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
                    sfn.start_execution(
                        stateMachineArn=state_machine_arn,
                        input=json.dumps({'s3_key': s3_key, 'cursor': 0}),
                    )
                except Exception as e:
                    print(f"[material] Failed to start SFN execution for {s3_key}: {e}")

        send_json(self, 201, {"material": material})

    def _update_visibility(self, google_id, data):
        material_id = data.get('material_id')
        visibility = data.get('visibility')

        if not material_id or visibility not in ('public', 'private'):
            send_json(self, 400, {"error": "material_id and visibility ('public' or 'private') are required"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        material = Material.get_by_id(material_id)
        if not material:
            send_json(self, 404, {"error": "Material not found"})
            return

        if material['uploaded_by'] != user['id']:
            send_json(self, 403, {"error": "Only the uploader can change visibility"})
            return

        updated = Material.update_visibility(material_id, visibility)
        send_json(self, 200, {"material": updated})
