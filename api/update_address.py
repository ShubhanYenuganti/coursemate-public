# Vercel Python Serverless Function — Update User Address (Authenticated)
# Endpoint: POST /api/update_address

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

    def do_POST(self):
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests"})
            return

        # Authenticate — google_id comes from the session, NOT the request body
        google_id, session_token = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized", "message": "Valid session required"})
            return

        # Verify CSRF token
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

            address = data.get('address')
            if not address:
                send_json(self, 400, {"error": "Missing address", "message": "address is required"})
                return

            # Sanitize input
            address = sanitize_string(address, max_length=500)
            if not address:
                send_json(self, 400, {"error": "Invalid address"})
                return

            # Update — user can only update their own address
            user = User.update_address(google_id, address)

            if not user:
                send_json(self, 404, {"error": "User not found"})
                return

            user_response = {
                "id": user.get("google_id"),
                "email": user.get("email"),
                "name": user.get("name"),
                "address": user.get("address"),
                "updated_at": user.get("updated_at").isoformat() if user.get("updated_at") else None,
            }

            send_json(self, 200, {
                "success": True,
                "message": "Address updated successfully",
                "user": user_response
            })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})
