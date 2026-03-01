# Vercel Python Serverless Function — Session Validation
# Endpoint: GET /api/validate_session

from http.server import BaseHTTPRequestHandler

try:
    from .models import User
    from .middleware import send_json, handle_options, authenticate_request, generate_csrf_token
except ImportError:
    from models import User
    from middleware import send_json, handle_options, authenticate_request, generate_csrf_token


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_GET(self):
        google_id, session_token = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized", "message": "Invalid or expired session"})
            return

        try:
            user = User.get_by_google_id(google_id)
            if not user:
                send_json(self, 401, {"error": "Unauthorized", "message": "User not found"})
                return

            csrf_token = generate_csrf_token(session_token)

            user_response = {
                "id": user.get("google_id"),
                "db_id": user.get("id"),
                "email": user.get("email"),
                "email_verified": user.get("email_verified"),
                "name": user.get("name"),
                "given_name": user.get("given_name"),
                "family_name": user.get("family_name"),
                "picture": user.get("picture"),
                "locale": user.get("locale"),
                "address": user.get("address"),
                "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
                "updated_at": user.get("updated_at").isoformat() if user.get("updated_at") else None,
            }

            send_json(self, 200, {
                "success": True,
                "user": user_response,
                "session_token": session_token,
                "csrf_token": csrf_token,
            })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})
