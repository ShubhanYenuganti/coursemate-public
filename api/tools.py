"""
Tool execution helpers for agentic chat loops.
"""
import hashlib
import json
import os
import time

try:
    from .rag import retrieve_chunks
except ImportError:
    from rag import retrieve_chunks

try:
    from services.query.retrieval import _fetch_chunk_context
except ImportError:
    _fetch_chunk_context = None

try:
    from services.query.persistence import embed_text_via_lambda
except ImportError:
    embed_text_via_lambda = None


def _dedupe_preserve_order(values):
    seen = set()
    out = []
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _chunk_id(value):
    return str(value)


def _format_search_payload(query: str, chunks: list) -> str:
    if not chunks:
        return (
            f"No relevant chunks found for query: {query!r}. "
            "Consider rewriting the query or asking a narrower follow-up."
        )

    lines = [f"Search results for query: {query!r}"]
    for idx, chunk in enumerate(chunks, 1):
        chunk_id = _chunk_id(chunk.get("id"))
        chunk_type = chunk.get("chunk_type", "unknown")
        similarity = float(chunk.get("similarity", 0) or 0)
        material_id = chunk.get("material_id")
        page = chunk.get("page_number")
        header = (
            f"[{idx}] id={chunk_id} type={chunk_type} "
            f"material_id={material_id} similarity={similarity:.3f}"
        )
        if page is not None:
            header += f" page={page}"
        lines.append(header)
        lines.append(chunk.get("chunk_text", ""))
        lines.append("")
    return "\n".join(lines).strip()


def execute_search_materials(conn, query: str, material_ids: list, top_k: int = 8) -> dict:
    """
    Execute scoped material search for the agent loop.

    Returns:
        {
            "text": str,
            "chunk_ids": list[str],
            "meta": {...}
        }
    """
    started = time.time()
    cleaned_query = (query or "").strip()
    scoped_material_ids = material_ids if isinstance(material_ids, list) else []
    safe_top_k = max(1, min(int(top_k or 8), 12))

    if not cleaned_query:
        return {
            "text": "Search query is empty; provide a non-empty query.",
            "chunk_ids": [],
            "meta": {"tool": "search_materials", "query": "", "result_count": 0, "latency_ms": 0},
        }

    chunks = retrieve_chunks(conn, cleaned_query, scoped_material_ids, top_k=safe_top_k)
    chunk_ids = _dedupe_preserve_order(
        [_chunk_id(c.get("id")) for c in chunks if c.get("id") is not None]
    )
    latency_ms = int((time.time() - started) * 1000)
    return {
        "text": _format_search_payload(cleaned_query, chunks),
        "chunk_ids": chunk_ids,
        "meta": {
            "tool": "search_materials",
            "query": cleaned_query,
            "result_count": len(chunks),
            "material_scope_count": len(scoped_material_ids),
            "top_k": safe_top_k,
            "latency_ms": latency_ms,
        },
    }


def execute_web_search(_conn, query: str, ttl_seconds: int = 3600) -> dict:
    """
    P0 stub for web search tool. Runtime integration is P1.
    """
    enabled = os.environ.get("AGENTIC_WEB_SEARCH_ENABLED", "false").lower() == "true"
    query_hash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()
    if not enabled:
        return {
            "text": "Web search is disabled in this environment.",
            "chunk_ids": [],
            "meta": {"tool": "web_search", "enabled": False, "query_hash": query_hash},
        }

    return {
        "text": "Web search runtime path is not yet implemented.",
        "chunk_ids": [],
        "meta": {"tool": "web_search", "enabled": True, "query_hash": query_hash, "ttl_seconds": ttl_seconds},
    }


def execute_rerank(_conn, _query: str, chunk_ids: list, top_n: int = 5) -> dict:
    """
    P0 stub for rerank tool. Runtime integration is P1.
    """
    enabled = os.environ.get("AGENTIC_RERANK_ENABLED", "false").lower() == "true"
    if not enabled:
        return {
            "text": "Rerank is disabled in this environment.",
            "chunk_ids": chunk_ids or [],
            "meta": {"tool": "rerank_results", "enabled": False},
        }
    return {
        "text": "Rerank runtime path is not yet implemented.",
        "chunk_ids": chunk_ids or [],
        "meta": {"tool": "rerank_results", "enabled": True, "top_n": top_n},
    }


def pull_grounding_context(conn, chat_id: int, query_text: str, max_msgs: int = 5, max_chunks: int = 8) -> dict:
    """
    Pull semantically related prior chat turns and hydrate their cited chunks.
    """
    if not embed_text_via_lambda or not _fetch_chunk_context:
        return {"messages": [], "chunks": [], "chunk_ids": [], "text": ""}
    if not query_text or not str(query_text).strip():
        return {"messages": [], "chunks": [], "chunk_ids": [], "text": ""}

    query_embedding = embed_text_via_lambda(query_text)
    if not query_embedding:
        return {"messages": [], "chunks": [], "chunk_ids": [], "text": ""}

    vec = "[" + ",".join(str(x) for x in query_embedding) + "]"
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, role, content, retrieved_chunk_ids, message_index,
               message_embedding <=> %s::vector AS dist
        FROM chat_messages
        WHERE chat_id = %s
          AND is_deleted = FALSE
          AND message_embedding IS NOT NULL
        ORDER BY dist ASC
        LIMIT %s
        """,
        (vec, chat_id, max(1, min(int(max_msgs or 5), 12))),
    )
    similar_messages = cursor.fetchall()
    cursor.close()

    collected_chunk_ids = []
    for message in similar_messages:
        refs = message.get("retrieved_chunk_ids") or []
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except json.JSONDecodeError:
                refs = []
        if isinstance(refs, list):
            collected_chunk_ids.extend(str(cid) for cid in refs)

    deduped_chunk_ids = _dedupe_preserve_order(collected_chunk_ids)[: max(1, min(int(max_chunks or 8), 20))]
    hydrated_chunks = _fetch_chunk_context(conn, deduped_chunk_ids) if deduped_chunk_ids else []
    chunk_map = {str(chunk["id"]): chunk for chunk in hydrated_chunks}
    ordered_chunks = [chunk_map[cid] for cid in deduped_chunk_ids if cid in chunk_map]

    lines = []
    if ordered_chunks:
        lines.append("Prior grounded chunks from this chat:")
        for idx, chunk in enumerate(ordered_chunks, 1):
            chunk_type = chunk.get("chunk_type", "unknown")
            page = chunk.get("page_number")
            material_id = chunk.get("material_id")
            header = f"[G{idx}] type={chunk_type} material_id={material_id}"
            if page is not None:
                header += f" page={page}"
            lines.append(header)
            lines.append(chunk.get("chunk_text", ""))
            lines.append("")
    if similar_messages:
        lines.append("Relevant prior chat turns:")
        for message in similar_messages:
            role = message.get("role", "unknown")
            content = (message.get("content", "") or "").strip()
            if len(content) > 400:
                content = content[:400] + "..."
            lines.append(f"- {role}: {content}")

    return {
        "messages": similar_messages,
        "chunks": ordered_chunks,
        "chunk_ids": deduped_chunk_ids,
        "text": "\n".join(lines).strip(),
    }
