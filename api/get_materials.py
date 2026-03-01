# Vercel Python Serverless Function — Get Course Materials
# Endpoint: GET /api/get_materials?course_id=<id>

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .models import User, Material
    from .courses import Course
    from .s3_utils import generate_download_presigned_url
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from models import User, Material
    from courses import Course
    from s3_utils import generate_download_presigned_url


def _extract_s3_key(file_url: str) -> str:
    """Extract the S3 object key from a full HTTPS URL."""
    parsed = urlparse(file_url)
    # path starts with '/', strip leading slash
    return parsed.path.lstrip('/')


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

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
                s3_key = _extract_s3_key(m['file_url'])
                m['download_url'] = generate_download_presigned_url(s3_key)
            except Exception:
                m['download_url'] = None

        send_json(self, 200, {"materials": materials})
