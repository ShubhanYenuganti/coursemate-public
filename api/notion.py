# Vercel Python Serverless Function — Notion Integration
# GET    /api/notion?action=auth               → initiate OAuth flow
# GET    /api/notion?action=callback           → handle OAuth callback
# GET    /api/notion?action=status             → connection status
# GET    /api/notion?action=search             → search pages/databases
# GET    /api/notion?action=get_target         → get sticky export target
# GET    /api/notion?action=list_source_points → list course source points
# GET    /api/notion?action=list_source_point_files → list pages in a source point database (paginated, with sync state)
# POST   /api/notion?action=set_target         → upsert sticky export target
# POST   /api/notion?action=export             → batch export (207 Multi-Status)
# POST   /api/notion?action=create_target      → create new Notion page/db, auto-select
# POST   /api/notion?action=add_source_point   → add Notion database as source
# POST   /api/notion?action=sync               → trigger integration poller for course
# DELETE /api/notion?action=revoke             → disconnect Notion
# DELETE /api/notion?action=remove_source_point → permanently remove source point
# PATCH  /api/notion?action=toggle_source_point → flip is_active for source point

from __future__ import annotations

import json
import os
import re
import secrets
import sys
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
    from .services.export_blocks import (
        flashcard_to_notion_toggle_block,
        quiz_to_notion_blocks,
        report_to_notion_blocks,
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
    from services.export_blocks import (
        flashcard_to_notion_toggle_block,
        quiz_to_notion_blocks,
        report_to_notion_blocks,
    )

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2026-03-11"
_NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
_NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"

_CLIENT_ID = os.environ.get("NOTION_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("NOTION_CLIENT_SECRET", "")
_REDIRECT_URI = os.environ.get("NOTION_REDIRECT_URI", "")

_IS_HTTPS = os.environ.get("VERCEL_ENV") in ("production", "preview")
_AWS_REGION = (
    os.environ.get("COURSEMATE_AWS_REGION")
    or os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or "us-east-1"
)
_INTEGRATION_POLLER_ARN = os.environ.get("INTEGRATION_POLLER_LAMBDA_ARN", "")


# ─── helpers ─────────────────────────────────────────────────────────────────


def _read_body(handler_self) -> tuple:
    """Read and parse JSON body. Returns (data, error_sent)."""
    try:
        length = int(handler_self.headers.get("Content-Length", 0))
        raw = handler_self.rfile.read(length).decode("utf-8")
        return (json.loads(raw) if raw else {}), False
    except (ValueError, json.JSONDecodeError):
        send_json(handler_self, 400, {"error": "Invalid request body"})
        return None, True


def _parse_qs_from_path(handler_self) -> dict:
    """Return parsed query string dict from request path."""
    return parse_qs(urlparse(handler_self.path).query)


def _qs_get(qs: dict, key: str) -> str | None:
    vals = qs.get(key, [])
    return vals[0] if vals else None


def _source_point_id_from_qs_or_body(qs: dict, body: dict | None = None) -> str | None:
    """Resolve source point id from query string, with legacy body fallback."""
    sp_id = _qs_get(qs, "id")
    if sp_id:
        return sp_id
    if body and isinstance(body, dict):
        legacy_id = body.get("source_point_id")
        if legacy_id is not None:
            return str(legacy_id)
    return None


def _get_notion_token(user_id: int) -> str | None:
    """Fetch and decrypt the user's Notion token. Returns None if not connected."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT encrypted_token FROM user_integrations WHERE user_id = %s AND provider = 'notion'",
            (user_id,),
        )
        row = cursor.fetchone()
        cursor.close()
    if not row:
        return None
    try:
        return decrypt_api_key(row["encrypted_token"])
    except ValueError:
        return None


def _notion_api(
    method: str,
    path: str,
    token: str,
    body: dict | None = None,
    user_id: int | None = None,
):
    """
    Make a raw request to the Notion API.
    Returns (response_dict_or_None, error_code_or_None, error_detail_or_None).
    error_code is 'notion_token_revoked' if the token has been revoked.
    error_detail is the raw Notion error body for surfacing in API responses.
    """
    url = f"{_NOTION_API_BASE}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    resp = http_requests.request(
        method.upper(),
        url,
        headers=headers,
        json=body,
        timeout=20,
    )

    if resp.status_code == 401:
        if user_id is not None:
            try:
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "DELETE FROM user_integrations WHERE user_id = %s AND provider = 'notion'",
                        (user_id,),
                    )
                    cur.close()
            except Exception:
                pass
        return None, "notion_token_revoked", None

    if not resp.ok:
        err_code = f"notion_api_error:{resp.status_code}"
        try:
            err_detail = resp.json()
        except Exception:
            err_detail = {"raw": resp.text[:500]}
        return None, err_code, err_detail

    try:
        return resp.json(), None, None
    except ValueError:
        return {}, None, None


def _get_user_from_request(handler_self):
    """Authenticate and resolve user. Returns (user_id, None) or (None, error_sent=True)."""
    google_id, _ = authenticate_request(handler_self)
    if not google_id:
        send_json(handler_self, 401, {"error": "Unauthenticated"})
        return None, True
    user = User.get_by_google_id(google_id)
    if not user:
        send_json(handler_self, 404, {"error": "User not found"})
        return None, True
    return user["id"], False


# ─── OAuth ───────────────────────────────────────────────────────────────────


def _handle_auth(handler_self):
    """Redirect user to Notion OAuth consent page with CSRF state cookie."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": _CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    oauth_url = f"{_NOTION_AUTH_URL}?{urlencode(params)}"

    cookie_attrs = [
        "notion_oauth_state=" + state,
        "HttpOnly",
        "Max-Age=600",
        "Path=/api/notion",
    ]
    if _IS_HTTPS:
        cookie_attrs += ["Secure", "SameSite=Lax"]
    else:
        cookie_attrs.append("SameSite=Lax")
    cookie = "; ".join(cookie_attrs)

    handler_self.send_response(302)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Set-Cookie", cookie)
    handler_self.send_header("Location", oauth_url)
    handler_self.end_headers()


def _handle_callback(handler_self, qs: dict):
    """Exchange OAuth code for token, upsert into user_integrations."""
    code = _qs_get(qs, "code")
    state = _qs_get(qs, "state")
    error = _qs_get(qs, "error")

    if error:
        _redirect(handler_self, "/profile?notion_error=access_denied")
        return

    cookie_header = handler_self.headers.get("Cookie", "")
    expected_state = _parse_cookie(cookie_header, "notion_oauth_state")
    if not expected_state or state != expected_state:
        send_json(handler_self, 400, {"error": "Invalid OAuth state"})
        return

    if not code:
        send_json(handler_self, 400, {"error": "Missing code"})
        return

    # Exchange code for token
    import base64

    credentials = base64.b64encode(f"{_CLIENT_ID}:{_CLIENT_SECRET}".encode()).decode()
    token_resp = http_requests.post(
        _NOTION_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT_URI,
        },
        timeout=15,
    )

    if not token_resp.ok:
        send_json(handler_self, 502, {"error": "Failed to exchange Notion OAuth code"})
        return

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        send_json(handler_self, 502, {"error": "No access_token in Notion response"})
        return

    metadata = {
        "workspace_id": token_data.get("workspace_id"),
        "workspace_name": token_data.get("workspace_name"),
        "workspace_icon": token_data.get("workspace_icon"),
        "bot_id": token_data.get("bot_id"),
    }

    # Need user_id — require session.
    # SameSite=Strict on the session cookie means it is NOT sent on cross-site redirects
    # (notion.com → our domain). Stash the token in a short-lived encrypted cookie and
    # let the profile page finalize via a same-site fetch that will carry the session cookie.
    google_id, _ = authenticate_request(handler_self)
    if not google_id:
        pending_payload = json.dumps({"token": access_token, "metadata": metadata})
        encrypted_pending = encrypt_api_key(pending_payload)
        pending_cookie_attrs = [
            f"notion_pending_token={encrypted_pending}",
            "HttpOnly",
            "Max-Age=300",
            "Path=/api/notion",
        ]
        if _IS_HTTPS:
            pending_cookie_attrs += ["Secure", "SameSite=Lax"]
        else:
            pending_cookie_attrs.append("SameSite=Lax")
        clear_state = "notion_oauth_state=; HttpOnly; Max-Age=0; Path=/api/notion"
        handler_self.send_response(302)
        for k, v in get_cors_headers().items():
            handler_self.send_header(k, v)
        handler_self.send_header("Set-Cookie", "; ".join(pending_cookie_attrs))
        handler_self.send_header("Set-Cookie", clear_state)
        handler_self.send_header("Location", "/profile?notion_pending=1")
        handler_self.end_headers()
        return

    user = User.get_by_google_id(google_id)
    if not user:
        send_json(handler_self, 404, {"error": "User not found"})
        return
    user_id = user["id"]

    _upsert_notion_integration(user_id, access_token, metadata)

    # Clear state cookie and redirect to profile
    clear_cookie = "notion_oauth_state=; HttpOnly; Max-Age=0; Path=/api/notion"
    handler_self.send_response(302)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Set-Cookie", clear_cookie)
    handler_self.send_header("Location", "/profile?notion_connected=1")
    handler_self.end_headers()


def _upsert_notion_integration(user_id: int, access_token: str, metadata: dict):
    encrypted = encrypt_api_key(access_token)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_integrations (user_id, provider, encrypted_token, metadata)
            VALUES (%s, 'notion', %s, %s)
            ON CONFLICT (user_id, provider)
            DO UPDATE SET encrypted_token = EXCLUDED.encrypted_token,
                          metadata = EXCLUDED.metadata,
                          connected_at = CURRENT_TIMESTAMP
            """,
            (user_id, encrypted, json.dumps(metadata)),
        )
        cur.close()


def _handle_finalize_connection(handler_self, user_id: int):
    """Complete a pending Notion OAuth connection using the stashed pending cookie."""
    cookie_header = handler_self.headers.get("Cookie", "")
    encrypted_pending = _parse_cookie(cookie_header, "notion_pending_token")
    if not encrypted_pending:
        send_json(handler_self, 400, {"error": "No pending Notion connection"})
        return

    try:
        payload = json.loads(decrypt_api_key(encrypted_pending))
        access_token = payload["token"]
        metadata = payload["metadata"]
    except Exception:
        send_json(handler_self, 400, {"error": "Invalid or expired pending token"})
        return

    _upsert_notion_integration(user_id, access_token, metadata)

    clear_pending = "notion_pending_token=; HttpOnly; Max-Age=0; Path=/api/notion"
    handler_self.send_response(200)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Content-Type", "application/json")
    handler_self.send_header("Set-Cookie", clear_pending)
    handler_self.end_headers()
    handler_self.wfile.write(
        json.dumps(
            {
                "connected": True,
                "workspace_name": metadata.get("workspace_name"),
                "workspace_icon": metadata.get("workspace_icon"),
                "workspace_id": metadata.get("workspace_id"),
            }
        ).encode()
    )


def _redirect(handler_self, location: str):
    handler_self.send_response(302)
    for k, v in get_cors_headers().items():
        handler_self.send_header(k, v)
    handler_self.send_header("Location", location)
    handler_self.end_headers()


def _handle_status(handler_self, user_id: int):
    """Return Notion connection status for the user."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT metadata FROM user_integrations WHERE user_id = %s AND provider = 'notion'",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()

    if not row:
        send_json(handler_self, 200, {"connected": False})
        return

    meta = row["metadata"] or {}
    send_json(
        handler_self,
        200,
        {
            "connected": True,
            "workspace_name": meta.get("workspace_name"),
            "workspace_icon": meta.get("workspace_icon"),
            "workspace_id": meta.get("workspace_id"),
        },
    )


# ─── target picker ───────────────────────────────────────────────────────────


def _canonical_notion_id(item: dict) -> str:
    """
    Notion search can return linked-view blocks whose `id` is a view block ID
    rather than the underlying database's ID.  The canonical database ID is
    always the 32-hex-char suffix of the item's `url` field.
    Falls back to `item["id"]` if the URL is absent or unparseable.
    """
    url = item.get("url", "")
    m = re.search(r"([0-9a-f]{32})(?:[?#]|$)", url)
    if m:
        raw = m.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return item.get("id")


def _handle_search(handler_self, user_id: int, qs: dict):
    """Search Notion pages/databases."""
    token = _get_notion_token(user_id)
    if not token:
        send_json(handler_self, 403, {"error": "Notion not connected"})
        return

    query = _qs_get(qs, "q") or ""
    filter_type = _qs_get(qs, "filter_type")  # 'page' | 'database' | None

    body: dict = {"query": query, "page_size": 20}
    if filter_type in ("page", "database"):
        # Notion API v2026-03-11 renamed "database" filter value to "data_source"
        api_filter_value = "data_source" if filter_type == "database" else filter_type
        body["filter"] = {"value": api_filter_value, "property": "object"}

    data, err, err_detail = _notion_api(
        "POST", "/search", token, body=body, user_id=user_id
    )
    if err == "notion_token_revoked":
        send_json(handler_self, 401, {"error": "notion_token_revoked"})
        return
    if err:
        send_json(
            handler_self,
            502,
            {"error": "Notion search failed", "code": err, "detail": err_detail},
        )
        return

    results = []
    for item in (data or {}).get("results", []):
        obj_type = item.get("object")
        title = _extract_title(item)
        icon = _extract_icon(item)
        results.append(
            {
                "id": _canonical_notion_id(item),
                "title": title,
                "type": obj_type,
                "icon": icon,
            }
        )

    send_json(handler_self, 200, {"results": results})


def _extract_title(item: dict) -> str:
    """Extract plain-text title from a Notion page or database object."""
    obj_type = item.get("object")

    # Try top-level title array (standard for databases; also present on some pages)
    title_arr = item.get("title")
    if isinstance(title_arr, list) and title_arr:
        result = "".join(
            t.get("plain_text", "") for t in title_arr if isinstance(t, dict)
        )
        if result:
            return result

    # Try page-style: walk properties for a type="title" property
    # (used by pages and inline databases surfaced as page objects)
    props = item.get("properties", {})
    for prop in props.values():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "title":
            texts = prop.get("title", [])
            if isinstance(texts, list) and texts:
                result = "".join(
                    t.get("plain_text", "") for t in texts if isinstance(t, dict)
                )
                if result:
                    return result

    # Fallback for pages with no extractable title
    if obj_type == "page":
        return item.get("url", "")
    return ""


def _extract_icon(item: dict) -> str | None:
    icon = item.get("icon")
    if not icon:
        return None
    if icon.get("type") == "emoji":
        return icon.get("emoji")
    if icon.get("type") == "external":
        return icon.get("external", {}).get("url")
    return None


def _handle_set_target(handler_self, user_id: int, body: dict):
    """Upsert sticky export target."""
    course_id = body.get("course_id")
    generation_type = body.get("generation_type")
    target_id = body.get("target_id")
    target_title = body.get("target_title")
    target_type = body.get("target_type")

    if not all([course_id, generation_type, target_id]):
        send_json(
            handler_self,
            400,
            {"error": "course_id, generation_type, target_id required"},
        )
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO course_export_targets
                (user_id, course_id, provider, generation_type, external_target_id,
                 external_target_title, external_target_type, updated_at)
            VALUES (%s, %s, 'notion', %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, course_id, provider, generation_type)
            DO UPDATE SET external_target_id    = EXCLUDED.external_target_id,
                          external_target_title = EXCLUDED.external_target_title,
                          external_target_type  = EXCLUDED.external_target_type,
                          updated_at            = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (user_id, course_id, generation_type, target_id, target_title, target_type),
        )
        row = cur.fetchone()
        cur.close()

    send_json(handler_self, 200, {"target": dict(row) if row else None})


def _handle_get_target(handler_self, user_id: int, qs: dict):
    """Return existing sticky target for (user, course, generation_type) or {target: null}."""
    course_id = _qs_get(qs, "course_id")
    generation_type = _qs_get(qs, "generation_type")

    if not course_id or not generation_type:
        send_json(
            handler_self, 400, {"error": "course_id and generation_type required"}
        )
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT external_target_id AS id, external_target_title AS title,
                   external_target_type AS type
            FROM course_export_targets
            WHERE user_id = %s AND course_id = %s AND provider = 'notion'
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
    POST /api/notion?action=export
    Shape C: { exports: [{ generation_id, generation_type, targets: [{ provider, target_id }] }] }
    Always returns 207 Multi-Status.
    """
    exports = body.get("exports", [])
    if not isinstance(exports, list) or not exports:
        send_json(handler_self, 400, {"error": "exports array required"})
        return

    token = _get_notion_token(user_id)
    if not token:
        send_json(handler_self, 403, {"error": "Notion not connected"})
        return

    results = []
    for export_item in exports:
        generation_id = export_item.get("generation_id")
        generation_type = export_item.get("generation_type")
        targets = export_item.get("targets", [])

        for tgt in targets:
            provider = tgt.get("provider")
            target_id = tgt.get("target_id")

            if provider != "notion":
                results.append(
                    {
                        "generation_id": generation_id,
                        "generation_type": generation_type,
                        "provider": provider,
                        "target_id": target_id,
                        "status": "error",
                        "error": f"Unsupported provider: {provider}",
                    }
                )
                continue

            name = tgt.get("name", "").strip()
            result = _dispatch_export(
                user_id, generation_id, generation_type, target_id, token, name
            )
            result["generation_id"] = generation_id
            result["generation_type"] = generation_type
            result["provider"] = provider
            result["target_id"] = target_id
            results.append(result)

    succeeded = sum(1 for r in results if r.get("status") == "success")
    failed = len(results) - succeeded

    send_json(
        handler_self,
        207,
        {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        },
    )


def _dispatch_export(
    user_id: int,
    generation_id,
    generation_type: str,
    target_id: str,
    token: str,
    name: str = "",
) -> dict:
    """Route to the appropriate export handler. Returns a result entry dict."""
    if generation_type == "flashcards":
        return _export_flashcards(user_id, generation_id, target_id, token, name)
    elif generation_type == "quiz":
        return _export_quiz(user_id, generation_id, target_id, token, name)
    elif generation_type == "report":
        return _export_report(user_id, generation_id, target_id, token, name)
    else:
        return {
            "status": "error",
            "error": f"Unknown generation_type: {generation_type}",
        }


def _create_page_in_database(database_id: str, name: str, token: str, user_id: int):
    """Create a new page in a Notion database. Returns (page_id, page_url, error)."""
    db_data, db_err, _ = _notion_api(
        "GET", f"/databases/{database_id}", token, user_id=user_id
    )
    if db_err == "notion_token_revoked":
        return None, None, "notion_token_revoked"
    if db_err or not db_data:
        return None, None, db_err or "Failed to fetch database"

    ds_id = None
    ds_items = db_data.get("data_sources") or []
    if ds_items:
        ds_id = (ds_items[0] or {}).get("id")

    title_prop = None
    if ds_id:
        ds_data, ds_err, _ = _notion_api(
            "GET", f"/data_sources/{ds_id}", token, user_id=user_id
        )
        if ds_err == "notion_token_revoked":
            return None, None, "notion_token_revoked"
        if not ds_err and ds_data:
            title_prop = next(
                (
                    k
                    for k, v in (ds_data.get("properties") or {}).items()
                    if v.get("type") == "title"
                ),
                None,
            )

    # Legacy fallback for workspaces/databases without data_sources
    if not title_prop:
        title_prop = next(
            (
                k
                for k, v in (db_data.get("properties") or {}).items()
                if v.get("type") == "title"
            ),
            None,
        )

    if not title_prop:
        return None, None, "Database has no title property"

    parent = (
        {"type": "data_source_id", "data_source_id": ds_id}
        if ds_id
        else {"database_id": database_id}
    )

    payload = {
        "parent": parent,
        "properties": {
            title_prop: {
                "title": [{"type": "text", "text": {"content": name or "Untitled"}}]
            }
        },
    }
    page_data, page_err, _ = _notion_api(
        "POST", "/pages", token, body=payload, user_id=user_id
    )
    if page_err == "notion_token_revoked":
        return None, None, "notion_token_revoked"
    if page_err:
        return None, None, page_err

    page_id = page_data.get("id", "")
    page_url = (
        page_data.get("url") or f"https://www.notion.so/{page_id.replace('-', '')}"
    )
    return page_id, page_url, None


def _export_flashcards(
    user_id: int, generation_id, target_id: str, token: str, name: str = ""
) -> dict:
    """Export flashcards as toggle blocks appended to a Notion page."""
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
        return {
            "status": "error",
            "error": f"Generation not ready (status={row['status']})",
        }

    # Create a new page in the database
    page_id, page_url, create_err = _create_page_in_database(
        target_id, name, token, user_id
    )
    if create_err == "notion_token_revoked":
        return {"status": "error", "error": "notion_token_revoked"}
    if create_err:
        return {"status": "error", "error": f"Failed to create page: {create_err}"}

    cards = row["cards"] or []
    blocks = [flashcard_to_notion_toggle_block(c) for c in cards if c]

    if not blocks:
        return {"status": "success", "exported_count": 0, "url": page_url}

    # Append in batches of 100 (Notion API limit)
    for i in range(0, len(blocks), 100):
        batch = blocks[i : i + 100]
        data, err, err_detail = _notion_api(
            "PATCH",
            f"/blocks/{page_id}/children",
            token,
            body={"children": batch},
            user_id=user_id,
        )
        if err == "notion_token_revoked":
            return {"status": "error", "error": "notion_token_revoked"}
        if err:
            return {
                "status": "error",
                "error": f"Notion API error: {err}",
                "detail": err_detail,
            }

    return {"status": "success", "exported_count": len(cards), "url": page_url}


def _export_quiz(
    user_id: int, generation_id, target_id: str, token: str, name: str = ""
) -> dict:
    """Export quiz as heading/toggle blocks on a Notion page."""
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
        return {
            "status": "error",
            "error": f"Generation not ready (status={row['status']})",
        }

    # Create a new page in the database
    page_id, page_url, create_err = _create_page_in_database(
        target_id, name, token, user_id
    )
    if create_err == "notion_token_revoked":
        return {"status": "error", "error": "notion_token_revoked"}
    if create_err:
        return {"status": "error", "error": f"Failed to create page: {create_err}"}

    questions = row["questions"] or []
    blocks = quiz_to_notion_blocks(questions)

    if not blocks:
        return {"status": "success", "exported_count": 0, "url": page_url}

    for i in range(0, len(blocks), 100):
        batch = blocks[i : i + 100]
        data, err, err_detail = _notion_api(
            "PATCH",
            f"/blocks/{page_id}/children",
            token,
            body={"children": batch},
            user_id=user_id,
        )
        if err == "notion_token_revoked":
            return {"status": "error", "error": "notion_token_revoked"}
        if err:
            return {
                "status": "error",
                "error": f"Notion API error: {err}",
                "detail": err_detail,
            }

    return {"status": "success", "exported_count": len(questions), "url": page_url}


def _export_report(
    user_id: int, generation_id, target_id: str, token: str, name: str = ""
) -> dict:
    """Export report sections as Notion blocks on a page."""
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
        return {
            "status": "error",
            "error": f"Generation not ready (status={row['status']})",
        }

    # Use the report's generated title as the page name if the caller didn't supply one.
    page_name = name or str(row.get("title") or "").strip() or "Report"
    page_id, page_url, create_err = _create_page_in_database(
        target_id, page_name, token, user_id
    )
    if create_err == "notion_token_revoked":
        return {"status": "error", "error": "notion_token_revoked"}
    if create_err:
        return {"status": "error", "error": f"Failed to create page: {create_err}"}

    sections = row["sections_json"] or []
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except ValueError:
            sections = []

    blocks = report_to_notion_blocks(sections)

    if not blocks:
        return {"status": "success", "exported_count": 0, "url": page_url}

    for i in range(0, len(blocks), 100):
        batch = blocks[i : i + 100]
        data, err, err_detail = _notion_api(
            "PATCH",
            f"/blocks/{page_id}/children",
            token,
            body={"children": batch},
            user_id=user_id,
        )
        if err == "notion_token_revoked":
            return {"status": "error", "error": "notion_token_revoked"}
        if err:
            return {
                "status": "error",
                "error": f"Notion API error: {err}",
                "detail": err_detail,
            }

    return {"status": "success", "exported_count": len(sections), "url": page_url}


# ─── create target ───────────────────────────────────────────────────────────


def _handle_create_target(handler_self, user_id: int, body: dict):
    """
    POST /api/notion?action=create_target
    Creates a new Notion page under a parent page, upserts as sticky target.
    """
    target_type = body.get("type", "page")
    title = body.get("title", "").strip()
    parent_id = body.get("parent_id", "").strip()
    course_id = body.get("course_id")
    generation_type = body.get("generation_type")

    if not title:
        send_json(handler_self, 400, {"error": "title required"})
        return
    if not parent_id:
        send_json(handler_self, 400, {"error": "parent_id required"})
        return

    token = _get_notion_token(user_id)
    if not token:
        send_json(handler_self, 403, {"error": "Notion not connected"})
        return

    if target_type == "page":
        payload = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
        }
        data, err, err_detail = _notion_api(
            "POST", "/pages", token, body=payload, user_id=user_id
        )
    else:
        # Database — hardcoded flashcard schema
        payload = {
            "parent": {"page_id": parent_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": {
                "Front": {"title": {}},
                "Back": {"rich_text": {}},
                "Hint": {"rich_text": {}},
            },
        }
        data, err, err_detail = _notion_api(
            "POST", "/databases", token, body=payload, user_id=user_id
        )

    if err == "notion_token_revoked":
        send_json(handler_self, 401, {"error": "notion_token_revoked"})
        return
    if err:
        send_json(
            handler_self,
            502,
            {"error": f"Failed to create Notion {target_type}", "detail": err_detail},
        )
        return

    new_id = data.get("id", "")
    notion_url = data.get("url") or f"https://www.notion.so/{new_id.replace('-', '')}"
    new_title = _extract_title(data) or title

    # Upsert as sticky target if course context given
    if course_id and generation_type:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO course_export_targets
                    (user_id, course_id, provider, generation_type, external_target_id,
                     external_target_title, external_target_type, updated_at)
                VALUES (%s, %s, 'notion', %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, course_id, provider, generation_type)
                DO UPDATE SET external_target_id    = EXCLUDED.external_target_id,
                              external_target_title = EXCLUDED.external_target_title,
                              external_target_type  = EXCLUDED.external_target_type,
                              updated_at            = CURRENT_TIMESTAMP
                """,
                (user_id, course_id, generation_type, new_id, new_title, target_type),
            )
            cur.close()

    send_json(
        handler_self,
        200,
        {
            "id": new_id,
            "title": new_title,
            "type": target_type,
            "notion_url": notion_url,
        },
    )


# ─── revoke ──────────────────────────────────────────────────────────────────


def _handle_revoke(handler_self, user_id: int):
    """Delete Notion integration and all sticky targets for the user."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM user_integrations WHERE user_id = %s AND provider = 'notion' RETURNING id",
            (user_id,),
        )
        deleted = cur.fetchone()
        if deleted:
            cur.execute(
                "DELETE FROM course_export_targets WHERE user_id = %s AND provider = 'notion'",
                (user_id,),
            )
        cur.close()

    if not deleted:
        send_json(handler_self, 404, {"error": "Notion integration not found"})
        return

    send_json(handler_self, 200, {"disconnected": True})


# ─── source points ───────────────────────────────────────────────────────────


def _resolve_notion_database_id(raw_id: str, token: str) -> str | None:
    data, err, err_detail = _notion_api(
        "GET", f"/databases/{raw_id}", token, user_id=None
    )
    if not err:
        return data.get("id", raw_id)

    print(
        f"[notion] resolve({raw_id}): /databases/ failed ({err}: {err_detail}), trying /blocks/"
    )

    block, block_err, block_err_detail = _notion_api(
        "GET", f"/blocks/{raw_id}", token, user_id=None
    )
    if block_err:
        print(
            f"[notion] resolve({raw_id}): /blocks/ also failed ({block_err}: {block_err_detail}) — "
            f"ID is either invalid, not shared with this integration, or a linked database view "
            f"(which the public API cannot resolve)"
        )
        return None

    block_type = block.get("type")
    parent = block.get("parent", {})
    parent_type = parent.get("type")
    parent_id = parent.get(parent_type) if parent_type else None
    title_hint = (
        (block.get("child_database") or {}).get("title")
        or (block.get("child_page") or {}).get("title")
        or ""
    )
    title_str = f" title={title_hint!r}" if title_hint else ""

    if block_type == "child_database":
        print(
            f"[notion] resolve({raw_id}): block is a child_database{title_str} "
            f"(parent {parent_type}={parent_id}) — using block ID as database ID"
        )
        return raw_id

    print(
        f"[notion] resolve({raw_id}): block has type={block_type!r}{title_str} "
        f"(parent {parent_type}={parent_id}) — this is not a database and cannot be resolved. "
        f"If this is a linked database view, the public API cannot follow the link; "
        f"share the original source database with the integration instead."
    )
    return None


def _resolve_notion_data_source_id(raw_id: str, token: str) -> str | None:
    """Resolve input ID to a queryable Notion data_source ID."""
    data_source, ds_err, _ = _notion_api(
        "GET", f"/data_sources/{raw_id}", token, user_id=None
    )
    if not ds_err and data_source:
        return data_source.get("id", raw_id)

    database_id = _resolve_notion_database_id(raw_id, token)
    if not database_id:
        return None

    db_data, db_err, db_err_detail = _notion_api(
        "GET", f"/databases/{database_id}", token, user_id=None
    )
    if db_err or not db_data:
        print(
            f"[notion] resolve data source({raw_id}): /databases/{database_id} failed ({db_err}: {db_err_detail})"
        )
        return None

    ds_items = db_data.get("data_sources") or []
    if not ds_items:
        print(
            f"[notion] resolve data source({raw_id}): database {database_id} has no data_sources"
        )
        return None
    ds_id = (ds_items[0] or {}).get("id")
    if not ds_id:
        print(
            f"[notion] resolve data source({raw_id}): first data_source missing id for database {database_id}"
        )
        return None
    return ds_id


def _handle_add_source_point(handler_self, user_id: int, body: dict):
    """Insert a Notion database as a course source point."""
    token = _get_notion_token(user_id)
    if not token:
        send_json(handler_self, 403, {"error": "Notion not connected"})
        return

    course_id = body.get("course_id")
    external_id = body.get("external_id", "").strip()
    external_title = body.get("external_title", "").strip()
    metadata = body.get("metadata") or {}

    if not course_id or not external_id:
        send_json(handler_self, 400, {"error": "course_id and external_id required"})
        return

    resolved_id = _resolve_notion_data_source_id(external_id, token)
    if not resolved_id:
        send_json(
            handler_self,
            400,
            {
                "error": "Could not resolve a queryable Notion data source from the provided ID. Make sure you are selecting a database or data source shared with this integration."
            },
        )
        return
    external_id = resolved_id

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO integration_source_points
                    (user_id, course_id, provider, external_id, external_title, metadata)
                VALUES (%s, %s, 'notion', %s, %s, %s)
                RETURNING *
                """,
                (
                    user_id,
                    course_id,
                    external_id,
                    external_title or None,
                    json.dumps(metadata),
                ),
            )
            row = cur.fetchone()
        except Exception as exc:
            if "unique" in str(exc).lower():
                send_json(handler_self, 409, {"error": "Source point already exists"})
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
                Payload=json.dumps(
                    {
                        "source_point_id": int(row["id"]),
                        "user_id": user_id,
                        "course_id": int(course_id),
                        "force_full_sync": True,
                    }
                ).encode(),
            )
            sync_triggered = True
            print(
                f"[notion add_source_point] initial sync invoked "
                f"source_point_id={row['id']} course_id={course_id} user_id={user_id}"
            )
        except Exception as exc:
            sync_error = str(exc)
            print(
                f"[notion add_source_point] initial sync invoke failed "
                f"source_point_id={row['id']} course_id={course_id} user_id={user_id}: {exc}"
            )
    elif not _INTEGRATION_POLLER_ARN:
        sync_error = "INTEGRATION_POLLER_LAMBDA_ARN not configured"
        print(
            f"[notion add_source_point] initial sync skipped: "
            f"missing INTEGRATION_POLLER_LAMBDA_ARN source_point_id={row['id'] if row else None}"
        )

    send_json(
        handler_self,
        201,
        {
            "source_point": dict(row) if row else None,
            "sync_triggered": sync_triggered,
            "sync_error": sync_error,
        },
    )


def _handle_resolve_database_target(handler_self, user_id: int, body: dict):
    """
    Resolve and normalize a Notion database ID using the exact same resolver
    as add_source_point, but without writing to integration_source_points.
    """
    token = _get_notion_token(user_id)
    if not token:
        send_json(handler_self, 403, {"error": "Notion not connected"})
        return

    external_id = body.get("external_id", "").strip()
    external_title = body.get("external_title", "").strip()
    if not external_id:
        send_json(handler_self, 400, {"error": "external_id required"})
        return

    resolved_id = _resolve_notion_database_id(external_id, token)
    if not resolved_id:
        send_json(
            handler_self,
            400,
            {
                "error": "Could not resolve a queryable Notion database from the provided ID. Make sure you are selecting a database (not a linked view or page)."
            },
        )
        return

    # Optional title backfill from resolved database
    db_data, db_err, _ = _notion_api(
        "GET", f"/databases/{resolved_id}", token, user_id=user_id
    )
    resolved_title = external_title or _extract_title(db_data or {}) or "Untitled"
    if db_err:
        resolved_title = external_title or "Untitled"

    send_json(
        handler_self,
        200,
        {
            "target": {
                "id": resolved_id,
                "title": resolved_title,
                "type": "database",
            }
        },
    )


def _handle_list_source_points(handler_self, user_id: int, qs: dict):
    """List all source points for the user in a course (active and disabled)."""
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
            WHERE user_id = %s AND course_id = %s AND provider = 'notion'
            ORDER BY created_at DESC
            """,
            (user_id, course_id),
        )
        rows = cur.fetchall()
        cur.close()

    send_json(handler_self, 200, {"source_points": [dict(r) for r in rows]})


_SOURCE_POINT_FILES_PAGE_SIZE = 20


def _handle_list_source_point_files(handler_self, user_id: int, qs: dict):
    """List pages in a Notion data source source point, cross-referenced with materials sync state.
    Paginated at 20 files per page (?page=1 by default)."""
    token = _get_notion_token(user_id)
    if not token:
        send_json(handler_self, 403, {"error": "Notion not connected"})
        return

    sp_id = _qs_get(qs, "id")
    if not sp_id:
        send_json(handler_self, 400, {"error": "id required"})
        return

    page = int(_qs_get(qs, "page") or 1)
    if page < 1:
        page = 1

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, external_id, course_id FROM integration_source_points WHERE id = %s AND user_id = %s AND provider = 'notion'",
            (sp_id, user_id),
        )
        sp = cur.fetchone()
        cur.close()

    if not sp:
        send_json(handler_self, 404, {"error": "Source point not found"})
        return

    data_source_id = sp["external_id"]
    course_id = sp["course_id"]
    page_size = _SOURCE_POINT_FILES_PAGE_SIZE
    target_count = page * page_size

    # Collect enough pages from Notion to satisfy the requested page
    all_pages = []
    cursor = None
    while len(all_pages) < target_count:
        body = {"page_size": min(100, target_count - len(all_pages))}
        if cursor:
            body["start_cursor"] = cursor
        data, err, _ = _notion_api(
            "POST", f"/data_sources/{data_source_id}/query", token, body=body, user_id=user_id
        )
        if err:
            send_json(handler_self, 502, {"error": "Notion API error", "code": err})
            return
        all_pages.extend((data or {}).get("results", []))
        has_more_notion = (data or {}).get("has_more", False)
        cursor = (data or {}).get("next_cursor")
        if not has_more_notion:
            break

    has_more = has_more_notion if len(all_pages) >= target_count else False
    page_items = all_pages[(page - 1) * page_size : page * page_size]

    if not page_items:
        send_json(handler_self, 200, {"files": [], "page": page, "has_more": False})
        return

    # Extract page ID and title from Notion page objects
    def _page_title(notion_page: dict) -> str:
        props = notion_page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                parts = prop.get("title", [])
                return "".join(p.get("plain_text", "") for p in parts)
        return notion_page.get("id", "Untitled")

    external_ids = [p["id"] for p in page_items]

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT external_id, sync, doc_type FROM materials WHERE external_id = ANY(%s) AND course_id = %s AND source_type = 'notion'",
            (external_ids, course_id),
        )
        sync_rows = {r["external_id"]: {"sync": r["sync"], "doc_type": r["doc_type"]} for r in cur.fetchall()}
        cur.close()

    files_out = [
        {
            "external_id": p["id"],
            "name": _page_title(p),
            "mime_type": "notion/page",
            "sync": sync_rows.get(p["id"], {}).get("sync"),
            "doc_type": sync_rows.get(p["id"], {}).get("doc_type"),
        }
        for p in page_items
    ]

    send_json(
        handler_self, 200, {"files": files_out, "page": page, "has_more": has_more}
    )


def _handle_toggle_source_point(
    handler_self, user_id: int, qs: dict, body: dict | None = None
):
    """Flip is_active for a source point owned by the user."""
    sp_id = _source_point_id_from_qs_or_body(qs, body)
    if not sp_id:
        send_json(handler_self, 400, {"error": "id required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE integration_source_points
            SET is_active = NOT is_active
            WHERE id = %s AND user_id = %s AND provider = 'notion'
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


def _handle_remove_source_point(
    handler_self, user_id: int, qs: dict, body: dict | None = None
):
    """Permanently delete a source point owned by the user."""
    sp_id = _source_point_id_from_qs_or_body(qs, body)
    if not sp_id:
        send_json(handler_self, 400, {"error": "id required"})
        return

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM integration_source_points WHERE id = %s AND user_id = %s AND provider = 'notion' RETURNING id",
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
    """
    POST /api/notion?action=sync
    Invoke integration_poller Lambda for the user's active source points in the course.
    """
    course_id = (
        body.get("course_id")
        or _parse_qs_from_path(handler_self).get("course_id", [None])[0]
    )
    if not course_id:
        send_json(handler_self, 400, {"error": "course_id required"})
        return

    if not _INTEGRATION_POLLER_ARN:
        send_json(
            handler_self, 202, {"message": "Sync accepted (Lambda not configured)"}
        )
        return

    try:
        import boto3

        lmbd = boto3.client("lambda", region_name=_AWS_REGION)
        lmbd.invoke(
            FunctionName=_INTEGRATION_POLLER_ARN,
            InvocationType="Event",
            Payload=json.dumps(
                {"user_id": user_id, "course_id": int(course_id)}
            ).encode(),
        )
    except Exception as e:
        import traceback

        print(
            f"[notion sync] Lambda invoke failed: {e}\n{traceback.format_exc()}"
        )  # visible in Vercel logs

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

        # All other GET actions require authentication
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
        elif action == "list_source_point_files":
            _handle_list_source_point_files(self, user_id, qs)
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
        elif action == "create_target":
            _handle_create_target(self, user_id, body)
        elif action == "add_source_point":
            _handle_add_source_point(self, user_id, body)
        elif action == "resolve_database_target":
            _handle_resolve_database_target(self, user_id, body)
        elif action == "sync":
            _handle_sync(self, user_id, body)
        else:
            send_json(self, 400, {"error": f"Unknown POST action: {action}"})

    def do_DELETE(self):
        qs = _parse_qs_from_path(self)
        action = _qs_get(qs, "action")

        # Try body for action too
        body, _ = _read_body(self)
        if not action and body:
            action = body.get("action")

        user_id, err = _get_user_from_request(self)
        if err:
            return

        if action == "revoke":
            _handle_revoke(self, user_id)
        elif action == "remove_source_point":
            _handle_remove_source_point(self, user_id, qs, body)
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
            _handle_toggle_source_point(self, user_id, qs, body)
        else:
            send_json(self, 400, {"error": f"Unknown PATCH action: {action}"})

    def log_message(self, format, *args):  # noqa: A002
        pass  # suppress default access log noise
