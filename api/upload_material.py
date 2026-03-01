# Vercel Python Serverless Function — Request Presigned Upload URL
# Endpoint: POST /api/upload_material
# Step 1 of 2-step upload: returns a presigned POST URL for direct S3 upload.

import json
import uuid
from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .models import User
    from .courses import Course
    from .s3_utils import validate_file_type, get_file_extension, generate_upload_presigned_url
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from models import User
    from courses import Course
    from s3_utils import validate_file_type, get_file_extension, generate_upload_presigned_url


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
