# Vercel Python Serverless Function — Re-link Google Account
# Endpoint: POST /api/relink_google

import json
import os
from http.server import BaseHTTPRequestHandler
from google.oauth2 import id_token
from google.auth.transport import requests

try:
    from .models import User, Session
    from .middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token, generate_csrf_token,
    )
except ImportError:
    from models import User, Session
    from middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token, generate_csrf_token,
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
            GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
            if not GOOGLE_CLIENT_ID:
                send_json(self, 500, {"error": "Server configuration error"})
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                send_json(self, 400, {"error": "Invalid JSON"})
                return

            credential = data.get('credential')
            if not credential:
                send_json(self, 400, {"error": "Missing credential", "message": "Google credential is required"})
                return

            # Verify the new Google credential
            try:
                idinfo = id_token.verify_oauth2_token(
                    credential,
                    requests.Request(),
                    GOOGLE_CLIENT_ID
                )
            except ValueError:
                send_json(self, 401, {"error": "Invalid token", "message": "Token verification failed"})
                return

            new_google_id = idinfo.get("sub")
            new_email = idinfo.get("email")
            new_name = idinfo.get("name")
            new_picture = idinfo.get("picture")

            # Guard: same account
            if new_google_id == google_id:
                send_json(self, 400, {"error": "Same account", "message": "Already linked to this Google account"})
                return

            # Guard: new google_id/email already registered to a different user
            existing_by_google = User.get_by_google_id(new_google_id)
            if existing_by_google:
                send_json(self, 409, {"error": "Account taken", "message": "This Google account is already registered to another user"})
                return

            existing_by_email = User.get_by_email(new_email)
            if existing_by_email and existing_by_email.get("google_id") != google_id:
                send_json(self, 409, {"error": "Email taken", "message": "This email is already registered to another user"})
                return

            # Fetch current user to get integer PK (google_id will change)
            current_user = User.get_by_google_id(google_id)
            if not current_user:
                send_json(self, 404, {"error": "User not found"})
                return

            user_id = current_user["id"]

            # Swap google_id — old sessions cascade-delete via FK ON DELETE CASCADE
            updated_user = User.relink_google(
                user_id=user_id,
                new_google_id=new_google_id,
                new_email=new_email,
                new_name=new_name,
                new_picture=new_picture,
                new_google_id_token=credential,
            )

            if not updated_user:
                send_json(self, 500, {"error": "Failed to update account"})
                return

            # Create new session under new google_id
            new_session = Session.create(google_id=new_google_id)
            csrf_token = generate_csrf_token(new_session["session_token"])

            send_json(self, 200, {
                "success": True,
                "message": "Google account updated successfully",
                "session_token": new_session["session_token"],
                "csrf_token": csrf_token,
                "user": {
                    "id": updated_user.get("google_id"),
                    "email": updated_user.get("email"),
                    "name": updated_user.get("name"),
                    "username": updated_user.get("username"),
                    "picture": updated_user.get("picture"),
                },
            })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})
