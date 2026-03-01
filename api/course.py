# Vercel Python Serverless Function — Courses
# GET  /api/course  → list courses for current user
# POST /api/course  → create course
# DELETE /api/course → delete course

import json
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

    # ------------------------------------------------------------------ GET --
    def do_GET(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        courses = Course.get_by_creator(user['id'], include_co_created=True)
        for course in courses:
            course['is_owner'] = course.get('primary_creator') == user['id']
        send_json(self, 200, {"courses": courses})

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

        course_id = data.get('course_id')
        if not isinstance(course_id, int):
            send_json(self, 400, {"error": "course_id is required"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        course = Course.get_by_id(course_id)
        if not course:
            send_json(self, 404, {"error": "Course not found"})
            return

        if course['primary_creator'] != user['id']:
            send_json(self, 403, {"error": "Only the course owner can delete it"})
            return

        deleted = Course.delete(course_id)
        if deleted:
            send_json(self, 200, {"success": True})
        else:
            send_json(self, 500, {"error": "Failed to delete course"})
