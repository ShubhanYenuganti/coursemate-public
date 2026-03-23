"""
Message persistence for conversation grounding.
Stores messages with Voyage AI embeddings in the `messages` table.
Uses sync voyageai.Client to match Vercel's sync runtime.
"""
import json
import os
import voyageai

_vo = None


def _get_client():
    global _vo
    if _vo is None:
        _vo = voyageai.Client(api_key=os.environ['VOYAGE_API_KEY'])
    return _vo


def _vec_str(emb: list) -> str:
    return '[' + ','.join(str(x) for x in emb) + ']'


def _embed_text(text: str) -> list | None:
    if not text:
        return None
    vo = _get_client()
    result = vo.embed(texts=[text], model="voyage-3.5", input_type="document")
    return result.embeddings[0]


def persist_message(conn, session_id: str, role: str, content: str,
                    tool_calls: list = None, grounding_refs: list = None) -> None:
    """
    Insert a message into the `messages` table with a Voyage AI embedding.
    Non-critical — callers should catch exceptions.
    """
    tool_calls = tool_calls or []
    grounding_refs = grounding_refs or []

    try:
        emb = _embed_text(content)
    except Exception:
        emb = None

    vec = _vec_str(emb) if emb else None

    cursor = conn.cursor()
    if vec:
        cursor.execute("""
            INSERT INTO messages (session_id, role, content, embedding, tool_calls, grounding_refs)
            VALUES (%s, %s, %s, %s::vector, %s, %s)
        """, (session_id, role, content, vec, json.dumps(tool_calls), json.dumps(grounding_refs)))
    else:
        cursor.execute("""
            INSERT INTO messages (session_id, role, content, tool_calls, grounding_refs)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, role, content, json.dumps(tool_calls), json.dumps(grounding_refs)))
    cursor.close()
