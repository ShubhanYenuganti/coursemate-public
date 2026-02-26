# Vercel Python Serverless Function — Create Course
# Endpoint: POST /api/create_course

from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .courses import Course
    from .models import User
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from courses import Course
    from models import User


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        import json

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

        title = sanitize_string(data.get('title', ''), max_length=200)
        if not title:
            send_json(self, 400, {"error": "Title is required"})
            return

        description = sanitize_string(data.get('description', '') or '', max_length=2000) or None

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        course = Course.create(
            title=title,
            primary_creator=user['id'],
            description=description,
        )

        send_json(self, 201, {"course": course})
