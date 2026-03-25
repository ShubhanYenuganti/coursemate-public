# Vercel Python Serverless Function — User Settings
# Dispatches on `resource` to serve both profile and API-key operations.
#
# GET    /api/user?resource=api_keys              → list saved provider flags (booleans)
# POST   /api/user  resource="api_keys"           → upsert { provider, api_key }
# DELETE /api/user?resource=api_keys              → remove key  { provider }
# PUT    /api/user  resource="profile"            → update username
# POST   /api/user  resource="profile"            → update address
# DELETE /api/user?resource=profile               → delete account

import json
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .models import User
    from .middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token, sanitize_string,
    )
    from .db import get_db
    from .crypto_utils import encrypt_api_key
except ImportError:
    from models import User
    from middleware import (
        send_json, handle_options, check_rate_limit,
        authenticate_request, verify_csrf_token, sanitize_string,
    )
    from db import get_db
    from crypto_utils import encrypt_api_key

VALID_PROVIDERS = ('gemini', 'openai', 'claude')


def _parse_resource_from_qs(handler_self):
    """Return the `resource` query-string value, or None."""
    parsed = urlparse(handler_self.path)
    qs = parse_qs(parsed.query)
    values = qs.get('resource', [])
    return values[0] if values else None


def _read_json_body(handler_self):
    """Read and parse the request body as JSON. Returns (data, error_sent)."""
    try:
        content_length = int(handler_self.headers.get('Content-Length', 0))
        raw = handler_self.rfile.read(content_length).decode('utf-8')
        return (json.loads(raw) if raw else {}), False
    except (ValueError, json.JSONDecodeError):
        send_json(handler_self, 400, {"error": "Invalid request body"})
        return None, True


def _get_user(handler_self, google_id):
    """Resolve google_id → user row. Sends 404 and returns None on miss."""
    user = User.get_by_google_id(google_id)
    if not user:
        send_json(handler_self, 404, {"error": "User not found"})
    return user


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ------------------------------------------------------------------ GET --
    # resource=api_keys → list provider flags (booleans only, never keys)
    def do_GET(self):
        resource = _parse_resource_from_qs(self)
        if resource != 'api_keys':
            send_json(self, 400, {"error": "resource query param must be 'api_keys'"})
            return

        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = _get_user(self, google_id)
        if not user:
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT provider FROM user_api_keys WHERE user_id = %s",
                (user['id'],)
            )
            rows = cursor.fetchall()
            cursor.close()

        saved = {row['provider'] for row in rows}
        send_json(self, 200, {
            "gemini": "gemini" in saved,
            "openai": "openai" in saved,
            "claude": "claude" in saved,
        })

    # ----------------------------------------------------------------- POST --
    # resource="api_keys" → upsert encrypted key for a provider
    # resource="profile"  → update address
    def do_POST(self):
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests"})
            return

        data, err = _read_json_body(self)
        if err:
            return

        resource = data.get('resource') or _parse_resource_from_qs(self)

        if resource == 'api_keys':
            self._post_api_key(data)
        elif resource == 'profile':
            self._post_profile_address(data)
        else:
            send_json(self, 400, {"error": "resource must be 'api_keys' or 'profile'"})

    def _post_api_key(self, data):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        provider = (data.get('provider') or '').lower().strip()
        api_key  = (data.get('api_key')  or '').strip()

        if provider not in VALID_PROVIDERS:
            send_json(self, 400, {"error": f"provider must be one of: {', '.join(VALID_PROVIDERS)}"})
            return
        if not api_key:
            send_json(self, 400, {"error": "api_key cannot be empty"})
            return

        user = _get_user(self, google_id)
        if not user:
            return

        try:
            encrypted = encrypt_api_key(api_key)
        except ValueError as e:
            send_json(self, 500, {"error": f"Encryption error: {e}"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_api_keys (user_id, provider, encrypted_key)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, provider) DO UPDATE
                    SET encrypted_key = EXCLUDED.encrypted_key,
                        updated_at    = CURRENT_TIMESTAMP
                RETURNING provider, updated_at
            """, (user['id'], provider, encrypted))
            row = cursor.fetchone()
            cursor.close()

        send_json(self, 200, {
            "success": True,
            "message": f"{provider.capitalize()} API key saved",
            "provider": row['provider'],
            "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
        })

    def _post_profile_address(self, data):
        google_id, session_token = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized", "message": "Valid session required"})
            return

        if not verify_csrf_token(self, session_token):
            send_json(self, 403, {"error": "Forbidden", "message": "Invalid CSRF token"})
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

    # ------------------------------------------------------------------ PUT --
    # resource="profile" → update username (only profile uses PUT)
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

        data, err = _read_json_body(self)
        if err:
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

    # --------------------------------------------------------------- DELETE --
    # resource=api_keys → remove saved key for a provider
    # resource=profile  → delete account
    def do_DELETE(self):
        if not check_rate_limit(self):
            send_json(self, 429, {"error": "Too many requests"})
            return

        resource = _parse_resource_from_qs(self)

        if resource == 'api_keys':
            self._delete_api_key()
        elif resource == 'profile':
            self._delete_account()
        else:
            send_json(self, 400, {"error": "resource query param must be 'api_keys' or 'profile'"})

    def _delete_api_key(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        data, err = _read_json_body(self)
        if err:
            return

        provider = (data.get('provider') or '').lower().strip()
        if provider not in VALID_PROVIDERS:
            send_json(self, 400, {"error": f"provider must be one of: {', '.join(VALID_PROVIDERS)}"})
            return

        user = _get_user(self, google_id)
        if not user:
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_api_keys
                WHERE user_id = %s AND provider = %s
                RETURNING id
            """, (user['id'], provider))
            row = cursor.fetchone()
            cursor.close()

        if not row:
            send_json(self, 404, {"error": f"No {provider} key found"})
            return

        send_json(self, 200, {
            "success": True,
            "message": f"{provider.capitalize()} API key deleted",
        })

    def _delete_account(self):
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
