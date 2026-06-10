import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .models import User
    from .db import get_db
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from models import User
    from db import get_db


def _validate_prompt(body: dict) -> tuple:
    title = (body.get('title') or '').strip()
    text = (body.get('body') or '').strip()
    if not title:
        raise ValueError("title is required")
    if not text:
        raise ValueError("body is required")
    return (title, text)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ------------------------------------------------------------------ GET --
    def do_GET(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, body, created_at FROM saved_prompts WHERE user_id=%s ORDER BY created_at DESC",
                (user['id'],),
            )
            rows = cursor.fetchall()

        prompts = [
            {"id": r["id"], "title": r["title"], "body": r["body"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ]
        send_json(self, 200, {"prompts": prompts})

    # ----------------------------------------------------------------- POST --
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

        try:
            title, text = _validate_prompt(data)
        except ValueError as e:
            send_json(self, 400, {"error": str(e)})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO saved_prompts (user_id, title, body) VALUES (%s,%s,%s) RETURNING id, title, body, created_at",
                (user['id'], title, text),
            )
            row = cursor.fetchone()
            conn.commit()

        prompt = {"id": row["id"], "title": row["title"], "body": row["body"], "created_at": row["created_at"].isoformat()}
        send_json(self, 201, {"prompt": prompt})

    # --------------------------------------------------------------- DELETE --
    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        prompt_id_raw = params.get('id', [None])[0]
        if not prompt_id_raw or not prompt_id_raw.isdigit():
            send_json(self, 400, {"error": "id is required"})
            return
        prompt_id = int(prompt_id_raw)

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_prompts WHERE id=%s AND user_id=%s",
                (prompt_id, user['id']),
            )
            deleted = cursor.rowcount
            conn.commit()

        if deleted:
            send_json(self, 200, {"success": True})
        else:
            send_json(self, 404, {"error": "Prompt not found"})
