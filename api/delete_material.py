# Vercel Python Serverless Function — Delete Material
# Endpoint: POST /api/delete_material

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .models import User, Material
    from .courses import Course
    from .s3_utils import delete_file
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from models import User, Material
    from courses import Course
    from s3_utils import delete_file


def _extract_s3_key(file_url: str) -> str:
    parsed = urlparse(file_url)
    return parsed.path.lstrip('/')


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
            s3_key = _extract_s3_key(material['file_url'])
            delete_file(s3_key)
        except Exception as e:
            send_json(self, 500, {"error": "Failed to delete file from S3", "detail": str(e)})
            return

        Course.remove_material(course_id, material_id)
        Material.delete(material_id)

        send_json(self, 200, {"success": True})
