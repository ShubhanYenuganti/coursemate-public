# Vercel Python Serverless Function — Google Drive Integration
# GET    /api/gdrive?action=auth               → initiate OAuth flow
# GET    /api/gdrive?action=callback           → handle OAuth callback
# GET    /api/gdrive?action=status             → connection status (email)
# GET    /api/gdrive?action=search             → search Drive folders
# GET    /api/gdrive?action=get_target         → get sticky export target
# GET    /api/gdrive?action=list_source_points → list course source points
# GET    /api/gdrive?action=finalize_connection → complete pending OAuth from cookie
# POST   /api/gdrive?action=set_target         → upsert sticky export target
# POST   /api/gdrive?action=export             → batch export (207 Multi-Status)
# POST   /api/gdrive?action=add_source_point   → add Drive folder as source
# POST   /api/gdrive?action=sync               → trigger integration poller for course
# DELETE /api/gdrive?action=revoke             → disconnect Google Drive
# DELETE /api/gdrive?action=remove_source_point → permanently remove source point
# PATCH  /api/gdrive?action=toggle_source_point → flip is_active for source point

from __future__ import annotations

import json
import os
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

import requests as http_requests

try:
    from .crypto_utils import decrypt_api_key, encrypt_api_key
    from .db import get_db
    from .middleware import (
        _parse_cookie,
        authenticate_request,
        get_cors_headers,
        handle_options,
        send_json,
    )
    from .models import User
    from .services.providers.gdrive import (
        flashcard_to_doc_requests,
        quiz_to_doc_requests,
        report_to_doc_requests,
    )
except ImportError:
    from crypto_utils import decrypt_api_key, encrypt_api_key
    from db import get_db
    from middleware import (
        _parse_cookie,
        authenticate_request,
        get_cors_headers,
        handle_options,
        send_json,
    )
    from models import User
    from services.providers.gdrive import (
        flashcard_to_doc_requests,
        quiz_to_doc_requests,
        report_to_doc_requests,
    )

_GDRIVE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GDRIVE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GDRIVE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
_DOCS_API_BASE = "https://docs.googleapis.com/v1"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Drive scopes: readonly for import, drive.file for export (only files we create)
_GDRIVE_SCOPES = " ".join([
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
])

_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()

_IS_HTTPS = os.environ.get("VERCEL_ENV") in ("production", "preview")
_AWS_REGION = (
    os.environ.get("COURSEMATE_AWS_REGION") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
)
_INTEGRATION_POLLER_ARN = os.environ.get("INTEGRATION_POLLER_LAMBDA_ARN", "")

_TOKEN_REFRESH_BUFFER_SECS = 300  # refresh 5 minutes before expiry


# ─── helpers ─────────────────────────────────────────────────────────────────


def _read_body(handler_self) -> tuple:
    try:
        length = int(handler_self.headers.get("Content-Length", 0))
        raw = handler_self.rfile.read(length).decode("utf-8")
        return (json.loads(raw) if raw else {}), False
    except (ValueError, json.JSONDecodeError):
        send_json(handler_self, 400, {"error": "Invalid request body"})
        return None, True


def _parse_qs_from_path(handler_self) -> dict:
    return parse_qs(urlparse(handler_self.path).query)


def _qs_get(qs: dict, key: str) -> str | None:
    vals = qs.get(key, [])
    return vals[0] if vals else None


_DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")


def _extract_drive_folder_id(raw: str) -> str | None:
    """Accept a Drive folder ID or URL and return the folder ID."""
    value = (raw or "").strip()
    if not value:
        return None
    if _DRIVE_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value)
    host = (parsed.netloc or "").lower()
    if not host:
        return None
    if not (host.endswith("drive.google.com") or host.endswith("docs.google.com")):
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if "folders" in parts:
        idx = parts.index("folders")
        if idx + 1 < len(parts):
            candidate = parts[idx + 1].strip()
            if _DRIVE_ID_RE.fullmatch(candidate):
                return candidate

    candidate = _qs_get(parse_qs(parsed.query), "id")
    if candidate and _DRIVE_ID_RE.fullmatch(candidate.strip()):
        return candidate.strip()
    return None


def _redirect(handler_self, location: str):
    handler_self.send_response(302)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Location", location)
    handler_self.end_headers()


def _get_user_from_request(handler_self):
    google_id, _ = authenticate_request(handler_self)
    if not google_id:
        send_json(handler_self, 401, {"error": "Unauthenticated"})
        return None, True
    user = User.get_by_google_id(google_id)
    if not user:
        send_json(handler_self, 404, {"error": "User not found"})
        return None, True
    return user["id"], False


# ─── token storage helpers ────────────────────────────────────────────────────


def _encrypt_token_payload(access_token: str, refresh_token: str, expires_in: int) -> str:
    """Encrypt Drive token JSON for storage in user_integrations."""
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
    }
    return encrypt_api_key(json.dumps(payload))


def _decrypt_token_payload(encrypted: str) -> dict | None:
    """Decrypt and parse stored Drive token JSON. Returns None on failure."""
    try:
        return json.loads(decrypt_api_key(encrypted))
    except Exception:
        return None


def get_valid_token(user_id: int, db=None) -> str | None:
    """
    Return a valid Drive access token for the user.
    Auto-refreshes if within 5 minutes of expiry.
    Returns None if the user has no Drive integration.
    Raises RuntimeError if the refresh token has been revoked.
    """
    def _fetch_and_refresh(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT encrypted_token FROM user_integrations WHERE user_id = %s AND provider = 'gdrive'",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None

        payload = _decrypt_token_payload(row["encrypted_token"])
        if not payload:
            return None

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_at = payload.get("expires_at", 0)

        if time.time() + _TOKEN_REFRESH_BUFFER_SECS < expires_at:
            return access_token

        # Token is near expiry — refresh
        if not refresh_token:
            raise RuntimeError("gdrive_token_revoked")

        resp = http_requests.post(
            _GDRIVE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
            },
            timeout=15,
        )

        if not resp.ok:
            raise RuntimeError("gdrive_token_revoked")

        token_data = resp.json()
        new_access = token_data.get("access_token")
        new_expires_in = token_data.get("expires_in", 3600)
        if not new_access:
            raise RuntimeError("gdrive_token_revoked")

        new_payload = {
            "access_token": new_access,
            "refresh_token": refresh_token,  # Google doesn't always return a new refresh token
            "expires_at": time.time() + new_expires_in,
        }
        new_encrypted = encrypt_api_key(json.dumps(new_payload))

        cur2 = conn.cursor()
        cur2.execute(
            """
            UPDATE user_integrations SET encrypted_token = %s
            WHERE user_id = %s AND provider = 'gdrive'
            """,
            (new_encrypted, user_id),
        )
        cur2.close()
        return new_access

    if db is not None:
        return _fetch_and_refresh(db)
    with get_db() as conn:
        return _fetch_and_refresh(conn)


def _drive_api(method: str, path: str, access_token: str, params: dict | None = None, body: dict | None = None, stream: bool = False):
    """Make a Drive API request. Returns (response_or_None, error_code_or_None)."""
    url = f"{_DRIVE_API_BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {access_token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    resp = http_requests.request(
        method.upper(),
        url,
        headers=headers,
        params=params,
        json=body,
        stream=stream,
        timeout=30,
    )
    if resp.status_code == 401:
        return None, "gdrive_token_revoked"
    if resp.status_code == 403:
        return None, "gdrive_permission_denied"
    if resp.status_code == 404:
        return None, "gdrive_not_found"
    if not resp.ok:
        return None, f"gdrive_api_error:{resp.status_code}"
    if stream:
        return resp, None
    try:
        return resp.json(), None
    except ValueError:
        return {}, None


def _docs_api(method: str, path: str, access_token: str, body: dict | None = None):
    """Make a Docs API request. Returns (response_or_None, error_code_or_None)."""
    url = f"{_DOCS_API_BASE}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    resp = http_requests.request(
        method.upper(),
        url,
        headers=headers,
        json=body,
        timeout=30,
    )
    if resp.status_code == 401:
        return None, "gdrive_token_revoked"
    if not resp.ok:
        return None, f"docs_api_error:{resp.status_code}"
    try:
        return resp.json(), None
    except ValueError:
        return {}, None


# ─── OAuth ────────────────────────────────────────────────────────────────────


def _handle_auth(handler_self):
    """Redirect user to Google OAuth consent page with CSRF state cookie."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": _CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": _GDRIVE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # always prompt to ensure refresh token is issued
        "state": state,
    }
    oauth_url = f"{_GDRIVE_AUTH_URL}?{urlencode(params)}"

    cookie_attrs = [
        "gdrive_oauth_state=" + state,
        "HttpOnly",
        "Max-Age=600",
        "Path=/api/gdrive",
    ]
    if _IS_HTTPS:
        cookie_attrs += ["Secure", "SameSite=Lax"]
    else:
        cookie_attrs.append("SameSite=Lax")

    handler_self.send_response(302)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Set-Cookie", "; ".join(cookie_attrs))
    handler_self.send_header("Location", oauth_url)
    handler_self.end_headers()


def _handle_callback(handler_self, qs: dict):
    """Exchange OAuth code for tokens, upsert into user_integrations."""
    code = _qs_get(qs, "code")
    state = _qs_get(qs, "state")
    error = _qs_get(qs, "error")

    if error:
        _redirect(handler_self, "/profile?gdrive_error=access_denied")
        return

    cookie_header = handler_self.headers.get("Cookie", "")
    expected_state = _parse_cookie(cookie_header, "gdrive_oauth_state")
    if not expected_state or state != expected_state:
        send_json(handler_self, 400, {"error": "Invalid OAuth state"})
        return

    if not code:
        send_json(handler_self, 400, {"error": "Missing code"})
        return

    token_resp = http_requests.post(
        _GDRIVE_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT_URI,
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
        },
        timeout=15,
    )

    if not token_resp.ok:
        send_json(handler_self, 502, {"error": "Failed to exchange Google OAuth code"})
        return

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        send_json(handler_self, 502, {"error": "Missing tokens in Google response"})
        return

    # Fetch Google account email to store in metadata
    email = _fetch_google_email(access_token)

    encrypted = _encrypt_token_payload(access_token, refresh_token, expires_in)

    # SameSite cookie workaround: session cookie may not be sent on cross-site redirect
    google_id, _ = authenticate_request(handler_self)
    if not google_id:
        pending_payload = json.dumps({
            "encrypted": encrypted,
            "email": email,
        })
        encrypted_pending = encrypt_api_key(pending_payload)
        pending_cookie_attrs = [
            f"gdrive_pending_token={encrypted_pending}",
            "HttpOnly",
            "Max-Age=300",
            "Path=/api/gdrive",
        ]
        if _IS_HTTPS:
            pending_cookie_attrs += ["Secure", "SameSite=Lax"]
        else:
            pending_cookie_attrs.append("SameSite=Lax")
        clear_state = "gdrive_oauth_state=; HttpOnly; Max-Age=0; Path=/api/gdrive"
        handler_self.send_response(302)
        for k, v in get_cors_headers().items():
            handler_self.send_header(k, v)
        handler_self.send_header("Set-Cookie", "; ".join(pending_cookie_attrs))
        handler_self.send_header("Set-Cookie", clear_state)
        handler_self.send_header("Location", "/profile?gdrive_pending=1")
        handler_self.end_headers()
        return

    user = User.get_by_google_id(google_id)
    if not user:
        send_json(handler_self, 404, {"error": "User not found"})
        return

    _upsert_gdrive_integration(user["id"], encrypted, email)

    clear_cookie = "gdrive_oauth_state=; HttpOnly; Max-Age=0; Path=/api/gdrive"
    handler_self.send_response(302)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Set-Cookie", clear_cookie)
    handler_self.send_header("Location", "/profile?gdrive_connected=1")
    handler_self.end_headers()


def _fetch_google_email(access_token: str) -> str | None:
    """Fetch the Google account email from the userinfo endpoint."""
    try:
        resp = http_requests.get(
            _USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("email")
    except Exception:
        pass
    return None


def _upsert_gdrive_integration(user_id: int, encrypted_token: str, email: str | None):
    metadata = {"email": email} if email else {}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_integrations (user_id, provider, encrypted_token, metadata)
            VALUES (%s, 'gdrive', %s, %s)
            ON CONFLICT (user_id, provider)
            DO UPDATE SET encrypted_token = EXCLUDED.encrypted_token,
                          metadata = EXCLUDED.metadata,
                          connected_at = CURRENT_TIMESTAMP
            """,
            (user_id, encrypted_token, json.dumps(metadata)),
        )
        cur.close()


def _handle_finalize_connection(handler_self, user_id: int):
    """Complete a pending Drive OAuth connection using the stashed pending cookie."""
    cookie_header = handler_self.headers.get("Cookie", "")
    encrypted_pending = _parse_cookie(cookie_header, "gdrive_pending_token")
    if not encrypted_pending:
        send_json(handler_self, 400, {"error": "No pending Google Drive connection"})
        return

    try:
        payload = json.loads(decrypt_api_key(encrypted_pending))
        encrypted = payload["encrypted"]
        email = payload.get("email")
    except Exception:
        send_json(handler_self, 400, {"error": "Invalid or expired pending token"})
        return

    _upsert_gdrive_integration(user_id, encrypted, email)

    clear_pending = "gdrive_pending_token=; HttpOnly; Max-Age=0; Path=/api/gdrive"
    handler_self.send_response(200)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Content-Type", "application/json")
    handler_self.send_header("Set-Cookie", clear_pending)
    handler_self.end_headers()
    handler_self.wfile.write(json.dumps({
        "connected": True,
        "email": email,
    }).encode())


# ─── status ───────────────────────────────────────────────────────────────────


def _handle_status(handler_self, user_id: int):
    """Return Drive connection status including Google account email."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT metadata FROM user_integrations WHERE user_id = %s AND provider = 'gdrive'",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()

    if not row:
        send_json(handler_self, 200, {"connected": False})
        return

    try:
        access_token = get_valid_token(user_id)
    except RuntimeError:
        send_json(handler_self, 401, {"error": "gdrive_token_revoked"})
        return

    if not access_token:
        send_json(handler_self, 200, {"connected": False})
        return

    meta = row.get("metadata") or {}
    email = _fetch_google_email(access_token) or meta.get("email")

    # Keep metadata email fresh when userinfo returns one.
    if email and email != meta.get("email"):
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_integrations
                SET metadata = %s
                WHERE user_id = %s AND provider = 'gdrive'
                """,
                (json.dumps({"email": email}), user_id),
            )
            cur.close()

    send_json(handler_self, 200, {
        "connected": True,
        "email": email,
    })


# ─── revoke ──────────────────────────────────────────────────────────────────


def _handle_revoke(handler_self, user_id: int):
    """Delete Drive integration and all sticky targets for the user."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM user_integrations WHERE user_id = %s AND provider = 'gdrive' RETURNING id",
            (user_id,),
        )
        deleted = cur.fetchone()
        if deleted:
            cur.execute(
                "DELETE FROM course_export_targets WHERE user_id = %s AND provider = 'gdrive'",
                (user_id,),
            )
        cur.close()

    if not deleted:
        send_json(handler_self, 404, {"error": "Google Drive integration not found"})
        return

    send_json(handler_self, 200, {"disconnected": True})


# ─── search ───────────────────────────────────────────────────────────────────


def _handle_search(handler_self, user_id: int, qs: dict):
    """Search Drive for folders matching a query term, or list recent folders."""
    try:
        access_token = get_valid_token(user_id)
    except RuntimeError:
        send_json(handler_self, 401, {"error": "gdrive_token_revoked"})
        return

    if not access_token:
        send_json(handler_self, 403, {"error": "Google Drive not connected"})
        return

    query_term = _qs_get(qs, "q") or ""
    folder_mime = "application/vnd.google-apps.folder"

    if query_term:
        q = f"mimeType='{folder_mime}' and trashed=false and name contains '{query_term.replace(chr(39), '')}'"
        params = {"q": q, "fields": "files(id,name)", "pageSize": 20}
    else:
        q = f"mimeType='{folder_mime}' and trashed=false"
        params = {"q": q, "fields": "files(id,name)", "pageSize": 20, "orderBy": "modifiedTime desc"}

    data, err = _drive_api("GET", "/files", access_token, params=params)
    if err == "gdrive_token_revoked":
        send_json(handler_self, 401, {"error": "gdrive_token_revoked"})
        return
    if err:
        send_json(handler_self, 502, {"error": "Drive search failed", "code": err})
        return

    results = [{"id": f["id"], "name": f["name"]} for f in (data or {}).get("files", [])]
    send_json(handler_self, 200, {"results": results})


# ─── sticky target ────────────────────────────────────────────────────────────


def _handle_set_target(handler_self, user_id: int, body: dict):
    """Upsert sticky export target for a course/generation_type."""
    course_id = body.get("course_id")
    generation_type = body.get("generation_type")
    target_id = body.get("target_id")
    target_title = body.get("target_title")

    if not all([course_id, generation_type, target_id]):
        send_json(handler_self, 400, {"error": "course_id, generation_type, target_id required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO course_export_targets
                (user_id, course_id, provider, generation_type, external_target_id,
                 external_target_title, updated_at)
            VALUES (%s, %s, 'gdrive', %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, course_id, provider, generation_type)
            DO UPDATE SET external_target_id    = EXCLUDED.external_target_id,
                          external_target_title = EXCLUDED.external_target_title,
                          updated_at            = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (user_id, course_id, generation_type, target_id, target_title),
        )
        row = cur.fetchone()
        cur.close()

    send_json(handler_self, 200, {"target": dict(row) if row else None})


def _handle_get_target(handler_self, user_id: int, qs: dict):
    """Return existing sticky target for (user, course, generation_type)."""
    course_id = _qs_get(qs, "course_id")
    generation_type = _qs_get(qs, "generation_type")

    if not course_id or not generation_type:
        send_json(handler_self, 400, {"error": "course_id and generation_type required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT external_target_id AS id, external_target_title AS title
            FROM course_export_targets
            WHERE user_id = %s AND course_id = %s AND provider = 'gdrive'
              AND generation_type = %s
            """,
            (user_id, course_id, generation_type),
        )
        row = cur.fetchone()
        cur.close()

    send_json(handler_self, 200, {"target": dict(row) if row else None})


# ─── export ──────────────────────────────────────────────────────────────────


def _handle_export(handler_self, user_id: int, body: dict):
    """
    POST /api/gdrive?action=export
    Shape: { exports: [{ generation_id, generation_type, targets: [{ provider, target_id, name? }] }] }
    Returns 207 Multi-Status.
    """
    exports = body.get("exports", [])
    if not isinstance(exports, list) or not exports:
        send_json(handler_self, 400, {"error": "exports array required"})
        return

    try:
        access_token = get_valid_token(user_id)
    except RuntimeError:
        send_json(handler_self, 401, {"error": "gdrive_token_revoked"})
        return

    if not access_token:
        send_json(handler_self, 401, {"error": "Google Drive not connected"})
        return

    results = []
    for export_item in exports:
        generation_id = export_item.get("generation_id")
        generation_type = export_item.get("generation_type")
        targets = export_item.get("targets", [])

        for tgt in targets:
            provider = tgt.get("provider")
            target_id = tgt.get("target_id")

            if provider != "gdrive":
                results.append({
                    "generation_id": generation_id,
                    "generation_type": generation_type,
                    "provider": provider,
                    "target_id": target_id,
                    "status": "error",
                    "error": f"Unsupported provider: {provider}",
                })
                continue

            name = (tgt.get("name") or "").strip()
            result = _dispatch_export(user_id, generation_id, generation_type, target_id, access_token, name)
            result["generation_id"] = generation_id
            result["generation_type"] = generation_type
            result["provider"] = provider
            result["target_id"] = target_id
            results.append(result)

    succeeded = sum(1 for r in results if r.get("status") == "success")
    failed = len(results) - succeeded
    send_json(handler_self, 207, {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    })


def _dispatch_export(user_id, generation_id, generation_type, folder_id, access_token, name=""):
    if generation_type == "flashcards":
        return _export_flashcards(user_id, generation_id, folder_id, access_token, name)
    elif generation_type == "quiz":
        return _export_quiz(user_id, generation_id, folder_id, access_token, name)
    elif generation_type == "report":
        return _export_report(user_id, generation_id, folder_id, access_token, name)
    else:
        return {"status": "error", "error": f"Unknown generation_type: {generation_type}"}


def _create_doc_in_folder(title: str, folder_id: str, access_token: str) -> tuple[str | None, str | None, str | None]:
    """
    Create a new Google Doc and move it into the target folder.
    Returns (doc_id, doc_url, error).
    """
    # Create blank document
    doc_data, err = _docs_api("POST", "/documents", access_token, body={"title": title or "Untitled"})
    if err:
        return None, None, err
    doc_id = doc_data.get("documentId")
    if not doc_id:
        return None, None, "No documentId in Docs API response"

    # Move to target folder via Drive files.update
    _, mv_err = _drive_api(
        "PATCH",
        f"/files/{doc_id}",
        access_token,
        params={"addParents": folder_id, "removeParents": "root", "fields": "id,parents"},
    )
    if mv_err:
        # Non-fatal: doc was created, just not in the right folder
        print(f"[gdrive] Warning: could not move doc {doc_id} to folder {folder_id}: {mv_err}")

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    return doc_id, doc_url, None


def _apply_doc_content(doc_id: str, requests: list, access_token: str) -> str | None:
    """Apply batchUpdate requests to a Google Doc. Returns error string or None."""
    if not requests:
        return None
    _, err = _docs_api("POST", f"/documents/{doc_id}:batchUpdate", access_token, body={"requests": requests})
    return err


def _export_flashcards(user_id, generation_id, folder_id, access_token, name=""):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fg.id, fg.status, fg.generated_by,
                   array_agg(
                       json_build_object(
                           'front', fc.front_text,
                           'back',  fc.back_text,
                           'hint',  fc.hint_text
                       ) ORDER BY fc.card_index
                   ) AS cards
            FROM flashcard_generations fg
            LEFT JOIN flashcard_cards fc ON fc.generation_id = fg.id
            WHERE fg.id = %s
            GROUP BY fg.id, fg.status, fg.generated_by
            """,
            (generation_id,),
        )
        row = cur.fetchone()
        cur.close()

    if not row:
        return {"status": "error", "error": "Generation not found"}
    if row["generated_by"] != user_id:
        return {"status": "error", "error": "Forbidden"}
    if row["status"] != "ready":
        return {"status": "error", "error": f"Generation not ready (status={row['status']})"}

    doc_title = name or "Flashcards"
    doc_id, doc_url, err = _create_doc_in_folder(doc_title, folder_id, access_token)
    if err:
        return {"status": "error", "error": f"Failed to create document: {err}"}

    cards = row["cards"] or []
    requests = flashcard_to_doc_requests([c for c in cards if c])
    apply_err = _apply_doc_content(doc_id, requests, access_token)
    if apply_err:
        return {"status": "error", "error": f"Failed to write content: {apply_err}", "url": doc_url}

    return {"status": "success", "exported_count": len(cards), "url": doc_url}


def _export_quiz(user_id, generation_id, folder_id, access_token, name=""):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT qg.id, qg.status, qg.generated_by,
                   array_agg(
                       json_build_object(
                           'question', qq.question_text,
                           'type',     qq.question_type,
                           'answer',   qq.correct_answer_text,
                           'explanation', qq.explanation,
                           'options',  (
                               SELECT array_agg(qo.option_text ORDER BY qo.option_index)
                               FROM quiz_question_options qo
                               WHERE qo.question_id = qq.id
                           )
                       ) ORDER BY qq.question_index
                   ) AS questions
            FROM quiz_generations qg
            LEFT JOIN quiz_questions qq ON qq.generation_id = qg.id
            WHERE qg.id = %s
            GROUP BY qg.id, qg.status, qg.generated_by
            """,
            (generation_id,),
        )
        row = cur.fetchone()
        cur.close()

    if not row:
        return {"status": "error", "error": "Generation not found"}
    if row["generated_by"] != user_id:
        return {"status": "error", "error": "Forbidden"}
    if row["status"] != "ready":
        return {"status": "error", "error": f"Generation not ready (status={row['status']})"}

    doc_title = name or "Quiz"
    doc_id, doc_url, err = _create_doc_in_folder(doc_title, folder_id, access_token)
    if err:
        return {"status": "error", "error": f"Failed to create document: {err}"}

    questions = row["questions"] or []
    requests = quiz_to_doc_requests([q for q in questions if q])
    apply_err = _apply_doc_content(doc_id, requests, access_token)
    if apply_err:
        return {"status": "error", "error": f"Failed to write content: {apply_err}", "url": doc_url}

    return {"status": "success", "exported_count": len(questions), "url": doc_url}


def _export_report(user_id, generation_id, folder_id, access_token, name=""):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT rg.id, rg.status, rg.generated_by,
                   rv.sections_json, rv.title
            FROM report_generations rg
            LEFT JOIN report_versions rv ON rv.generation_id = rg.id
            WHERE rg.id = %s
            ORDER BY rv.version_number DESC
            LIMIT 1
            """,
            (generation_id,),
        )
        row = cur.fetchone()
        cur.close()

    if not row:
        return {"status": "error", "error": "Generation not found"}
    if row["generated_by"] != user_id:
        return {"status": "error", "error": "Forbidden"}
    if row["status"] != "ready":
        return {"status": "error", "error": f"Generation not ready (status={row['status']})"}

    doc_title = name or str(row.get("title") or "").strip() or "Report"
    doc_id, doc_url, err = _create_doc_in_folder(doc_title, folder_id, access_token)
    if err:
        return {"status": "error", "error": f"Failed to create document: {err}"}

    sections = row["sections_json"] or []
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except ValueError:
            sections = []

    requests = report_to_doc_requests(sections)
    apply_err = _apply_doc_content(doc_id, requests, access_token)
    if apply_err:
        return {"status": "error", "error": f"Failed to write content: {apply_err}", "url": doc_url}

    return {"status": "success", "exported_count": len(sections), "url": doc_url}


# ─── source points ────────────────────────────────────────────────────────────


def _handle_add_source_point(handler_self, user_id: int, body: dict):
    """Add a Drive folder as a course source point."""
    try:
        access_token = get_valid_token(user_id)
    except RuntimeError:
        send_json(handler_self, 401, {"error": "gdrive_token_revoked"})
        return

    if not access_token:
        send_json(handler_self, 403, {"error": "Google Drive not connected"})
        return

    course_id = body.get("course_id")
    raw_external_id = body.get("external_id", "").strip()
    external_id = _extract_drive_folder_id(raw_external_id)
    external_title = body.get("external_title", "").strip()

    if not course_id or not raw_external_id:
        send_json(handler_self, 400, {"error": "course_id and external_id required"})
        return
    if not external_id:
        send_json(handler_self, 400, {"error": "external_id must be a valid Drive folder ID or URL"})
        return

    # Validate folder is accessible
    folder_data, err = _drive_api(
        "GET",
        f"/files/{external_id}",
        access_token,
        params={"fields": "id,name,mimeType"},
    )
    if err == "gdrive_not_found" or err == "gdrive_permission_denied":
        send_json(handler_self, 403, {"error": "Folder not accessible. Verify the folder is shared with this Google account."})
        return
    if err:
        send_json(handler_self, 502, {"error": f"Could not verify folder: {err}"})
        return
    if (folder_data or {}).get("mimeType") != "application/vnd.google-apps.folder":
        send_json(handler_self, 400, {"error": "external_id must reference a Drive folder"})
        return

    # Use the folder's actual name if no title provided
    resolved_title = external_title or (folder_data or {}).get("name") or ""

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO integration_source_points
                    (user_id, course_id, provider, external_id, external_title, metadata)
                VALUES (%s, %s, 'gdrive', %s, %s, %s)
                RETURNING *
                """,
                (user_id, course_id, external_id, resolved_title or None, json.dumps({})),
            )
            row = cur.fetchone()
        except Exception as exc:
            if "unique" in str(exc).lower():
                send_json(handler_self, 409, {"error": "This Drive folder is already a source point for this course"})
                return
            raise
        cur.close()

    sync_triggered = False
    sync_error = None

    if _INTEGRATION_POLLER_ARN and row:
        try:
            import boto3
            lmbd = boto3.client("lambda", region_name=_AWS_REGION)
            lmbd.invoke(
                FunctionName=_INTEGRATION_POLLER_ARN,
                InvocationType="Event",
                Payload=json.dumps({
                    "source_point_id": int(row["id"]),
                    "user_id": user_id,
                    "course_id": int(course_id),
                    "force_full_sync": True,
                }).encode(),
            )
            sync_triggered = True
        except Exception as exc:
            sync_error = str(exc)
    elif not _INTEGRATION_POLLER_ARN:
        sync_error = "INTEGRATION_POLLER_LAMBDA_ARN not configured"

    send_json(handler_self, 201, {
        "source_point": dict(row) if row else None,
        "sync_triggered": sync_triggered,
        "sync_error": sync_error,
    })


def _handle_list_source_points(handler_self, user_id: int, qs: dict):
    course_id = _qs_get(qs, "course_id")
    if not course_id:
        send_json(handler_self, 400, {"error": "course_id required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, external_id, external_title, is_active, last_synced_at, created_at, metadata
            FROM integration_source_points
            WHERE user_id = %s AND course_id = %s AND provider = 'gdrive'
            ORDER BY created_at DESC
            """,
            (user_id, course_id),
        )
        rows = cur.fetchall()
        cur.close()

    send_json(handler_self, 200, {"source_points": [dict(r) for r in rows]})


def _handle_toggle_source_point(handler_self, user_id: int, qs: dict):
    sp_id = _qs_get(qs, "id")
    if not sp_id:
        send_json(handler_self, 400, {"error": "id required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE integration_source_points
            SET is_active = NOT is_active
            WHERE id = %s AND user_id = %s AND provider = 'gdrive'
            RETURNING *
            """,
            (sp_id, user_id),
        )
        row = cur.fetchone()
        cur.close()

    if not row:
        send_json(handler_self, 404, {"error": "Source point not found"})
        return

    send_json(handler_self, 200, {"source_point": dict(row)})


def _handle_remove_source_point(handler_self, user_id: int, qs: dict):
    sp_id = _qs_get(qs, "id")
    if not sp_id:
        send_json(handler_self, 400, {"error": "id required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM integration_source_points WHERE id = %s AND user_id = %s AND provider = 'gdrive' RETURNING id",
            (sp_id, user_id),
        )
        deleted = cur.fetchone()
        cur.close()

    if not deleted:
        send_json(handler_self, 404, {"error": "Source point not found"})
        return

    handler_self.send_response(204)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.end_headers()


def _handle_sync(handler_self, user_id: int, body: dict):
    """Invoke integration_poller Lambda for the user's active Drive source points in a course."""
    course_id = (
        body.get("course_id")
        or _parse_qs_from_path(handler_self).get("course_id", [None])[0]
    )
    if not course_id:
        send_json(handler_self, 400, {"error": "course_id required"})
        return

    if not _INTEGRATION_POLLER_ARN:
        send_json(handler_self, 202, {"message": "Sync accepted (Lambda not configured)"})
        return

    try:
        import boto3
        lmbd = boto3.client("lambda", region_name=_AWS_REGION)
        lmbd.invoke(
            FunctionName=_INTEGRATION_POLLER_ARN,
            InvocationType="Event",
            Payload=json.dumps({"user_id": user_id, "course_id": int(course_id)}).encode(),
        )
    except Exception as e:
        import traceback
        print(f"[gdrive sync] Lambda invoke failed: {e}\n{traceback.format_exc()}")

    send_json(handler_self, 202, {"message": "Sync triggered"})


# ─── main handler ─────────────────────────────────────────────────────────────


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_GET(self):
        qs = _parse_qs_from_path(self)
        action = _qs_get(qs, "action")

        if action == "auth":
            _handle_auth(self)
            return

        if action == "callback" or (action is None and _qs_get(qs, "code")):
            _handle_callback(self, qs)
            return

        user_id, err = _get_user_from_request(self)
        if err:
            return

        if action == "status":
            _handle_status(self, user_id)
        elif action == "finalize_connection":
            _handle_finalize_connection(self, user_id)
        elif action == "search":
            _handle_search(self, user_id, qs)
        elif action == "get_target":
            _handle_get_target(self, user_id, qs)
        elif action == "list_source_points":
            _handle_list_source_points(self, user_id, qs)
        else:
            send_json(self, 400, {"error": f"Unknown GET action: {action}"})

    def do_POST(self):
        body, err_sent = _read_body(self)
        if err_sent:
            return

        qs = _parse_qs_from_path(self)
        action = _qs_get(qs, "action") or body.get("action")

        user_id, err = _get_user_from_request(self)
        if err:
            return

        if action == "set_target":
            _handle_set_target(self, user_id, body)
        elif action == "export":
            _handle_export(self, user_id, body)
        elif action == "add_source_point":
            _handle_add_source_point(self, user_id, body)
        elif action == "sync":
            _handle_sync(self, user_id, body)
        else:
            send_json(self, 400, {"error": f"Unknown POST action: {action}"})

    def do_DELETE(self):
        qs = _parse_qs_from_path(self)
        action = _qs_get(qs, "action")
        body, _ = _read_body(self)
        if not action and body:
            action = body.get("action")

        user_id, err = _get_user_from_request(self)
        if err:
            return

        if action == "revoke":
            _handle_revoke(self, user_id)
        elif action == "remove_source_point":
            _handle_remove_source_point(self, user_id, qs)
        else:
            send_json(self, 400, {"error": f"Unknown DELETE action: {action}"})

    def do_PATCH(self):
        body, err_sent = _read_body(self)
        if err_sent:
            return

        qs = _parse_qs_from_path(self)
        action = _qs_get(qs, "action") or body.get("action")

        user_id, err = _get_user_from_request(self)
        if err:
            return

        if action == "toggle_source_point":
            _handle_toggle_source_point(self, user_id, qs)
        else:
            send_json(self, 400, {"error": f"Unknown PATCH action: {action}"})

    def log_message(self, format, *args):  # noqa: A002
        pass  # suppress default access log noise
