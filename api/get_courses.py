# Vercel Python Serverless Function — Get Courses
# Endpoint: GET /api/get_courses

from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .courses import Course
    from .models import User
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from courses import Course
    from models import User


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

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
