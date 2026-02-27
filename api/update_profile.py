# Vercel Python Serverless Function — Update User Profile
# Endpoint: PUT /api/update_profile

import json
from http.server import BaseHTTPRequestHandler

try:
    from .models import User
    from .middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token, sanitize_string,
    )
except ImportError:
    from models import User
    from middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token, sanitize_string,
    )


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_PUT(self):
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests"})
            return

        google_id, session_token = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized", "message": "Valid session required"})
            return

        if not verify_csrf_token(self, session_token):
            send_json(self, 403, {"error": "Forbidden", "message": "Invalid CSRF token"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                send_json(self, 400, {"error": "Invalid JSON"})
                return

            username = data.get('username')
            if not username:
                send_json(self, 400, {"error": "Missing username", "message": "username is required"})
                return

            username = sanitize_string(username, max_length=255)
            if not username:
                send_json(self, 400, {"error": "Invalid username"})
                return

            user = User.update_username(google_id, username)

            if not user:
                send_json(self, 404, {"error": "User not found"})
                return

            send_json(self, 200, {
                "success": True,
                "message": "Username updated successfully",
                "user": {
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "picture": user.get("picture"),
                    "updated_at": user.get("updated_at").isoformat() if user.get("updated_at") else None,
                },
            })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})
