# Vercel Python Serverless Function — Confirm S3 Upload and Create Material Record
# Endpoint: POST /api/confirm_upload
# Step 2 of 2-step upload: verifies the file landed in S3 and writes the DB record.

import json
import os
from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .models import User, Material
    from .courses import Course
    from .s3_utils import verify_file_exists
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from models import User, Material
    from courses import Course
    from s3_utils import verify_file_exists


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

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
