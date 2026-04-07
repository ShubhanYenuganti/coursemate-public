# Vercel Python Serverless Function — Notion Integration
# GET    /api/notion?action=auth               → initiate OAuth flow
# GET    /api/notion?action=callback           → handle OAuth callback
# GET    /api/notion?action=status             → connection status
# GET    /api/notion?action=search             → search pages/databases
# GET    /api/notion?action=get_target         → get sticky export target
# GET    /api/notion?action=list_source_points → list course source points
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
import secrets
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
    os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
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
    Returns (response_dict_or_None, error_code_or_None).
    error_code is 'notion_token_revoked' if the token has been revoked.
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
        # Token revoked externally — clean up stored credentials
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
        return None, "notion_token_revoked"

    if not resp.ok:
        return None, f"notion_api_error:{resp.status_code}"

    try:
        return resp.json(), None
    except ValueError:
        return {}, None


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
    handler_self.wfile.write(json.dumps({
        "connected": True,
        "workspace_name": metadata.get("workspace_name"),
        "workspace_icon": metadata.get("workspace_icon"),
        "workspace_id": metadata.get("workspace_id"),
    }).encode())


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
        body["filter"] = {"value": filter_type, "property": "object"}

    data, err = _notion_api("POST", "/search", token, body=body, user_id=user_id)
    if err == "notion_token_revoked":
        send_json(handler_self, 401, {"error": "notion_token_revoked"})
        return
    if err:
        send_json(handler_self, 502, {"error": "Notion search failed"})
        return

    results = []
    for item in (data or {}).get("results", []):
        obj_type = item.get("object")
        title = _extract_title(item)
        icon = _extract_icon(item)
        results.append(
            {
                "id": item.get("id"),
                "title": title,
                "type": obj_type,
                "icon": icon,
            }
        )

    send_json(handler_self, 200, {"results": results})


def _extract_title(item: dict) -> str:
    """Extract plain-text title from a Notion page or database object."""
    obj_type = item.get("object")
    if obj_type == "page":
        props = item.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                texts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in texts)
        # fallback for pages without a title property
        return item.get("url", "")
    elif obj_type == "database":
        title_arr = item.get("title", [])
        return "".join(t.get("plain_text", "") for t in title_arr)
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

            result = _dispatch_export(
                user_id, generation_id, generation_type, target_id, token
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
    user_id: int, generation_id, generation_type: str, target_id: str, token: str
) -> dict:
    """Route to the appropriate export handler. Returns a result entry dict."""
    if generation_type == "flashcards":
        return _export_flashcards(user_id, generation_id, target_id, token)
    elif generation_type == "quiz":
        return _export_quiz(user_id, generation_id, target_id, token)
    elif generation_type == "report":
        return _export_report(user_id, generation_id, target_id, token)
    else:
        return {
            "status": "error",
            "error": f"Unknown generation_type: {generation_type}",
        }


def _export_flashcards(user_id: int, generation_id, target_id: str, token: str) -> dict:
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

    # Verify target is a Notion page (not a database)
    page_data, page_err = _notion_api("GET", f"/pages/{target_id}", token, user_id=user_id)
    if page_err == "notion_token_revoked":
        return {"status": "error", "error": "notion_token_revoked"}
    if page_err or not page_data:
        return {"status": "error", "error": "Flashcard export requires a Notion page target, not a database"}

    cards = row["cards"] or []
    blocks = [flashcard_to_notion_toggle_block(c) for c in cards if c]

    if not blocks:
        return {
            "status": "success",
            "exported_count": 0,
            "url": f"https://www.notion.so/{target_id.replace('-', '')}",
        }

    # Append in batches of 100 (Notion API limit)
    for i in range(0, max(len(blocks), 1), 100):
        batch = blocks[i : i + 100]
        data, err = _notion_api(
            "PATCH",
            f"/blocks/{target_id}/children",
            token,
            body={"children": batch},
            user_id=user_id,
        )
        if err == "notion_token_revoked":
            return {"status": "error", "error": "notion_token_revoked"}
        if err:
            return {"status": "error", "error": f"Notion API error: {err}"}

    notion_url = f"https://www.notion.so/{target_id.replace('-', '')}"
    return {"status": "success", "exported_count": len(cards), "url": notion_url}


def _export_quiz(user_id: int, generation_id, target_id: str, token: str) -> dict:
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

    # Verify target is a Notion page (not a database)
    page_data, page_err = _notion_api("GET", f"/pages/{target_id}", token, user_id=user_id)
    if page_err == "notion_token_revoked":
        return {"status": "error", "error": "notion_token_revoked"}
    if page_err or not page_data:
        return {"status": "error", "error": "Quiz export requires a Notion page target, not a database"}

    questions = row["questions"] or []
    blocks = quiz_to_notion_blocks(questions)

    if not blocks:
        return {
            "status": "success",
            "exported_count": 0,
            "url": f"https://www.notion.so/{target_id.replace('-', '')}",
        }

    for i in range(0, max(len(blocks), 1), 100):
        batch = blocks[i : i + 100]
        data, err = _notion_api(
            "PATCH",
            f"/blocks/{target_id}/children",
            token,
            body={"children": batch},
            user_id=user_id,
        )
        if err == "notion_token_revoked":
            return {"status": "error", "error": "notion_token_revoked"}
        if err:
            return {"status": "error", "error": f"Notion API error: {err}"}

    notion_url = f"https://www.notion.so/{target_id.replace('-', '')}"
    return {"status": "success", "exported_count": len(questions), "url": notion_url}


def _export_report(user_id: int, generation_id, target_id: str, token: str) -> dict:
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

    # Verify target is a Notion page (not a database)
    page_data, page_err = _notion_api("GET", f"/pages/{target_id}", token, user_id=user_id)
    if page_err == "notion_token_revoked":
        return {"status": "error", "error": "notion_token_revoked"}
    if page_err or not page_data:
        return {"status": "error", "error": "Report export requires a Notion page target, not a database"}

    sections = row["sections_json"] or []
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except ValueError:
            sections = []

    blocks = report_to_notion_blocks(sections)

    if not blocks:
        return {
            "status": "success",
            "exported_count": 0,
            "url": f"https://www.notion.so/{target_id.replace('-', '')}",
        }

    for i in range(0, max(len(blocks), 1), 100):
        batch = blocks[i : i + 100]
        data, err = _notion_api(
            "PATCH",
            f"/blocks/{target_id}/children",
            token,
            body={"children": batch},
            user_id=user_id,
        )
        if err == "notion_token_revoked":
            return {"status": "error", "error": "notion_token_revoked"}
        if err:
            return {"status": "error", "error": f"Notion API error: {err}"}

    notion_url = f"https://www.notion.so/{target_id.replace('-', '')}"
    return {"status": "success", "exported_count": len(sections), "url": notion_url}


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
        data, err = _notion_api("POST", "/pages", token, body=payload, user_id=user_id)
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
        data, err = _notion_api(
            "POST", "/databases", token, body=payload, user_id=user_id
        )

    if err == "notion_token_revoked":
        send_json(handler_self, 401, {"error": "notion_token_revoked"})
        return
    if err:
        send_json(
            handler_self, 502, {"error": f"Failed to create Notion {target_type}"}
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

    send_json(handler_self, 201, {"source_point": dict(row) if row else None})


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


def _handle_toggle_source_point(handler_self, user_id: int, qs: dict):
    """Flip is_active for a source point owned by the user."""
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


def _handle_remove_source_point(handler_self, user_id: int, qs: dict):
    """Permanently delete a source point owned by the user."""
    sp_id = _qs_get(qs, "id")
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
    except Exception:
        pass  # Fire-and-forget — always return 202

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
