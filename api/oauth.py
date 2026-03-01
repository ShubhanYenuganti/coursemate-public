# Vercel Python Serverless Function — Google OAuth Login
# Endpoint: POST /api/oauth

import json
import os
from http.server import BaseHTTPRequestHandler
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime, timedelta

try:
    from .models import User, Session
    from .middleware import send_json, handle_options, check_rate_limit, generate_csrf_token
except ImportError:
    from models import User, Session
    from middleware import send_json, handle_options, check_rate_limit, generate_csrf_token


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        # Rate limiting
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests", "message": "Please try again later"})
            return

        try:
            # Verify server configuration
            GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
            if not GOOGLE_CLIENT_ID:
                send_json(self, 500, {"error": "Server configuration error"})
                return

            # Read and parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                send_json(self, 400, {"error": "Invalid JSON"})
                return

            token = data.get('token') or data.get('credential')
            if not token:
                send_json(self, 400, {"error": "Missing token", "message": "Google OAuth token is required"})
                return

            # Verify the Google OAuth token
            try:
                idinfo = id_token.verify_oauth2_token(
                    token,
                    requests.Request(),
                    GOOGLE_CLIENT_ID
                )
            except ValueError:
                send_json(self, 401, {"error": "Invalid token", "message": "Token verification failed"})
                return

            # Extract user information from verified token
            google_id = idinfo.get("sub")
            email = idinfo.get("email")
            email_verified = idinfo.get("email_verified", False)
            name = idinfo.get("name")
            given_name = idinfo.get("given_name")
            family_name = idinfo.get("family_name")
            picture = idinfo.get("picture")
            locale = idinfo.get("locale")

            token_expires_at = datetime.utcnow() + timedelta(hours=1)

            # Save or update user in database, create session
            try:
                user = User.create_or_update(
                    google_id=google_id,
                    email=email,
                    email_verified=email_verified,
                    name=name,
                    given_name=given_name,
                    family_name=family_name,
                    picture=picture,
                    locale=locale,
                    google_id_token=token,
                    token_expires_at=token_expires_at
                )

                # Create a server-side session
                session = Session.create(google_id=google_id)
                csrf_token = generate_csrf_token(session['session_token'])

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
                    "message": "User profile created/updated successfully",
                    "user": user_response,
                    "session_token": session['session_token'],
                    "csrf_token": csrf_token,
                    "expires_at": session['expires_at'].isoformat() if hasattr(session['expires_at'], 'isoformat') else str(session['expires_at']),
                    "database_saved": True
                })

            except Exception:
                # Graceful degradation if database fails — user still authenticated via Google
                user_profile = {
                    "id": google_id,
                    "email": email,
                    "email_verified": email_verified,
                    "name": name,
                    "given_name": given_name,
                    "family_name": family_name,
                    "picture": picture,
                    "locale": locale,
                }

                send_json(self, 200, {
                    "success": True,
                    "message": "User profile verified (database unavailable)",
                    "user": user_profile,
                    "database_saved": False
                })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})

    def do_GET(self):
        send_json(self, 200, {
            "endpoint": "/api/oauth",
            "description": "Google OAuth Login",
            "methods": ["POST"],
            "required_env": ["GOOGLE_CLIENT_ID", "DATABASE_URL", "SESSION_SECRET"],
            "request_body": {
                "credential": "Google OAuth ID token (required)"
            }
        })
