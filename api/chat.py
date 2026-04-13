# Vercel Python Serverless Function — Chat
# GET    /api/chat?resource=chat&course_id=<id>              → list chats
# GET    /api/chat?resource=chat&course_id=<id>&q=<query>    → search chat titles
# GET    /api/chat?resource=message&chat_id=<id>             → list messages
# GET    /api/chat?resource=message&chat_id=<id>&q=<query>   → search within chat
# GET    /api/chat?resource=message&course_id=<id>&q=<query> → search across course
# POST   /api/chat  resource="chat"    action="create"       → create chat
# POST   /api/chat  resource="chat"    action="update"       → rename chat
# POST   /api/chat  resource="chat"    action="archive"      → archive/unarchive chat
# POST   /api/chat  resource="message" action="send"         → send message + AI reply
# POST   /api/chat  resource="message" action="edit"         → edit message + regenerate reply
# POST   /api/chat  resource="message" action="delete"       → soft-delete message
# DELETE /api/chat  resource="chat"                          → hard-delete chat

import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

try:
    from .middleware import send_json, send_sse_headers, send_sse_event, handle_options, authenticate_request, sanitize_string, check_rate_limit
    from .models import User
    from .courses import Course
    from .db import get_db
    from .rag import retrieve_chunks
    from .llm import synthesize
    from services.query.retrieval import _fetch_chunk_context
except ImportError:
    from middleware import send_json, send_sse_headers, send_sse_event, handle_options, authenticate_request, sanitize_string, check_rate_limit
    from models import User
    from courses import Course
    from db import get_db
    from rag import retrieve_chunks
    from llm import synthesize
    from services.query.retrieval import _fetch_chunk_context

try:
    from services.query.persistence import embed_text_via_lambda, write_chat_message_embedding
except ImportError:
    embed_text_via_lambda = None
    write_chat_message_embedding = None


logger = logging.getLogger(__name__)
DEFAULT_AI_PROVIDER = "openai"
DEFAULT_AI_MODEL = "gpt-4o-mini"


# ------------------------------------------------------------------ helpers --

def _get_chat(conn, chat_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE id = %s", (chat_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def _next_message_index(conn, chat_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(MAX(message_index) + 1, 0) AS next_idx FROM chat_messages WHERE chat_id = %s",
        (chat_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    return row['next_idx']


def _should_suggest_title(user_msg_index: int) -> bool:
    """Fire on exchange 1, then every 4th exchange: 1, 5, 9, 13, …"""
    exchange = (user_msg_index // 2) + 1
    return exchange == 1 or (exchange - 1) % 4 == 0


def _maybe_suggest_title(conn, chat, user_id: int, user_msg_index: int):
    """
    If auto-titling is active and cadence fires, call GPT-4o-mini for a title suggestion,
    persist it to the DB, and return the new title. Returns None otherwise.
    """
    if not chat.get("title_auto", True):
        return None
    if not _should_suggest_title(user_msg_index):
        return None

    try:
        from .llm import suggest_chat_title
    except ImportError:
        from llm import suggest_chat_title

    suggested = suggest_chat_title(
        conn=conn,
        user_id=user_id,
        chat_id=chat["id"],
        current_title=chat.get("title") or "New Chat",
    )
    if not suggested:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chats SET title = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (suggested, chat["id"]),
        )
        cursor.close()
    except Exception:
        logger.exception("auto_title_update_failed", extra={"chat_id": chat["id"]})
        return None

    return suggested


def _parse_reply_history(raw):
    """Return (back_list, forward_list) from a reply_history value.

    Supports v1 (plain array) and v2 ({back, forward}) formats.
    v1 entries lack 'user_query'; reverting them won't change the user message content.
    """
    if raw is None:
        return [], []
    if isinstance(raw, list):   # v1 compat
        return raw, []
    if isinstance(raw, dict):
        return raw.get('back', []), raw.get('forward', [])
    return [], []


def _build_reply_history(back, forward):
    return json.dumps({'back': back, 'forward': forward})


def _parse_body(handler):
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length).decode('utf-8')
        return json.loads(body) if body else {}, None
    except ValueError:
        return None, "Invalid request body"


def _is_enabled(env_name: str, default: bool = False) -> bool:
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _is_agentic_request(ai_provider: str, ai_model: str) -> bool:
    _ = (ai_provider, ai_model)  # kept for backward-compatible call sites
    return _is_enabled("AGENTIC_LOOP_ENABLED", default=False)


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

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        resource = params.get('resource', ['chat'])[0]
        q = params.get('q', [None])[0]

        if resource == 'chat':
            self._list_or_search_chats(user, params, q)
        elif resource == 'message':
            self._list_or_search_messages(user, params, q)
        elif resource == 'chunks':
            self._get_message_chunks(user, params)
        elif resource == 'pin':
            self._list_pins(user, params)
        else:
            send_json(self, 400, {"error": f"Unknown resource '{resource}'"})

    # ----------------------------------------------------------------- POST --
    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        data, err = _parse_body(self)
        if err:
            send_json(self, 400, {"error": err})
            return

        resource = data.get('resource', 'chat')
        action = data.get('action')

        if resource == 'chat':
            if action == 'create':
                self._create_chat(user, data)
            elif action == 'update':
                self._update_chat(user, data)
            elif action == 'archive':
                self._archive_chat(user, data)
            elif action == 'archive_all':
                self._archive_all_chats(user, data)
            else:
                send_json(self, 400, {"error": f"Unknown action '{action}' for resource 'chat'"})
        elif resource == 'pin':
            if action == 'pin':
                self._pin_message(user, data)
            elif action == 'unpin':
                self._unpin_message(user, data)
            else:
                send_json(self, 400, {"error": f"Unknown action '{action}' for resource 'pin'"})
        elif resource == 'message':
            if action == 'send':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._send_message(user, data)
            elif action == 'stream_send':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._stream_send_message(user, data)
            elif action == 'edit':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._edit_message(user, data)
            elif action == 'stream_edit':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._stream_edit_message(user, data)
            elif action == 'revert':
                self._revert_message(user, data)
            elif action == 'restore':
                self._restore_message(user, data)
            elif action == 'regenerate':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._regenerate_message(user, data)
            elif action == 'stream_regenerate':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._stream_regenerate_message(user, data)
            elif action == 'delete':
                self._delete_message(user, data)
            else:
                send_json(self, 400, {"error": f"Unknown action '{action}' for resource 'message'"})
        else:
            send_json(self, 400, {"error": f"Unknown resource '{resource}'"})

    # --------------------------------------------------------------- DELETE --
    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        data, err = _parse_body(self)
        if err:
            send_json(self, 400, {"error": err})
            return

        resource = data.get('resource', 'chat')
        if resource == 'chat':
            self._delete_chat(user, data)
        elif resource == 'pin':
            self._unpin_message(user, data)
        else:
            send_json(self, 400, {"error": f"Unknown resource '{resource}'"})

    # ----------------------------------------------------------- GET helpers --

    def _list_or_search_chats(self, user, params, q):
        course_id_raw = params.get('course_id', [None])[0]
        if not course_id_raw or not course_id_raw.isdigit():
            send_json(self, 400, {"error": "course_id query parameter is required"})
            return
        course_id = int(course_id_raw)

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        show_archived = params.get('archived', ['false'])[0].lower() == 'true'

        with get_db() as conn:
            cursor = conn.cursor()
            if q:
                cursor.execute("""
                    SELECT id, title, course_id, message_count, last_message_at, created_at, is_archived,
                           ts_rank(to_tsvector('english', title), plainto_tsquery('english', %s)) AS rank
                    FROM chats
                    WHERE course_id = %s
                      AND user_id = %s
                      AND is_archived = %s
                      AND to_tsvector('english', title) @@ plainto_tsquery('english', %s)
                    ORDER BY rank DESC, updated_at DESC
                """, (q, course_id, user['id'], show_archived, q))
            else:
                cursor.execute("""
                    SELECT id, title, course_id, message_count, last_message_at, created_at, is_archived
                    FROM chats
                    WHERE course_id = %s
                      AND user_id = %s
                      AND is_archived = %s
                    ORDER BY last_message_at DESC NULLS LAST, created_at DESC
                """, (course_id, user['id'], show_archived))
            chats = cursor.fetchall()
            cursor.close()

        send_json(self, 200, {"chats": chats})

    def _list_or_search_messages(self, user, params, q):
        chat_id_raw = params.get('chat_id', [None])[0]
        course_id_raw = params.get('course_id', [None])[0]

        # Search across a course
        if q and course_id_raw and not chat_id_raw:
            if not course_id_raw.isdigit():
                send_json(self, 400, {"error": "course_id must be an integer"})
                return
            course_id = int(course_id_raw)
            if not Course.verify_access(course_id, user['id']):
                send_json(self, 403, {"error": "Access denied to this course"})
                return

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cm.id, cm.chat_id, c.title AS chat_title,
                           cm.role, cm.content, cm.created_at,
                           ts_rank(to_tsvector('english', cm.content), plainto_tsquery('english', %s)) AS rank
                    FROM chat_messages cm
                    JOIN chats c ON c.id = cm.chat_id
                    WHERE cm.course_id = %s
                      AND cm.user_id = %s
                      AND cm.is_deleted = FALSE
                      AND to_tsvector('english', cm.content) @@ plainto_tsquery('english', %s)
                    ORDER BY rank DESC, cm.created_at DESC
                    LIMIT 50
                """, (q, course_id, user['id'], q))
                results = cursor.fetchall()
                cursor.close()
            send_json(self, 200, {"results": results})
            return

        # Require chat_id for all other message queries
        if not chat_id_raw or not chat_id_raw.isdigit():
            send_json(self, 400, {"error": "chat_id query parameter is required"})
            return
        chat_id = int(chat_id_raw)

        with get_db() as conn:
            chat = _get_chat(conn, chat_id)
            if not chat:
                send_json(self, 404, {"error": "Chat not found"})
                return
            if chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied to this chat"})
                return

            cursor = conn.cursor()
            if q:
                cursor.execute("""
                    SELECT id, role, content, is_edited, reply_history, message_index, created_at,
                           ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) AS rank
                    FROM chat_messages
                    WHERE chat_id = %s
                      AND is_deleted = FALSE
                      AND to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                    ORDER BY rank DESC, message_index
                """, (q, chat_id, q))
                results = cursor.fetchall()
                cursor.close()
                send_json(self, 200, {"results": results})
            else:
                limit_raw = params.get('limit', ['100'])[0]
                before_raw = params.get('before_index', [None])[0]
                limit = min(int(limit_raw) if limit_raw.isdigit() else 100, 200)

                if before_raw and before_raw.isdigit():
                    cursor.execute("""
                        SELECT id, chat_id, role, content, summary, ai_provider, ai_model,
                               context_material_ids, retrieved_chunk_ids, context_token_count,
                               response_token_count, response_time_ms, finish_reason, grounding_meta,
                               is_edited, reply_history, edited_at, message_index, created_at, tool_trace
                        FROM chat_messages
                        WHERE chat_id = %s
                          AND is_deleted = FALSE
                          AND message_index < %s
                        ORDER BY message_index DESC
                        LIMIT %s
                    """, (chat_id, int(before_raw), limit))
                else:
                    cursor.execute("""
                        SELECT id, chat_id, role, content, summary, ai_provider, ai_model,
                               context_material_ids, retrieved_chunk_ids, context_token_count,
                               response_token_count, response_time_ms, finish_reason, grounding_meta,
                               is_edited, reply_history, edited_at, message_index, created_at, tool_trace
                        FROM chat_messages
                        WHERE chat_id = %s
                          AND is_deleted = FALSE
                        ORDER BY message_index ASC
                        LIMIT %s
                    """, (chat_id, limit))
                messages = cursor.fetchall()
                cursor.close()
                send_json(self, 200, {"messages": messages})

    def _get_message_chunks(self, user, params):
        message_id_raw = params.get('message_id', [None])[0]
        if not message_id_raw or not message_id_raw.isdigit():
            send_json(self, 400, {"error": "message_id query parameter is required"})
            return
        message_id = int(message_id_raw)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cm.retrieved_chunk_ids, c.user_id
                FROM chat_messages cm
                JOIN chats c ON c.id = cm.chat_id
                WHERE cm.id = %s AND cm.is_deleted = FALSE
            """, (message_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                send_json(self, 404, {"error": "Message not found"})
                return
            if row['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied"})
                return

            chunk_ids = row['retrieved_chunk_ids'] or []
            if not chunk_ids:
                send_json(self, 200, {"chunks": []})
                return

            raw_chunks = _fetch_chunk_context(conn, chunk_ids)

        chunk_map = {str(c['id']): c for c in raw_chunks}
        ordered = [chunk_map[str(cid)] for cid in chunk_ids if str(cid) in chunk_map]
        serialized = [
            {
                "chunk_text":  c.get("chunk_text", ""),
                "chunk_type":  c.get("chunk_type", ""),
                "page_number": c.get("page_number"),
                "similarity":  None,
                "source_type": c.get("source_type", ""),
                "material_id": c.get("material_id"),
            }
            for c in ordered
        ]
        send_json(self, 200, {"chunks": serialized})

    # ---------------------------------------------------------- POST helpers --

    def _create_chat(self, user, data):
        course_id = data.get('course_id')
        title = sanitize_string(data.get('title', '') or '', max_length=500)

        if not isinstance(course_id, int):
            send_json(self, 400, {"error": "course_id is required"})
            return
        if not title:
            send_json(self, 400, {"error": "title is required"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chats (course_id, user_id, title)
                VALUES (%s, %s, %s)
                RETURNING id, course_id, user_id, title, visibility, message_count,
                          last_message_at, created_at, updated_at, is_archived, session_uuid
            """, (course_id, user['id'], title))
            chat = cursor.fetchone()
            cursor.close()

        send_json(self, 201, {"chat": chat})

    def _update_chat(self, user, data):
        chat_id = data.get('chat_id')
        title = sanitize_string(data.get('title', '') or '', max_length=500)

        if not isinstance(chat_id, int):
            send_json(self, 400, {"error": "chat_id is required"})
            return
        if not title:
            send_json(self, 400, {"error": "title is required"})
            return

        with get_db() as conn:
            chat = _get_chat(conn, chat_id)
            if not chat:
                send_json(self, 404, {"error": "Chat not found"})
                return
            if chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Only the chat owner can rename it"})
                return

            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chats SET title = %s, title_auto = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, course_id, user_id, title, title_auto, visibility, message_count,
                          last_message_at, created_at, updated_at, is_archived
            """, (title, chat_id))
            updated = cursor.fetchone()
            cursor.close()

        send_json(self, 200, {"chat": updated})

    def _archive_chat(self, user, data):
        chat_id = data.get('chat_id')
        is_archived = data.get('is_archived')

        if not isinstance(chat_id, int):
            send_json(self, 400, {"error": "chat_id is required"})
            return
        if not isinstance(is_archived, bool):
            send_json(self, 400, {"error": "is_archived (boolean) is required"})
            return

        with get_db() as conn:
            chat = _get_chat(conn, chat_id)
            if not chat:
                send_json(self, 404, {"error": "Chat not found"})
                return
            if chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Only the chat owner can archive it"})
                return

            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chats SET is_archived = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, course_id, user_id, title, visibility, message_count,
                          last_message_at, created_at, updated_at, is_archived
            """, (is_archived, chat_id))
            updated = cursor.fetchone()
            cursor.close()

        send_json(self, 200, {"chat": updated})

    def _archive_all_chats(self, user, data):
        course_id = data.get('course_id')
        if not isinstance(course_id, int):
            send_json(self, 400, {"error": "course_id is required"})
            return

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chats SET is_archived = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE course_id = %s AND user_id = %s AND is_archived = FALSE
            """, (course_id, user['id']))
            cursor.close()

        send_json(self, 200, {"success": True})

    def _send_message(self, user, data):
        chat_id = data.get('chat_id')
        content = sanitize_string(data.get('content', '') or '', max_length=10000)
        context_material_ids = data.get('context_material_ids') or []
        ai_provider = data.get('ai_provider') or DEFAULT_AI_PROVIDER
        ai_model = data.get('ai_model')
        if ai_provider == "openai" and not ai_model:
            ai_model = DEFAULT_AI_MODEL
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens')

        if not isinstance(chat_id, int):
            send_json(self, 400, {"error": "chat_id is required"})
            return
        if not content:
            send_json(self, 400, {"error": "content is required"})
            return
        if ai_provider not in ('gemini', 'openai', 'claude'):
            send_json(self, 400, {"error": "ai_provider must be one of: gemini, openai, claude"})
            return
        if not ai_model:
            send_json(self, 400, {"error": "ai_model is required"})
            return
        if not isinstance(context_material_ids, list):
            send_json(self, 400, {"error": "context_material_ids must be a list"})
            return

        metrics = {
            "chat_send": 1,
            "embedding_success": 0,
            "embedding_null": 0,
            "embedding_errors": 0,
        }

        with get_db() as conn:
            chat = _get_chat(conn, chat_id)
            if not chat:
                send_json(self, 404, {"error": "Chat not found"})
                return
            if chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied to this chat"})
                return

            # Validate material IDs belong to the chat's course
            if context_material_ids:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM materials
                    WHERE id = ANY(%s::int[])
                      AND course_id = %s
                """, (context_material_ids, chat['course_id']))
                valid_ids = {row['id'] for row in cursor.fetchall()}
                cursor.close()
                invalid = [mid for mid in context_material_ids if mid not in valid_ids]
                if invalid:
                    send_json(self, 400, {"error": f"Invalid material IDs for this course: {invalid}"})
                    return

            next_idx = _next_message_index(conn, chat_id)

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_messages
                    (chat_id, course_id, user_id, role, content,
                     ai_provider, ai_model, temperature, max_tokens,
                     context_material_ids, message_index)
                VALUES (%s, %s, %s, 'user', %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, chat_id, role, content, context_material_ids,
                          ai_provider, ai_model, message_index, created_at
            """, (
                chat_id, chat['course_id'], user['id'], content,
                ai_provider, ai_model, temperature, max_tokens,
                json.dumps(context_material_ids), next_idx,
            ))
            user_message = cursor.fetchone()
            if embed_text_via_lambda and write_chat_message_embedding:
                try:
                    user_embedding = embed_text_via_lambda(content)
                    if user_embedding:
                        write_chat_message_embedding(conn, user_message['id'], user_embedding)
                        metrics["embedding_success"] += 1
                    else:
                        metrics["embedding_null"] += 1
                except Exception:
                    metrics["embedding_errors"] += 1
                    logger.exception("Failed to persist user message embedding", extra={
                        "chat_id": chat_id,
                        "message_id": user_message.get('id'),
                    })
            else:
                metrics["embedding_null"] += 1

            # RAG retrieval + LLM synthesis
            chunks = retrieve_chunks(conn, content, context_material_ids)
            request_id = f"send-{uuid4().hex[:10]}"
            logger.info(
                "chat_synthesize_start",
                extra={
                    "request_id": request_id,
                    "action": "send",
                    "chat_id": chat_id,
                    "user_id": user["id"],
                    "ai_provider": ai_provider,
                    "ai_model": ai_model,
                    "agentic_enabled": _is_agentic_request(ai_provider, ai_model),
                    "retrieved_seed_chunks": len(chunks),
                    "context_material_count": len(context_material_ids),
                },
            )

            try:
                assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary = synthesize(
                    conn,
                    user['id'],
                    ai_provider,
                    ai_model,
                    content,
                    chunks,
                    chat_id=chat_id,
                    context_material_ids=context_material_ids,
                )
                logger.info(
                    "chat_synthesize_done",
                    extra={
                        "request_id": request_id,
                        "action": "send",
                        "chat_id": chat_id,
                        "ai_provider": ai_provider,
                        "ai_model": ai_model,
                        "assistant_char_count": len(assistant_content or ""),
                        "grounding_ref_count": len(retrieved_ids or []),
                        "intent_type": grounding_meta.get("intent_type"),
                        "resolver_confidence": grounding_meta.get("resolver_confidence"),
                        "verifier_passed": grounding_meta.get("verifier_passed"),
                        "repair_invoked": grounding_meta.get("repair_invoked"),
                    },
                )
            except ValueError as e:
                send_json(self, 400, {"error": str(e)})
                return
            except Exception as e:
                import requests as _requests
                if isinstance(e, _requests.HTTPError) and e.response is not None and e.response.status_code == 429:
                    send_json(self, 429, {"error": (
                        f"Rate limit exceeded for {ai_provider}. "
                        "You have sent too many requests — please wait a moment and try again, "
                        "or check your API usage and quota in your provider's dashboard."
                    )})
                    return
                raise

            cursor.execute("""
                INSERT INTO chat_messages
                    (chat_id, course_id, user_id, parent_message_id, role, content, summary,
                     ai_provider, ai_model, context_material_ids,
                     grounding_meta, tool_trace,
                     retrieved_chunk_ids, message_index)
                VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, chat_id, role, content, summary, ai_provider, ai_model,
                          retrieved_chunk_ids, context_token_count, response_token_count,
                          response_time_ms, finish_reason, message_index, created_at, tool_trace
            """, (
                chat_id, chat['course_id'], user['id'], user_message['id'], assistant_content,
                assistant_summary,
                ai_provider, ai_model,
                json.dumps(context_material_ids),
                json.dumps(grounding_meta or {}),
                json.dumps(tool_trace or []),
                json.dumps(retrieved_ids),
                next_idx + 1,
            ))
            assistant_message = cursor.fetchone()
            if embed_text_via_lambda and write_chat_message_embedding:
                try:
                    assistant_embedding = embed_text_via_lambda(assistant_content)
                    if assistant_embedding:
                        write_chat_message_embedding(conn, assistant_message['id'], assistant_embedding)
                        metrics["embedding_success"] += 1
                    else:
                        metrics["embedding_null"] += 1
                except Exception:
                    metrics["embedding_errors"] += 1
                    logger.exception("Failed to persist assistant message embedding", extra={
                        "chat_id": chat_id,
                        "message_id": assistant_message.get('id'),
                    })
            else:
                metrics["embedding_null"] += 1
            cursor.close()
            logger.info("chat_message_embedding_metrics", extra=metrics)

            suggested_title = _maybe_suggest_title(conn, chat, user['id'], next_idx)

        serialized_chunks = [
            {
                "chunk_text":  c.get("chunk_text", ""),
                "chunk_type":  c.get("chunk_type", ""),
                "page_number": c.get("page_number"),
                "similarity":  round(float(c.get("similarity", 0) or 0), 3),
                "source_type": c.get("source_type", ""),
                "material_id": c.get("material_id"),
            }
            for c in chunks
        ]
        send_json(self, 201, {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "chunks": serialized_chunks,
            "suggested_title": suggested_title,
        })

    def _stream_send_message(self, user, data):
        chat_id = data.get('chat_id')
        content = sanitize_string(data.get('content', '') or '', max_length=10000)
        context_material_ids = data.get('context_material_ids') or []
        ai_provider = data.get('ai_provider') or DEFAULT_AI_PROVIDER
        ai_model = data.get('ai_model')
        if ai_provider == "openai" and not ai_model:
            ai_model = DEFAULT_AI_MODEL
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens')

        if not isinstance(chat_id, int):
            send_json(self, 400, {"error": "chat_id is required"})
            return
        if not content:
            send_json(self, 400, {"error": "content is required"})
            return
        if ai_provider not in ('gemini', 'openai', 'claude'):
            send_json(self, 400, {"error": "ai_provider must be one of: gemini, openai, claude"})
            return
        if not ai_model:
            send_json(self, 400, {"error": "ai_model is required"})
            return
        if not isinstance(context_material_ids, list):
            send_json(self, 400, {"error": "context_material_ids must be a list"})
            return

        with get_db() as conn:
            chat = _get_chat(conn, chat_id)
            if not chat:
                send_json(self, 404, {"error": "Chat not found"})
                return
            if chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied to this chat"})
                return

            if context_material_ids:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM materials
                    WHERE id = ANY(%s::int[])
                      AND course_id = %s
                """, (context_material_ids, chat['course_id']))
                valid_ids = {row['id'] for row in cursor.fetchall()}
                cursor.close()
                invalid = [mid for mid in context_material_ids if mid not in valid_ids]
                if invalid:
                    send_json(self, 400, {"error": f"Invalid material IDs for this course: {invalid}"})
                    return

            next_idx = _next_message_index(conn, chat_id)

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_messages
                    (chat_id, course_id, user_id, role, content,
                     ai_provider, ai_model, temperature, max_tokens,
                     context_material_ids, message_index)
                VALUES (%s, %s, %s, 'user', %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, chat_id, role, content, context_material_ids,
                          ai_provider, ai_model, message_index, created_at
            """, (
                chat_id, chat['course_id'], user['id'], content,
                ai_provider, ai_model, temperature, max_tokens,
                json.dumps(context_material_ids), next_idx,
            ))
            user_message = cursor.fetchone()
            if embed_text_via_lambda and write_chat_message_embedding:
                try:
                    user_embedding = embed_text_via_lambda(content)
                    if user_embedding:
                        write_chat_message_embedding(conn, user_message['id'], user_embedding)
                except Exception:
                    logger.exception("Failed to persist user message embedding (stream_send)")

            # All validation passed — now commit to SSE headers
            send_sse_headers(self)
            send_sse_event(self, {"type": "user_message", "message": dict(user_message)})

            chunks = retrieve_chunks(conn, content, context_material_ids)
            request_id = f"stream-{uuid4().hex[:10]}"
            logger.info(
                "chat_synthesize_start",
                extra={
                    "request_id": request_id,
                    "action": "stream_send",
                    "chat_id": chat_id,
                    "user_id": user["id"],
                    "ai_provider": ai_provider,
                    "ai_model": ai_model,
                    "agentic_enabled": _is_agentic_request(ai_provider, ai_model),
                    "retrieved_seed_chunks": len(chunks),
                    "context_material_count": len(context_material_ids),
                },
            )

            def on_event(evt):
                send_sse_event(self, evt)

            try:
                assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary = synthesize(
                    conn,
                    user['id'],
                    ai_provider,
                    ai_model,
                    content,
                    chunks,
                    chat_id=chat_id,
                    context_material_ids=context_material_ids,
                    on_event=on_event,
                )
            except Exception as e:
                send_sse_event(self, {"type": "error", "message": str(e)})
                cursor.close()
                return

            cursor.execute("""
                INSERT INTO chat_messages
                    (chat_id, course_id, user_id, parent_message_id, role, content, summary,
                     ai_provider, ai_model, context_material_ids,
                     grounding_meta, tool_trace,
                     retrieved_chunk_ids, message_index)
                VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, chat_id, role, content, summary, ai_provider, ai_model,
                          retrieved_chunk_ids, context_token_count, response_token_count,
                          response_time_ms, finish_reason, message_index, created_at, tool_trace
            """, (
                chat_id, chat['course_id'], user['id'], user_message['id'], assistant_content,
                assistant_summary,
                ai_provider, ai_model,
                json.dumps(context_material_ids),
                json.dumps(grounding_meta or {}),
                json.dumps(tool_trace or []),
                json.dumps(retrieved_ids),
                next_idx + 1,
            ))
            assistant_message = cursor.fetchone()
            if embed_text_via_lambda and write_chat_message_embedding:
                try:
                    assistant_embedding = embed_text_via_lambda(assistant_content)
                    if assistant_embedding:
                        write_chat_message_embedding(conn, assistant_message['id'], assistant_embedding)
                except Exception:
                    logger.exception("Failed to persist assistant message embedding (stream_send)")
            cursor.close()

            suggested_title = _maybe_suggest_title(conn, chat, user['id'], next_idx)

            send_sse_event(self, {
                "type": "done",
                "user_message": dict(user_message),
                "assistant_message": dict(assistant_message),
                "suggested_title": suggested_title,
            })

    def _stream_edit_message(self, user, data):
        self._edit_message(user, data, is_streaming=True)

    def _edit_message(self, user, data, is_streaming=False):
        message_id = data.get('message_id')
        content = sanitize_string(data.get('content', '') or '', max_length=10000)
        context_material_ids = data.get('context_material_ids')
        ai_provider = data.get('ai_provider') or DEFAULT_AI_PROVIDER
        ai_model = data.get('ai_model')
        if ai_provider == "openai" and not ai_model:
            ai_model = DEFAULT_AI_MODEL

        if not isinstance(message_id, int):
            send_json(self, 400, {"error": "message_id is required"})
            return
        if not content:
            send_json(self, 400, {"error": "content is required"})
            return
        if ai_provider not in ('gemini', 'openai', 'claude'):
            send_json(self, 400, {"error": "ai_provider must be one of: gemini, openai, claude"})
            return
        if not ai_model:
            send_json(self, 400, {"error": "ai_model is required"})
            return
        if context_material_ids is not None and not isinstance(context_material_ids, list):
            send_json(self, 400, {"error": "context_material_ids must be a list"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, chat_id, course_id, user_id, role, content, context_material_ids,
                       message_index, ai_provider, ai_model, reply_history
                FROM chat_messages
                WHERE id = %s AND is_deleted = FALSE
                """,
                (message_id,)
            )
            msg = cursor.fetchone()
            if not msg:
                send_json(self, 404, {"error": "Message not found"})
                cursor.close()
                return
            if msg['user_id'] != user['id']:
                send_json(self, 403, {"error": "Only the message author can edit it"})
                cursor.close()
                return
            if msg['role'] != 'user':
                send_json(self, 400, {"error": "Only user messages can be edited"})
                cursor.close()
                return

            chat = _get_chat(conn, msg['chat_id'])
            if not chat or chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied to this chat"})
                cursor.close()
                return

            if context_material_ids is None:
                context_material_ids = msg.get('context_material_ids') or []

            if context_material_ids:
                cursor.execute("""
                    SELECT id FROM materials
                    WHERE id = ANY(%s::int[])
                      AND course_id = %s
                """, (context_material_ids, chat['course_id']))
                valid_ids = {row['id'] for row in cursor.fetchall()}
                invalid = [mid for mid in context_material_ids if mid not in valid_ids]
                if invalid:
                    send_json(self, 400, {"error": f"Invalid material IDs for this course: {invalid}"})
                    cursor.close()
                    return

            # Use parent_message_id to find the current live assistant response.
            # message_index + 1 is unreliable after reverts/regenerates leave gaps.
            cursor.execute(
                """
                SELECT id, content, retrieved_chunk_ids, ai_provider, ai_model
                FROM chat_messages
                WHERE parent_message_id = %s
                  AND role = 'assistant'
                  AND is_deleted = FALSE
                ORDER BY message_index DESC
                LIMIT 1
                """,
                (message_id,)
            )
            old_assistant = cursor.fetchone()
            displaced_reply = old_assistant['content'] if old_assistant else None
            if not displaced_reply:
                send_json(self, 400, {"error": "Cannot edit a message without an assistant reply"})
                cursor.close()
                return

            chunks = retrieve_chunks(conn, content, context_material_ids)

            if is_streaming:
                send_sse_headers(self)

            request_id = f"edit-{uuid4().hex[:10]}"
            logger.info(
                "chat_synthesize_start",
                extra={
                    "request_id": request_id,
                    "action": "edit",
                    "chat_id": msg["chat_id"],
                    "user_id": user["id"],
                    "ai_provider": ai_provider,
                    "ai_model": ai_model,
                    "agentic_enabled": _is_agentic_request(ai_provider, ai_model),
                    "retrieved_seed_chunks": len(chunks),
                    "context_material_count": len(context_material_ids),
                },
            )

            on_event = (lambda evt: send_sse_event(self, evt)) if is_streaming else None
            try:
                assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary = synthesize(
                    conn,
                    user['id'],
                    ai_provider,
                    ai_model,
                    content,
                    chunks,
                    chat_id=msg['chat_id'],
                    context_material_ids=context_material_ids,
                    on_event=on_event,
                )
                logger.info(
                    "chat_synthesize_done",
                    extra={
                        "request_id": request_id,
                        "action": "edit",
                        "chat_id": msg["chat_id"],
                        "ai_provider": ai_provider,
                        "ai_model": ai_model,
                        "assistant_char_count": len(assistant_content or ""),
                        "grounding_ref_count": len(retrieved_ids or []),
                        "intent_type": grounding_meta.get("intent_type"),
                        "resolver_confidence": grounding_meta.get("resolver_confidence"),
                        "verifier_passed": grounding_meta.get("verifier_passed"),
                        "repair_invoked": grounding_meta.get("repair_invoked"),
                    },
                )
            except Exception as e:
                cursor.close()
                if is_streaming:
                    send_sse_event(self, {"type": "error", "message": str(e)})
                    return
                import requests as _requests
                if isinstance(e, ValueError):
                    send_json(self, 400, {"error": str(e)})
                    return
                if isinstance(e, _requests.HTTPError) and e.response is not None and e.response.status_code == 429:
                    send_json(self, 429, {"error": (
                        f"Rate limit exceeded for {ai_provider}. "
                        "You have sent too many requests — please wait a moment and try again, "
                        "or check your API usage and quota in your provider's dashboard."
                    )})
                    return
                raise

            suggested_title = None
            try:
                # Build v2 reply_history: push displaced assistant + old user query to back, clear forward.
                # Store original_msg_id so revert can look up retrieved_chunk_ids directly from the DB row.
                back, _ = _parse_reply_history(msg.get('reply_history'))
                back = back + [{
                    'content': displaced_reply,
                    'user_query': msg['content'],  # user query before this edit
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'original_msg_id': old_assistant['id'],
                    'ai_provider': old_assistant.get('ai_provider'),
                    'ai_model': old_assistant.get('ai_model'),
                }]
                new_reply_history = _build_reply_history(back, [])

                cursor.execute(
                    """
                    UPDATE chat_messages
                    SET reply_history = %s::jsonb,
                        content = %s,
                        context_material_ids = %s,
                        ai_provider = %s,
                        ai_model = %s,
                        is_edited = TRUE,
                        edited_at = NOW()
                    WHERE id = %s
                    RETURNING id, chat_id, role, content, context_material_ids, ai_provider, ai_model,
                              is_edited, reply_history, edited_at, message_index, created_at
                    """,
                    (
                        new_reply_history,
                        content,
                        json.dumps(context_material_ids),
                        ai_provider,
                        ai_model,
                        message_id,
                    )
                )
                edited_user_message = cursor.fetchone()

                cursor.execute("""
                    UPDATE chat_messages
                    SET is_deleted = TRUE
                    WHERE chat_id = %s
                      AND message_index >= %s
                      AND is_deleted = FALSE
                """, (msg['chat_id'], msg['message_index'] + 1))

                next_idx = _next_message_index(conn, msg['chat_id'])

                if embed_text_via_lambda and write_chat_message_embedding:
                    try:
                        edited_user_embedding = embed_text_via_lambda(content)
                        if edited_user_embedding:
                            write_chat_message_embedding(conn, edited_user_message['id'], edited_user_embedding)
                    except Exception:
                        logger.exception("Failed to persist edited user message embedding", extra={
                            "chat_id": msg['chat_id'],
                            "message_id": edited_user_message.get('id'),
                        })
                cursor.execute("""
                    INSERT INTO chat_messages
                        (chat_id, course_id, user_id, parent_message_id, role, content, summary,
                         ai_provider, ai_model, context_material_ids,
                         grounding_meta, tool_trace,
                         retrieved_chunk_ids, message_index)
                    VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, chat_id, role, content, summary, ai_provider, ai_model,
                              retrieved_chunk_ids, context_token_count, response_token_count,
                              response_time_ms, finish_reason, message_index, created_at, tool_trace
                """, (
                    msg['chat_id'],
                    chat['course_id'],
                    user['id'],
                    edited_user_message['id'],
                    assistant_content,
                    assistant_summary,
                    ai_provider,
                    ai_model,
                    json.dumps(context_material_ids),
                    json.dumps(grounding_meta or {}),
                    json.dumps(tool_trace or []),
                    json.dumps(retrieved_ids),
                    next_idx,
                ))
                assistant_message = cursor.fetchone()

                if embed_text_via_lambda and write_chat_message_embedding:
                    try:
                        assistant_embedding = embed_text_via_lambda(assistant_content)
                        if assistant_embedding:
                            write_chat_message_embedding(conn, assistant_message['id'], assistant_embedding)
                    except Exception:
                        logger.exception("Failed to persist edited assistant message embedding", extra={
                            "chat_id": msg['chat_id'],
                            "message_id": assistant_message.get('id'),
                        })
                suggested_title = _maybe_suggest_title(conn, chat, user['id'], msg['message_index'])
            except Exception as e:
                if is_streaming:
                    send_sse_event(self, {"type": "error", "message": str(e)})
                    return
                raise
            finally:
                cursor.close()

        serialized_chunks = [
            {
                "chunk_text": c.get("chunk_text", ""),
                "chunk_type": c.get("chunk_type", ""),
                "page_number": c.get("page_number"),
                "similarity": round(float(c.get("similarity", 0) or 0), 3),
                "source_type": c.get("source_type", ""),
                "material_id": c.get("material_id"),
            }
            for c in chunks
        ]
        if is_streaming:
            send_sse_event(self, {
                "type": "done",
                "user_message": dict(edited_user_message),
                "assistant_message": dict(assistant_message),
                "suggested_title": suggested_title,
            })
        else:
            send_json(self, 200, {
                "user_message": edited_user_message,
                "assistant_message": assistant_message,
                "chunks": serialized_chunks,
                "suggested_title": suggested_title,
            })

    def _revert_message(self, user, data):
        message_id = data.get('message_id')
        if not isinstance(message_id, int):
            send_json(self, 400, {"error": "message_id is required"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, chat_id, course_id, user_id, role, content, message_index,
                       ai_provider, ai_model, context_material_ids, parent_message_id,
                       retrieved_chunk_ids
                FROM chat_messages
                WHERE id = %s AND is_deleted = FALSE
                """,
                (message_id,)
            )
            msg = cursor.fetchone()
            if not msg:
                send_json(self, 404, {"error": "Message not found"})
                cursor.close()
                return
            if msg['role'] != 'assistant':
                send_json(self, 400, {"error": "Can only revert assistant messages"})
                cursor.close()
                return

            chat = _get_chat(conn, msg['chat_id'])
            if not chat or chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied"})
                cursor.close()
                return

            # Use parent_message_id when available; fall back to nearest preceding user message.
            # (message_index - 1 is wrong when edits have created non-consecutive indices.)
            if msg.get('parent_message_id'):
                cursor.execute(
                    """
                    SELECT id, chat_id, role, content, message_index, reply_history,
                           context_material_ids
                    FROM chat_messages
                    WHERE id = %s AND role = 'user' AND is_deleted = FALSE
                    """,
                    (msg['parent_message_id'],)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, chat_id, role, content, message_index, reply_history,
                           context_material_ids
                    FROM chat_messages
                    WHERE chat_id = %s
                      AND message_index < %s
                      AND role = 'user'
                      AND is_deleted = FALSE
                    ORDER BY message_index DESC
                    LIMIT 1
                    """,
                    (msg['chat_id'], msg['message_index'])
                )
            user_msg = cursor.fetchone()
            if not user_msg:
                send_json(self, 400, {"error": "No preceding user message found"})
                cursor.close()
                return

            back, forward = _parse_reply_history(user_msg.get('reply_history'))
            if not back:
                send_json(self, 400, {"error": "No reply history to revert to"})
                cursor.close()
                return

            reverted_entry = back[-1]
            new_back = back[:-1]
            reverted_content = reverted_entry.get('content', '')
            reverted_user_query = reverted_entry.get('user_query')

            # Push current state onto forward so it can be restored later.
            # Store original_msg_id so restore can look up retrieved_chunk_ids directly from the DB.
            forward = forward + [{
                'content': msg['content'],
                'user_query': user_msg['content'],
                'ts': datetime.now(timezone.utc).isoformat(),
                'original_msg_id': msg['id'],
                'ai_provider': msg.get('ai_provider'),
                'ai_model': msg.get('ai_model'),
            }]
            new_reply_history = _build_reply_history(new_back, forward)

            new_user_content = reverted_user_query if reverted_user_query is not None else user_msg['content']
            cursor.execute(
                """
                UPDATE chat_messages
                SET reply_history = %s::jsonb,
                    content = %s
                WHERE id = %s
                RETURNING id, chat_id, role, content, context_material_ids, ai_provider, ai_model,
                          is_edited, reply_history, edited_at, message_index, created_at
                """,
                (new_reply_history, new_user_content, user_msg['id'])
            )
            updated_user_msg = cursor.fetchone()

            cursor.execute(
                """
                UPDATE chat_messages
                SET is_deleted = TRUE
                WHERE chat_id = %s
                  AND message_index >= %s
                  AND is_deleted = FALSE
                """,
                (msg['chat_id'], msg['message_index'])
            )

            next_idx = _next_message_index(conn, msg['chat_id'])

            # Look up the original chunk IDs from the DB row (works even for soft-deleted rows).
            original_msg_id = reverted_entry.get('original_msg_id')
            reverted_provider = reverted_entry.get('ai_provider')
            reverted_model = reverted_entry.get('ai_model')
            reverted_summary = None
            if original_msg_id:
                cursor.execute(
                    "SELECT retrieved_chunk_ids, ai_provider, ai_model, tool_trace, summary FROM chat_messages WHERE id = %s",
                    (original_msg_id,)
                )
                orig_row = cursor.fetchone()
                reverted_chunk_ids = (orig_row['retrieved_chunk_ids'] if orig_row else None) or []
                reverted_tool_trace = (orig_row['tool_trace'] if orig_row else None)
                if orig_row:
                    reverted_provider = reverted_provider or orig_row.get('ai_provider')
                    reverted_model = reverted_model or orig_row.get('ai_model')
                    reverted_summary = orig_row.get('summary')
            else:
                reverted_chunk_ids = reverted_entry.get('retrieved_chunk_ids') or []
                reverted_tool_trace = None
            reverted_provider = reverted_provider or msg.get('ai_provider')
            reverted_model = reverted_model or msg.get('ai_model')

            cursor.execute(
                """
                INSERT INTO chat_messages
                    (chat_id, course_id, user_id, parent_message_id, role, content, summary,
                     ai_provider, ai_model, context_material_ids, retrieved_chunk_ids, tool_trace, message_index)
                VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id, chat_id, role, content, summary, ai_provider, ai_model,
                          retrieved_chunk_ids, tool_trace, message_index, created_at
                """,
                (
                    msg['chat_id'],
                    chat['course_id'],
                    user['id'],
                    user_msg['id'],
                    reverted_content,
                    reverted_summary,
                    reverted_provider,
                    reverted_model,
                    json.dumps(user_msg.get('context_material_ids') or []),
                    json.dumps(reverted_chunk_ids),
                    json.dumps(reverted_tool_trace) if reverted_tool_trace is not None else None,
                    next_idx,
                )
            )
            new_assistant = cursor.fetchone()
            cursor.close()

        send_json(self, 200, {
            "user_message": updated_user_msg,
            "assistant_message": new_assistant,
        })

    def _restore_message(self, user, data):
        """Restore the most recently reverted assistant response (redo)."""
        message_id = data.get('message_id')
        if not isinstance(message_id, int):
            send_json(self, 400, {"error": "message_id is required"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, chat_id, course_id, user_id, role, content, message_index,
                       ai_provider, ai_model, context_material_ids, parent_message_id,
                       retrieved_chunk_ids
                FROM chat_messages
                WHERE id = %s AND is_deleted = FALSE
                """,
                (message_id,)
            )
            msg = cursor.fetchone()
            if not msg:
                send_json(self, 404, {"error": "Message not found"})
                cursor.close()
                return
            if msg['role'] != 'assistant':
                send_json(self, 400, {"error": "Can only restore assistant messages"})
                cursor.close()
                return

            chat = _get_chat(conn, msg['chat_id'])
            if not chat or chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied"})
                cursor.close()
                return

            if msg.get('parent_message_id'):
                cursor.execute(
                    """
                    SELECT id, chat_id, role, content, message_index, reply_history,
                           context_material_ids
                    FROM chat_messages
                    WHERE id = %s AND role = 'user' AND is_deleted = FALSE
                    """,
                    (msg['parent_message_id'],)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, chat_id, role, content, message_index, reply_history,
                           context_material_ids
                    FROM chat_messages
                    WHERE chat_id = %s
                      AND message_index < %s
                      AND role = 'user'
                      AND is_deleted = FALSE
                    ORDER BY message_index DESC
                    LIMIT 1
                    """,
                    (msg['chat_id'], msg['message_index'])
                )
            user_msg = cursor.fetchone()
            if not user_msg:
                send_json(self, 400, {"error": "No preceding user message found"})
                cursor.close()
                return

            back, forward = _parse_reply_history(user_msg.get('reply_history'))
            if not forward:
                send_json(self, 400, {"error": "No forward history to restore"})
                cursor.close()
                return

            restored_entry = forward[-1]
            new_forward = forward[:-1]
            restored_content = restored_entry.get('content', '')
            restored_user_query = restored_entry.get('user_query')

            # Push current state back onto back stack.
            back = back + [{
                'content': msg['content'],
                'user_query': user_msg['content'],
                'ts': datetime.now(timezone.utc).isoformat(),
                'original_msg_id': msg['id'],
                'ai_provider': msg.get('ai_provider'),
                'ai_model': msg.get('ai_model'),
            }]
            new_reply_history = _build_reply_history(back, new_forward)

            new_user_content = restored_user_query if restored_user_query is not None else user_msg['content']
            cursor.execute(
                """
                UPDATE chat_messages
                SET reply_history = %s::jsonb,
                    content = %s
                WHERE id = %s
                RETURNING id, chat_id, role, content, context_material_ids, ai_provider, ai_model,
                          is_edited, reply_history, edited_at, message_index, created_at
                """,
                (new_reply_history, new_user_content, user_msg['id'])
            )
            updated_user_msg = cursor.fetchone()

            cursor.execute(
                """
                UPDATE chat_messages
                SET is_deleted = TRUE
                WHERE chat_id = %s
                  AND message_index >= %s
                  AND is_deleted = FALSE
                """,
                (msg['chat_id'], msg['message_index'])
            )

            next_idx = _next_message_index(conn, msg['chat_id'])

            # Look up the original chunk IDs from the DB row (works even for soft-deleted rows).
            original_msg_id = restored_entry.get('original_msg_id')
            restored_provider = restored_entry.get('ai_provider')
            restored_model = restored_entry.get('ai_model')
            restored_summary = None
            if original_msg_id:
                cursor.execute(
                    "SELECT retrieved_chunk_ids, ai_provider, ai_model, tool_trace, summary FROM chat_messages WHERE id = %s",
                    (original_msg_id,)
                )
                orig_row = cursor.fetchone()
                restored_chunk_ids = (orig_row['retrieved_chunk_ids'] if orig_row else None) or []
                restored_tool_trace = (orig_row['tool_trace'] if orig_row else None)
                if orig_row:
                    restored_provider = restored_provider or orig_row.get('ai_provider')
                    restored_model = restored_model or orig_row.get('ai_model')
                    restored_summary = orig_row.get('summary')
            else:
                restored_chunk_ids = restored_entry.get('retrieved_chunk_ids') or []
                restored_tool_trace = None
            restored_provider = restored_provider or msg.get('ai_provider')
            restored_model = restored_model or msg.get('ai_model')

            cursor.execute(
                """
                INSERT INTO chat_messages
                    (chat_id, course_id, user_id, parent_message_id, role, content, summary,
                     ai_provider, ai_model, context_material_ids, retrieved_chunk_ids, tool_trace, message_index)
                VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id, chat_id, role, content, summary, ai_provider, ai_model,
                          retrieved_chunk_ids, tool_trace, message_index, created_at
                """,
                (
                    msg['chat_id'],
                    chat['course_id'],
                    user['id'],
                    user_msg['id'],
                    restored_content,
                    restored_summary,
                    restored_provider,
                    restored_model,
                    json.dumps(user_msg.get('context_material_ids') or []),
                    json.dumps(restored_chunk_ids),
                    json.dumps(restored_tool_trace) if restored_tool_trace is not None else None,
                    next_idx,
                )
            )
            new_assistant = cursor.fetchone()
            cursor.close()

        send_json(self, 200, {
            "user_message": updated_user_msg,
            "assistant_message": new_assistant,
        })

    def _stream_regenerate_message(self, user, data):
        self._regenerate_message(user, data, is_streaming=True)

    def _regenerate_message(self, user, data, is_streaming=False):
        """Re-run the parent user query through a (possibly different) model.

        Displaces the current assistant response into reply_history.back (clearing forward),
        then synthesizes a fresh response without modifying the user message content.
        """
        message_id = data.get('message_id')
        ai_provider = data.get('ai_provider') or DEFAULT_AI_PROVIDER
        ai_model = data.get('ai_model')
        if ai_provider == "openai" and not ai_model:
            ai_model = DEFAULT_AI_MODEL

        if not isinstance(message_id, int):
            send_json(self, 400, {"error": "message_id is required"})
            return
        if ai_provider not in ('gemini', 'openai', 'claude'):
            send_json(self, 400, {"error": "ai_provider must be one of: gemini, openai, claude"})
            return
        if not ai_model:
            send_json(self, 400, {"error": "ai_model is required"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, chat_id, course_id, user_id, role, content, message_index,
                       ai_provider, ai_model, context_material_ids, parent_message_id
                FROM chat_messages
                WHERE id = %s AND is_deleted = FALSE
                """,
                (message_id,)
            )
            msg = cursor.fetchone()
            if not msg:
                send_json(self, 404, {"error": "Message not found"})
                cursor.close()
                return
            if msg['role'] != 'assistant':
                send_json(self, 400, {"error": "Can only regenerate assistant messages"})
                cursor.close()
                return
            if msg['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied"})
                cursor.close()
                return

            chat = _get_chat(conn, msg['chat_id'])
            if not chat or chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Access denied"})
                cursor.close()
                return

            if msg.get('parent_message_id'):
                cursor.execute(
                    """
                    SELECT id, chat_id, role, content, message_index, reply_history,
                           context_material_ids, ai_provider, ai_model
                    FROM chat_messages
                    WHERE id = %s AND role = 'user' AND is_deleted = FALSE
                    """,
                    (msg['parent_message_id'],)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, chat_id, role, content, message_index, reply_history,
                           context_material_ids, ai_provider, ai_model
                    FROM chat_messages
                    WHERE chat_id = %s
                      AND message_index < %s
                      AND role = 'user'
                      AND is_deleted = FALSE
                    ORDER BY message_index DESC
                    LIMIT 1
                    """,
                    (msg['chat_id'], msg['message_index'])
                )
            user_msg = cursor.fetchone()
            if not user_msg:
                send_json(self, 400, {"error": "No preceding user message found"})
                cursor.close()
                return

            context_material_ids = user_msg.get('context_material_ids') or []
            locked_chunk_ids = msg.get('retrieved_chunk_ids') or []
            if isinstance(locked_chunk_ids, str):
                try:
                    locked_chunk_ids = json.loads(locked_chunk_ids)
                except json.JSONDecodeError:
                    locked_chunk_ids = []
            if not isinstance(locked_chunk_ids, list):
                locked_chunk_ids = []
            locked_chunk_ids = [str(cid) for cid in locked_chunk_ids if cid is not None]

            locked_chunks = []
            if locked_chunk_ids:
                hydrated_locked_chunks = _fetch_chunk_context(conn, locked_chunk_ids)
                by_id = {str(c.get('id')): c for c in hydrated_locked_chunks}
                ordered_hydrated = [by_id[cid] for cid in locked_chunk_ids if cid in by_id]
                for idx, chunk in enumerate(ordered_hydrated):
                    locked_chunks.append(
                        {
                            "id": chunk.get("id"),
                            "chunk_text": chunk.get("chunk_text", ""),
                            "chunk_type": chunk.get("chunk_type", ""),
                            "page_number": chunk.get("page_number"),
                            # Keep stable, deterministic ordering signal for prompt context.
                            "similarity": max(0.0, 1.0 - (idx * 0.01)),
                            "source_type": chunk.get("source_type", ""),
                            "material_id": chunk.get("material_id"),
                        }
                    )

            # Regenerate should default to the exact same grounding snapshot when available.
            # Fall back to fresh retrieval only for legacy rows without stored chunk refs.
            chunks = locked_chunks or retrieve_chunks(conn, user_msg['content'], context_material_ids)

            if is_streaming:
                send_sse_headers(self)

            request_id = f"regen-{uuid4().hex[:10]}"
            logger.info(
                "chat_synthesize_start",
                extra={
                    "request_id": request_id,
                    "action": "regenerate",
                    "chat_id": msg["chat_id"],
                    "user_id": user["id"],
                    "ai_provider": ai_provider,
                    "ai_model": ai_model,
                    "agentic_enabled": _is_agentic_request(ai_provider, ai_model),
                    "retrieved_seed_chunks": len(chunks),
                    "context_material_count": len(context_material_ids),
                },
            )

            on_event = (lambda evt: send_sse_event(self, evt)) if is_streaming else None
            try:
                assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary = synthesize(
                    conn,
                    user['id'],
                    ai_provider,
                    ai_model,
                    user_msg['content'],
                    chunks,
                    chat_id=msg['chat_id'],
                    context_material_ids=context_material_ids,
                    on_event=on_event,
                    force_context_only=bool(locked_chunks),
                )
                logger.info(
                    "chat_synthesize_done",
                    extra={
                        "request_id": request_id,
                        "action": "regenerate",
                        "chat_id": msg["chat_id"],
                        "ai_provider": ai_provider,
                        "ai_model": ai_model,
                        "assistant_char_count": len(assistant_content or ""),
                        "grounding_ref_count": len(retrieved_ids or []),
                        "intent_type": grounding_meta.get("intent_type"),
                        "resolver_confidence": grounding_meta.get("resolver_confidence"),
                        "verifier_passed": grounding_meta.get("verifier_passed"),
                        "repair_invoked": grounding_meta.get("repair_invoked"),
                    },
                )
            except Exception as e:
                cursor.close()
                if is_streaming:
                    send_sse_event(self, {"type": "error", "message": str(e)})
                    return
                import requests as _requests
                if isinstance(e, ValueError):
                    send_json(self, 400, {"error": str(e)})
                    return
                if isinstance(e, _requests.HTTPError) and e.response is not None and e.response.status_code == 429:
                    send_json(self, 429, {"error": (
                        f"Rate limit exceeded for {ai_provider}. "
                        "You have sent too many requests — please wait a moment and try again, "
                        "or check your API usage and quota in your provider's dashboard."
                    )})
                    return
                raise

            suggested_title = None
            try:
                # Displace current response to back, clear forward (new branch).
                back, _ = _parse_reply_history(user_msg.get('reply_history'))
                back = back + [{
                    'content': msg['content'],
                    'user_query': user_msg['content'],
                    'ts': datetime.now(timezone.utc).isoformat(),
                    'original_msg_id': msg['id'],
                    'ai_provider': msg.get('ai_provider'),
                    'ai_model': msg.get('ai_model'),
                }]
                new_reply_history = _build_reply_history(back, [])

                cursor.execute(
                    """
                    UPDATE chat_messages
                    SET reply_history = %s::jsonb
                    WHERE id = %s
                    RETURNING id, chat_id, role, content, context_material_ids, ai_provider, ai_model,
                              is_edited, reply_history, edited_at, message_index, created_at
                    """,
                    (new_reply_history, user_msg['id'])
                )
                updated_user_msg = cursor.fetchone()

                cursor.execute(
                    """
                    UPDATE chat_messages
                    SET is_deleted = TRUE
                    WHERE chat_id = %s
                      AND message_index >= %s
                      AND is_deleted = FALSE
                    """,
                    (msg['chat_id'], msg['message_index'])
                )

                next_idx = _next_message_index(conn, msg['chat_id'])

                cursor.execute(
                    """
                    INSERT INTO chat_messages
                        (chat_id, course_id, user_id, parent_message_id, role, content, summary,
                         ai_provider, ai_model, context_material_ids, grounding_meta, tool_trace,
                         retrieved_chunk_ids, message_index)
                    VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, chat_id, role, content, summary, ai_provider, ai_model, retrieved_chunk_ids,
                              message_index, created_at, tool_trace
                    """,
                    (
                        msg['chat_id'],
                        chat['course_id'],
                        user['id'],
                        user_msg['id'],
                        assistant_content,
                        assistant_summary,
                        ai_provider,
                        ai_model,
                        json.dumps(context_material_ids),
                        json.dumps(grounding_meta or {}),
                        json.dumps(tool_trace or []),
                        json.dumps(retrieved_ids),
                        next_idx,
                    )
                )
                new_assistant = cursor.fetchone()
                suggested_title = _maybe_suggest_title(conn, chat, user['id'], user_msg['message_index'])
            except Exception as e:
                if is_streaming:
                    send_sse_event(self, {"type": "error", "message": str(e)})
                    return
                raise
            finally:
                cursor.close()

        if is_streaming:
            send_sse_event(self, {
                "type": "done",
                "user_message": dict(updated_user_msg),
                "assistant_message": dict(new_assistant),
                "suggested_title": suggested_title,
            })
        else:
            send_json(self, 200, {
                "user_message": updated_user_msg,
                "assistant_message": new_assistant,
                "suggested_title": suggested_title,
            })

    def _delete_message(self, user, data):
        message_id = data.get('message_id')
        if not isinstance(message_id, int):
            send_json(self, 400, {"error": "message_id is required"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chat_messages WHERE id = %s AND is_deleted = FALSE",
                (message_id,)
            )
            msg = cursor.fetchone()
            if not msg:
                send_json(self, 404, {"error": "Message not found"})
                cursor.close()
                return
            if msg['user_id'] != user['id']:
                send_json(self, 403, {"error": "Only the message author can delete it"})
                cursor.close()
                return

            # Soft-delete the user message and the immediately following assistant reply
            cursor.execute("""
                UPDATE chat_messages
                SET is_deleted = TRUE
                WHERE chat_id = %s
                  AND message_index IN (%s, %s)
                  AND is_deleted = FALSE
            """, (msg['chat_id'], msg['message_index'], msg['message_index'] + 1))
            cursor.close()

        send_json(self, 200, {"success": True})

    # ----------------------------------------------------------- pin helpers --

    def _list_pins(self, user, params):
        course_id_raw = params.get('course_id', [None])[0]
        if not course_id_raw or not str(course_id_raw).isdigit():
            send_json(self, 400, {"error": "course_id query parameter is required"})
            return
        course_id = int(course_id_raw)

        if not Course.verify_access(course_id, user['id']):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    pm.id,
                    pm.user_message_id,
                    pm.assistant_message_id,
                    pm.chat_id,
                    pm.course_id,
                    COALESCE(am.summary, pm.ai_summary, '') AS ai_summary,
                    pm.pinned_at,
                    ch.title AS chat_title,
                    um.content AS user_content,
                    am.content AS assistant_content,
                    am.summary AS assistant_summary,
                    am.ai_provider,
                    am.ai_model
                FROM pinned_messages pm
                JOIN chats ch ON ch.id = pm.chat_id
                JOIN chat_messages um ON um.id = pm.user_message_id
                JOIN chat_messages am ON am.id = pm.assistant_message_id
                WHERE pm.user_id = %s AND pm.course_id = %s
                ORDER BY pm.pinned_at DESC
            """, (user['id'], course_id))
            rows = cursor.fetchall()
            cursor.close()

        pins = [
            {
                "id": row['id'],
                "user_message_id": row['user_message_id'],
                "assistant_message_id": row['assistant_message_id'],
                "chat_id": row['chat_id'],
                "course_id": row['course_id'],
                "ai_summary": row['ai_summary'],
                "pinned_at": row['pinned_at'].isoformat() if row['pinned_at'] else None,
                "chat_title": row['chat_title'],
                "user_message": {"id": row['user_message_id'], "role": "user", "content": row['user_content']},
                "assistant_message": {
                    "id": row['assistant_message_id'],
                    "role": "assistant",
                    "content": row['assistant_content'],
                    "summary": row['assistant_summary'],
                    "ai_provider": row['ai_provider'],
                    "ai_model": row['ai_model'],
                },
            }
            for row in rows
        ]
        send_json(self, 200, {"pins": pins})

    def _pin_message(self, user, data):
        user_message_id = data.get('user_message_id')
        assistant_message_id = data.get('assistant_message_id')
        course_id = data.get('course_id')
        chat_id = data.get('chat_id')

        if not all(isinstance(v, int) for v in [user_message_id, assistant_message_id, course_id, chat_id]):
            send_json(self, 400, {"error": "user_message_id, assistant_message_id, course_id, and chat_id are required integers"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            # Verify ownership of both messages
            cursor.execute(
                "SELECT id FROM chat_messages WHERE id = %s AND user_id = %s",
                (user_message_id, user['id'])
            )
            if not cursor.fetchone():
                cursor.close()
                send_json(self, 403, {"error": "Access denied: user message not owned by caller"})
                return
            cursor.execute(
                "SELECT COALESCE(summary, '') AS s FROM chat_messages WHERE id = %s AND user_id = %s",
                (assistant_message_id, user['id'])
            )
            asst = cursor.fetchone()
            if not asst:
                cursor.close()
                send_json(self, 403, {"error": "Access denied: assistant message not owned by caller"})
                return
            pin_summary = (asst['s'] or '')[:300]

            cursor.execute("""
                INSERT INTO pinned_messages
                  (user_id, course_id, chat_id, user_message_id, assistant_message_id, ai_summary)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, assistant_message_id) DO NOTHING
                RETURNING id, pinned_at
            """, (user['id'], course_id, chat_id, user_message_id, assistant_message_id, pin_summary))
            row = cursor.fetchone()
            cursor.close()

        if row:
            send_json(self, 200, {"pin": {"id": row['id'], "pinned_at": row['pinned_at'].isoformat()}})
        else:
            # Already pinned — idempotent success
            send_json(self, 200, {"pin": None})

    def _unpin_message(self, user, data):
        assistant_message_id = data.get('assistant_message_id')
        if not isinstance(assistant_message_id, int):
            send_json(self, 400, {"error": "assistant_message_id is required"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM pinned_messages
                WHERE user_id = %s AND assistant_message_id = %s
            """, (user['id'], assistant_message_id))
            deleted = cursor.rowcount > 0
            cursor.close()

        send_json(self, 200, {"deleted": deleted})

    def _delete_chat(self, user, data):
        chat_id = data.get('chat_id')
        if not isinstance(chat_id, int):
            send_json(self, 400, {"error": "chat_id is required"})
            return

        with get_db() as conn:
            chat = _get_chat(conn, chat_id)
            if not chat:
                send_json(self, 404, {"error": "Chat not found"})
                return
            if chat['user_id'] != user['id']:
                send_json(self, 403, {"error": "Only the chat owner can delete it"})
                return

            cursor = conn.cursor()
            cursor.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
            cursor.close()

        send_json(self, 200, {"success": True})
