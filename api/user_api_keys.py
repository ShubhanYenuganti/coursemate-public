# Vercel Python Serverless Function — User API Keys
# GET    /api/user_api_keys               → which providers have a key saved (booleans only)
# POST   /api/user_api_keys               → upsert a key  { provider, api_key }
# DELETE /api/user_api_keys               → remove a key  { provider }

import json
from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .models import User
    from .db import get_db
    from .crypto_utils import encrypt_api_key, decrypt_api_key
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from models import User
    from db import get_db
    from crypto_utils import encrypt_api_key, decrypt_api_key

VALID_PROVIDERS = ('gemini', 'openai', 'claude')


def _get_user(handler, google_id):
    """Resolve google_id → user row. Sends 404 and returns None on miss."""
    user = User.get_by_google_id(google_id)
    if not user:
        send_json(handler, 404, {"error": "User not found"})
    return user


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ------------------------------------------------------------------ GET --
    # Returns only boolean flags — never exposes ciphertext or plaintext.
    def do_GET(self):
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
    # Upserts (insert or update) an encrypted key for a provider.
    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
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

    # --------------------------------------------------------------- DELETE --
    # Removes a saved key for a provider.
    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
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
