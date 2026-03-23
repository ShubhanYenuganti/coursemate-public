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
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string, check_rate_limit
    from .models import User
    from .courses import Course
    from .db import get_db
    from .rag import retrieve_chunks
    from .llm import synthesize
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string, check_rate_limit
    from models import User
    from courses import Course
    from db import get_db
    from rag import retrieve_chunks
    from llm import synthesize

try:
    from services.query.persistence import embed_text_via_lambda, write_chat_message_embedding
except ImportError:
    embed_text_via_lambda = None
    write_chat_message_embedding = None


logger = logging.getLogger(__name__)


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


def _parse_body(handler):
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length).decode('utf-8')
        return json.loads(body) if body else {}, None
    except (ValueError, json.JSONDecodeError):
        return None, "Invalid request body"


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
        elif resource == 'message':
            if action == 'send':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._send_message(user, data)
            elif action == 'edit':
                if not check_rate_limit(self, max_rpm=10):
                    send_json(self, 429, {"error": "Rate limit exceeded"})
                    return
                self._edit_message(user, data)
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
                        SELECT id, chat_id, role, content, ai_provider, ai_model,
                               context_material_ids, retrieved_chunk_ids, context_token_count,
                               response_token_count, response_time_ms, finish_reason,
                               is_edited, reply_history, edited_at, message_index, created_at
                        FROM chat_messages
                        WHERE chat_id = %s
                          AND is_deleted = FALSE
                          AND message_index < %s
                        ORDER BY message_index DESC
                        LIMIT %s
                    """, (chat_id, int(before_raw), limit))
                else:
                    cursor.execute("""
                        SELECT id, chat_id, role, content, ai_provider, ai_model,
                               context_material_ids, retrieved_chunk_ids, context_token_count,
                               response_token_count, response_time_ms, finish_reason,
                               is_edited, reply_history, edited_at, message_index, created_at
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

            from services.query.retrieval import _fetch_chunk_context
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
                UPDATE chats SET title = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, course_id, user_id, title, visibility, message_count,
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
        ai_provider = data.get('ai_provider')
        ai_model = data.get('ai_model')
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

            try:
                assistant_content, retrieved_ids = synthesize(
                    conn, user['id'], ai_provider, ai_model, content, chunks
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
                    (chat_id, course_id, user_id, parent_message_id, role, content,
                     ai_provider, ai_model, context_material_ids,
                     retrieved_chunk_ids, message_index)
                VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s)
                RETURNING id, chat_id, role, content, retrieved_chunk_ids,
                          context_token_count, response_token_count,
                          response_time_ms, finish_reason, message_index, created_at
            """, (
                chat_id, chat['course_id'], user['id'], user_message['id'], assistant_content,
                ai_provider, ai_model,
                json.dumps(context_material_ids),
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
        })

    def _edit_message(self, user, data):
        message_id = data.get('message_id')
        content = sanitize_string(data.get('content', '') or '', max_length=10000)
        context_material_ids = data.get('context_material_ids')
        ai_provider = data.get('ai_provider')
        ai_model = data.get('ai_model')

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
                       message_index, ai_provider, ai_model
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

            cursor.execute(
                """
                SELECT content
                FROM chat_messages
                WHERE chat_id = %s
                  AND message_index = %s
                  AND role = 'assistant'
                  AND is_deleted = FALSE
                ORDER BY id ASC
                LIMIT 1
                """,
                (msg['chat_id'], msg['message_index'] + 1)
            )
            old_assistant = cursor.fetchone()
            displaced_reply = old_assistant['content'] if old_assistant else None
            if not displaced_reply:
                send_json(self, 400, {"error": "Cannot edit a message without an assistant reply"})
                cursor.close()
                return

            chunks = retrieve_chunks(conn, content, context_material_ids)

            try:
                assistant_content, retrieved_ids = synthesize(
                    conn, user['id'], ai_provider, ai_model, content, chunks
                )
            except ValueError as e:
                send_json(self, 400, {"error": str(e)})
                cursor.close()
                return
            except Exception as e:
                import requests as _requests
                if isinstance(e, _requests.HTTPError) and e.response is not None and e.response.status_code == 429:
                    send_json(self, 429, {"error": (
                        f"Rate limit exceeded for {ai_provider}. "
                        "You have sent too many requests — please wait a moment and try again, "
                        "or check your API usage and quota in your provider's dashboard."
                    )})
                    cursor.close()
                    return
                cursor.close()
                raise

            cursor.execute(
                """
                UPDATE chat_messages
                SET reply_history = COALESCE(reply_history, '[]'::jsonb) ||
                        CASE
                            WHEN %s::text IS NULL THEN '[]'::jsonb
                            ELSE jsonb_build_array(
                                jsonb_build_object('content', %s::text, 'edited_at', NOW()::text)
                            )
                        END,
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
                    displaced_reply,
                    displaced_reply,
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
                    (chat_id, course_id, user_id, parent_message_id, role, content,
                     ai_provider, ai_model, context_material_ids,
                     retrieved_chunk_ids, message_index)
                VALUES (%s, %s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s)
                RETURNING id, chat_id, role, content, retrieved_chunk_ids,
                          context_token_count, response_token_count,
                          response_time_ms, finish_reason, message_index, created_at
            """, (
                msg['chat_id'],
                chat['course_id'],
                user['id'],
                edited_user_message['id'],
                assistant_content,
                ai_provider,
                ai_model,
                json.dumps(context_material_ids),
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
        send_json(self, 200, {
            "user_message": edited_user_message,
            "assistant_message": assistant_message,
            "chunks": serialized_chunks,
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
