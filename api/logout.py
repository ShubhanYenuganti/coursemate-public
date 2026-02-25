# Vercel Python Serverless Function — Server-Side Logout
# Endpoint: POST /api/logout

from http.server import BaseHTTPRequestHandler

try:
    from .models import Session
    from .middleware import send_json, handle_options, check_rate_limit
except ImportError:
    from models import Session
    from middleware import send_json, handle_options, check_rate_limit


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests"})
            return

        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            send_json(self, 401, {"error": "Missing session token"})
            return

        session_token = auth_header[7:]

        try:
            Session.revoke(session_token)
        except Exception:
            pass  # Don't fail logout if DB is unreachable

        # Always return success to prevent session enumeration
        send_json(self, 200, {"success": True, "message": "Logged out"})
