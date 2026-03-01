# Vercel Python Serverless Function — Materials
# GET    /api/material?course_id=<id>               → list course materials
# POST   /api/material  action="request_upload"     → get presigned S3 upload URL
# POST   /api/material  action="confirm_upload"     → confirm S3 upload, create record
# POST   /api/material  action="update_visibility"  → change public/private
# DELETE /api/material                              → delete material

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .models import User, Material
    from .courses import Course
    from .s3_utils import (
        validate_file_type, get_file_extension,
        generate_upload_presigned_url, generate_download_presigned_url,
        verify_file_exists, delete_file,
    )
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from models import User, Material
    from courses import Course
    from s3_utils import (
        validate_file_type, get_file_extension,
        generate_upload_presigned_url, generate_download_presigned_url,
        verify_file_exists, delete_file,
    )


def _s3_key_from_url(file_url: str) -> str:
    return urlparse(file_url).path.lstrip('/')


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

        if action == 'request_upload':
            self._request_upload(google_id, data)
        elif action == 'confirm_upload':
            self._confirm_upload(google_id, data)
        elif action == 'update_visibility':
            self._update_visibility(google_id, data)
        else:
            send_json(self, 400, {"error": f"Unknown action '{action}'"})

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

        try:
            delete_file(_s3_key_from_url(material['file_url']))
        except Exception as e:
            send_json(self, 500, {"error": "Failed to delete file from S3", "detail": str(e)})
            return

        Course.remove_material(course_id, material_id)
        Material.delete(material_id)
        send_json(self, 200, {"success": True})

    # --------------------------------------------------------- POST helpers --

    def _request_upload(self, google_id, data):
        course_id = data.get('course_id')
        filename = sanitize_string(data.get('filename', ''), max_length=255)
        file_type = sanitize_string(data.get('file_type', ''), max_length=100)
        visibility = data.get('visibility', 'private')

        if not course_id or not filename or not file_type:
            send_json(self, 400, {"error": "course_id, filename, and file_type are required"})
            return

        if visibility not in ('public', 'private'):
            send_json(self, 400, {"error": "visibility must be 'public' or 'private'"})
            return

        if not validate_file_type(file_type):
            send_json(self, 400, {"error": "Unsupported file type"})
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

        try:
            presigned = generate_upload_presigned_url(s3_key, file_type)
        except Exception as e:
            send_json(self, 500, {"error": "Failed to generate upload URL", "detail": str(e)})
            return

        send_json(self, 200, {
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

        if not s3_key or not course_id or not filename or not file_type:
            send_json(self, 400, {"error": "s3_key, course_id, filename, and file_type are required"})
            return

        if visibility not in ('public', 'private'):
            send_json(self, 400, {"error": "visibility must be 'public' or 'private'"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
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

        material = Material.create(
            course_id=course_id,
            name=filename,
            file_url=file_url,
            uploaded_by=user['id'],
            file_type=file_type,
            visibility=visibility,
            source_type='upload',
        )
        Course.add_material(course_id, material['id'])
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
