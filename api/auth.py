# Vercel Python Serverless Function — Authentication
# GET    /api/auth                        → validate existing session
# POST   /api/auth  { credential }        → Google OAuth login
# DELETE /api/auth                        → logout (revoke session)

import json
import os
from http.server import BaseHTTPRequestHandler
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime, timedelta

try:
    from .models import User, Session
    from .middleware import send_json, handle_options, check_rate_limit, authenticate_request, generate_csrf_token
except ImportError:
    from models import User, Session
    from middleware import send_json, handle_options, check_rate_limit, authenticate_request, generate_csrf_token


def _build_user_response(user):
    return {
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


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ------------------------------------------------------------------ GET --
    # Validate existing session and return fresh CSRF token + user data.
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
            send_json(self, 200, {
                "success": True,
                "user": _build_user_response(user),
                "session_token": session_token,
                "csrf_token": csrf_token,
            })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})

    # ----------------------------------------------------------------- POST --
    # Google OAuth login — verify ID token, upsert user, create session.
    def do_POST(self):
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests", "message": "Please try again later"})
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

            token = data.get('token') or data.get('credential')
            if not token:
                send_json(self, 400, {"error": "Missing token", "message": "Google OAuth token is required"})
                return

            try:
                idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
            except ValueError:
                send_json(self, 401, {"error": "Invalid token", "message": "Token verification failed"})
                return

            google_id      = idinfo.get("sub")
            email          = idinfo.get("email")
            email_verified = idinfo.get("email_verified", False)
            name           = idinfo.get("name")
            given_name     = idinfo.get("given_name")
            family_name    = idinfo.get("family_name")
            picture        = idinfo.get("picture")
            locale         = idinfo.get("locale")

            token_expires_at = datetime.utcnow() + timedelta(hours=1)

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
                    token_expires_at=token_expires_at,
                )

                session    = Session.create(google_id=google_id)
                csrf_token = generate_csrf_token(session['session_token'])

                send_json(self, 200, {
                    "success": True,
                    "message": "User profile created/updated successfully",
                    "user": _build_user_response(user),
                    "session_token": session['session_token'],
                    "csrf_token": csrf_token,
                    "expires_at": session['expires_at'].isoformat() if hasattr(session['expires_at'], 'isoformat') else str(session['expires_at']),
                    "database_saved": True,
                })

            except Exception:
                # Graceful degradation if database fails — user still authenticated via Google
                send_json(self, 200, {
                    "success": True,
                    "message": "User profile verified (database unavailable)",
                    "user": {
                        "id": google_id, "email": email, "email_verified": email_verified,
                        "name": name, "given_name": given_name, "family_name": family_name,
                        "picture": picture, "locale": locale,
                    },
                    "database_saved": False,
                })

        except Exception:
            send_json(self, 500, {"error": "Internal server error"})

    # --------------------------------------------------------------- DELETE --
    # Revoke session token (logout). Always returns success to prevent enumeration.
    def do_DELETE(self):
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

        send_json(self, 200, {"success": True, "message": "Logged out"})
