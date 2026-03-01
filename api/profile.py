# Vercel Python Serverless Function — User Profile
# PUT    /api/profile  → update username
# POST   /api/profile  → update address
# DELETE /api/profile  → delete account

import json
import traceback
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

    # ------------------------------------------------------------------ PUT --
    # Update username
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
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
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

    # ----------------------------------------------------------------- POST --
    # Update address
    def do_POST(self):
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
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid JSON"})
            return

        address = data.get('address')
        if not address:
            send_json(self, 400, {"error": "Missing address", "message": "address is required"})
            return

        address = sanitize_string(address, max_length=500)
        if not address:
            send_json(self, 400, {"error": "Invalid address"})
            return

        user = User.update_address(google_id, address)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        send_json(self, 200, {
            "success": True,
            "message": "Address updated successfully",
            "user": {
                "id": user.get("google_id"),
                "email": user.get("email"),
                "name": user.get("name"),
                "address": user.get("address"),
                "updated_at": user.get("updated_at").isoformat() if user.get("updated_at") else None,
            },
        })

    # --------------------------------------------------------------- DELETE --
    # Delete account
    def do_DELETE(self):
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
            deleted = User.delete_user(google_id)
            if not deleted:
                send_json(self, 404, {"error": "User not found"})
                return
            send_json(self, 200, {"success": True, "message": "Account deleted successfully"})
        except Exception:
            traceback.print_exc()
            send_json(self, 500, {"error": "Internal server error"})
