# Vercel Python Serverless Function — Delete Account
# Endpoint: POST /api/delete_account

import traceback
from http.server import BaseHTTPRequestHandler

try:
    from .models import User
    from .middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token,
    )
except ImportError:
    from models import User
    from middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token,
    )


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

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
            deleted = User.delete_user(google_id)
            if not deleted:
                send_json(self, 404, {"error": "User not found"})
                return
            send_json(self, 200, {"success": True, "message": "Account deleted successfully"})
        except Exception:
            traceback.print_exc()
            send_json(self, 500, {"error": "Internal server error"})
