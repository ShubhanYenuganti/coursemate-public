"""
Tool execution helpers for agentic chat loops.
"""
import hashlib
import json
import logging
import os
import re
import time

import requests

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

logger = logging.getLogger(__name__)
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_RESOLVER_DEFAULT_MODEL = "gpt-4o-mini"
_RESOLVER_TIMEOUT = 8


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


def _is_enabled(env_name: str, default: bool = False) -> bool:
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _safe_int_env(env_name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(high, value))


def _safe_float_env(env_name: str, default: float) -> float:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _truncate_text(value: str, limit: int = 500) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _entity_match_score(text: str, entities: list[str]) -> float:
    if not entities:
        return 0.0
    hay = (text or "").lower()
    hits = 0
    for entity in entities:
        needle = str(entity or "").strip().lower()
        if needle and needle in hay:
            hits += 1
    return hits / max(len(entities), 1)


def _normalize_weight_map(weights: dict) -> dict:
    total = sum(max(float(v), 0.0) for v in weights.values())
    if total <= 0:
        return dict.fromkeys(weights, 0.0)
    return {k: max(float(v), 0.0) / total for k, v in weights.items()}


def _weight_profile(mode: str) -> dict:
    mode = (mode or "fresh").lower()
    if mode == "followup":
        return _normalize_weight_map(
            {
                "semantic": _safe_float_env("WEIGHT_FOLLOWUP_SEMANTIC", 0.15),
                "anchor": _safe_float_env("WEIGHT_FOLLOWUP_ANCHOR", 0.65),
                "entity": _safe_float_env("WEIGHT_FOLLOWUP_ENTITY", 0.20),
                "recency": _safe_float_env("WEIGHT_FOLLOWUP_RECENCY", 0.05),
            }
        )
    if mode == "mixed":
        return _normalize_weight_map(
            {
                "semantic": _safe_float_env("WEIGHT_MIXED_SEMANTIC", 0.55),
                "anchor": _safe_float_env("WEIGHT_MIXED_ANCHOR", 0.25),
                "entity": _safe_float_env("WEIGHT_MIXED_ENTITY", 0.15),
                "recency": _safe_float_env("WEIGHT_MIXED_RECENCY", 0.05),
            }
        )
    return _normalize_weight_map(
        {
            "semantic": _safe_float_env("WEIGHT_FRESH_SEMANTIC", 0.75),
            "anchor": _safe_float_env("WEIGHT_FRESH_ANCHOR", 0.10),
            "entity": _safe_float_env("WEIGHT_FRESH_ENTITY", 0.10),
            "recency": _safe_float_env("WEIGHT_FRESH_RECENCY", 0.05),
        }
    )


def _fetch_recent_messages(conn, chat_id: int, limit: int = 15) -> list:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, role, content, retrieved_chunk_ids, message_index, created_at
        FROM chat_messages
        WHERE chat_id = %s
          AND is_deleted = FALSE
        ORDER BY message_index DESC
        LIMIT %s
        """,
        (chat_id, max(1, min(int(limit or 15), 30))),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def _fetch_semantic_neighbors(conn, chat_id: int, query_text: str, limit: int = 8) -> list:
    if not embed_text_via_lambda:
        return []
    embedding = embed_text_via_lambda(query_text)
    if not embedding:
        return []
    vec = "[" + ",".join(str(x) for x in embedding) + "]"
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
        (vec, chat_id, max(1, min(int(limit or 8), 20))),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def _extract_known_chunk_ids(messages: list, hydrated_chunk_ids: set[str]) -> list[str]:
    collected = []
    for message in messages:
        refs = message.get("retrieved_chunk_ids") or []
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except json.JSONDecodeError:
                refs = []
        if isinstance(refs, list):
            for cid in refs:
                scid = str(cid)
                if scid in hydrated_chunk_ids:
                    collected.append(scid)
    return _dedupe_preserve_order(collected)


def _default_resolver_output(current_query: str) -> dict:
    return {
        "intent_type": "fresh",
        "resolved_query": current_query,
        "resolved_entities": [],
        "required_entities": [],
        "required_entities_source_turn": None,
        "carryover_chunk_ids": [],
        "confidence": 0.0,
        "reasoning_brief": "fallback resolver output",
    }


def resolve_references_llm(
    conn,
    chat_id: int | None,
    current_query: str,
    selected_material_ids: list | None,
    api_key: str | None,
    model: str | None = None,
) -> dict:
    """
    LLM-based reference resolver for indirect follow-up turns.
    """
    cleaned_query = (current_query or "").strip()
    if not cleaned_query:
        return _default_resolver_output("")
    if not _is_enabled("GROUNDING_RESOLVER_ENABLED", default=True):
        return _default_resolver_output(cleaned_query)
    if not chat_id or not api_key:
        return _default_resolver_output(cleaned_query)

    recent = _fetch_recent_messages(conn, chat_id, limit=_safe_int_env("GROUNDING_RECENT_LIMIT", 12, 4, 25))
    semantic = _fetch_semantic_neighbors(conn, chat_id, cleaned_query, limit=_safe_int_env("GROUNDING_SEMANTIC_LIMIT", 8, 3, 20))
    recent_ids = {row.get("id") for row in recent}
    merged_messages = list(recent) + [row for row in semantic if row.get("id") not in recent_ids]

    all_refs = []
    for row in merged_messages:
        refs = row.get("retrieved_chunk_ids") or []
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except json.JSONDecodeError:
                refs = []
        if isinstance(refs, list):
            all_refs.extend(str(cid) for cid in refs)
    all_refs = _dedupe_preserve_order(all_refs)[:30]
    hydrated = _fetch_chunk_context(conn, all_refs) if (_fetch_chunk_context and all_refs) else []
    hydrated_ids = {str(c.get("id")) for c in hydrated}

    payload = {
        "current_query": cleaned_query,
        "selected_material_ids": selected_material_ids or [],
        "chat_slice_recent": [
            {
                "role": row.get("role"),
                "message_index": row.get("message_index"),
                "content": _truncate_text(row.get("content", ""), 420),
            }
            for row in recent
        ],
        "chat_slice_semantic": [
            {
                "role": row.get("role"),
                "message_index": row.get("message_index"),
                "distance": row.get("dist"),
                "content": _truncate_text(row.get("content", ""), 320),
            }
            for row in semantic
        ],
        "prior_grounding_refs": all_refs[:20],
        "hydrated_grounding_chunks": [
            {
                "id": str(chunk.get("id")),
                "chunk_type": chunk.get("chunk_type"),
                "material_id": chunk.get("material_id"),
                "excerpt": _truncate_text(chunk.get("chunk_text", ""), 240),
            }
            for chunk in hydrated[:20]
        ],
    }

    resolver_prompt = (
        "You are a reference resolver for follow-up questions in a chat RAG system.\n"
        "Resolve indirect references like 'those two algorithms' into explicit entities.\n"
        "Return strict JSON with these keys:\n"
        "  intent_type (followup|fresh|mixed),\n"
        "  resolved_query (string),\n"
        "  resolved_entities (array of strings),\n"
        "  required_entities (array of strings — see below),\n"
        "  required_entities_source_turn (integer or null — see below),\n"
        "  carryover_chunk_ids (array of ids),\n"
        "  confidence (0..1 float),\n"
        "  reasoning_brief (one sentence).\n\n"
        "required_entities: Populate this when the user is explicitly asking about items that were\n"
        "enumerated in a prior assistant turn (e.g. 'these methods', 'those N algorithms',\n"
        "'the ones you listed', 'amongst these'). Scan ALL messages in chat_slice_recent —\n"
        "the referenced enumeration may not be in the immediately preceding turn; it could be\n"
        "from several turns back. Identify which assistant turn contains the numbered/bulleted\n"
        "list the user most plausibly means, then extract the exact item names from that list.\n"
        "Max 12 items. Leave empty [] for fresh queries or when no prior turn contains a\n"
        "relevant explicit enumeration.\n\n"
        "required_entities_source_turn: The 0-based index into chat_slice_recent of the\n"
        "assistant turn you extracted required_entities from. Set to null if required_entities\n"
        "is empty.\n\n"
        "Only include carryover_chunk_ids that appear in provided hydrated_grounding_chunks.\n"
    )
    resolver_model = model or _RESOLVER_DEFAULT_MODEL

    try:
        response = requests.post(
            _OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": resolver_model,
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": resolver_prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=_safe_int_env("GROUNDING_RESOLVER_TIMEOUT_SEC", _RESOLVER_TIMEOUT, 3, 15),
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception:
        logger.exception("resolve_references_llm_failed", extra={"chat_id": chat_id})
        return _default_resolver_output(cleaned_query)

    intent_type = str(parsed.get("intent_type", "fresh")).lower()
    if intent_type not in ("followup", "fresh", "mixed"):
        intent_type = "fresh"
    resolved_query = str(parsed.get("resolved_query", "")).strip() or cleaned_query
    entities = parsed.get("resolved_entities") or []
    if not isinstance(entities, list):
        entities = []
    entities = _dedupe_preserve_order([str(e).strip() for e in entities if str(e).strip()])[:8]

    carryover = parsed.get("carryover_chunk_ids") or []
    if not isinstance(carryover, list):
        carryover = []
    carryover = _dedupe_preserve_order([str(cid) for cid in carryover if str(cid) in hydrated_ids])[:20]
    carryover = _extract_known_chunk_ids(merged_messages, hydrated_ids) if not carryover else carryover

    required = parsed.get("required_entities") or []
    if not isinstance(required, list):
        required = []
    required = _dedupe_preserve_order([str(e).strip() for e in required if str(e).strip()])[:12]

    required_source_turn = parsed.get("required_entities_source_turn")
    if required_source_turn is not None:
        try:
            required_source_turn = int(required_source_turn)
        except (TypeError, ValueError):
            required_source_turn = None

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    reasoning_brief = _truncate_text(str(parsed.get("reasoning_brief", "")).strip(), 220) or "resolver output"

    return {
        "intent_type": intent_type,
        "resolved_query": resolved_query,
        "resolved_entities": entities,
        "required_entities": required,
        "required_entities_source_turn": required_source_turn,
        "carryover_chunk_ids": carryover,
        "confidence": confidence,
        "reasoning_brief": reasoning_brief,
    }


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


def execute_search_materials(
    conn,
    query: str,
    material_ids: list,
    top_k: int = 8,
    mode: str = "fresh",
    anchor_chunk_ids: list | None = None,
    resolved_entities: list | None = None,
    chat_id: int | None = None,
) -> dict:
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
    mode = (mode or "fresh").lower()
    if mode not in ("followup", "fresh", "mixed"):
        mode = "fresh"
    anchor_chunk_ids = _dedupe_preserve_order(anchor_chunk_ids or [])
    resolved_entities = _dedupe_preserve_order(resolved_entities or [])

    if not cleaned_query:
        return {
            "text": "Search query is empty; provide a non-empty query.",
            "chunk_ids": [],
            "meta": {"tool": "search_materials", "query": "", "result_count": 0, "latency_ms": 0},
        }

    all_fresh = retrieve_chunks(conn, cleaned_query, scoped_material_ids, top_k=safe_top_k, chat_id=chat_id)
    chat_image_chunks = [c for c in all_fresh if c.get('chunk_type') == 'chat_image']
    fresh_chunks = [c for c in all_fresh if c.get('chunk_type') != 'chat_image']
    carryover_chunks = _fetch_chunk_context(conn, anchor_chunk_ids) if (_fetch_chunk_context and anchor_chunk_ids) else []

    anchor_set = {str(cid) for cid in anchor_chunk_ids}
    recency_rank = {str(cid): idx for idx, cid in enumerate(anchor_chunk_ids)}
    weights = _weight_profile(mode)

    scored = {}
    min_carryover_hits = _safe_int_env("GROUNDING_MIN_CARRYOVER_HITS", 5, 1, 10)
    for chunk in fresh_chunks:
        cid = _chunk_id(chunk.get("id"))
        semantic_score = max(0.0, min(1.0, float(chunk.get("similarity", 0) or 0)))
        anchor_score = 1.0 if cid in anchor_set else 0.0
        entity_score = _entity_match_score(chunk.get("chunk_text", ""), resolved_entities)
        if cid in recency_rank and len(recency_rank) > 1:
            recency_score = 1.0 - (recency_rank[cid] / (len(recency_rank) - 1))
        elif cid in recency_rank:
            recency_score = 1.0
        else:
            recency_score = 0.0
        fused = (
            weights["semantic"] * semantic_score
            + weights["anchor"] * anchor_score
            + weights["entity"] * entity_score
            + weights["recency"] * recency_score
        )
        chunk["fused_score"] = fused
        chunk["source_branch"] = "fresh"
        scored[cid] = chunk

    for chunk in carryover_chunks:
        cid = _chunk_id(chunk.get("id"))
        semantic_score = max(0.0, min(1.0, float(chunk.get("similarity", 0.55) or 0.55)))
        anchor_score = 1.0 if cid in anchor_set else 0.0
        entity_score = _entity_match_score(chunk.get("chunk_text", ""), resolved_entities)
        if cid in recency_rank and len(recency_rank) > 1:
            recency_score = 1.0 - (recency_rank[cid] / (len(recency_rank) - 1))
        elif cid in recency_rank:
            recency_score = 1.0
        else:
            recency_score = 0.0
        fused = (
            weights["semantic"] * semantic_score
            + weights["anchor"] * anchor_score
            + weights["entity"] * entity_score
            + weights["recency"] * recency_score
        )
        chunk["fused_score"] = fused
        chunk["source_branch"] = "carryover"
        if cid not in scored or fused > scored[cid].get("fused_score", -1):
            scored[cid] = chunk

    merged = sorted(scored.values(), key=lambda c: c.get("fused_score", 0), reverse=True)
    if mode == "followup" and anchor_chunk_ids:
        carryover_sorted = [c for c in merged if _chunk_id(c.get("id")) in anchor_set]
        if len(carryover_sorted) >= min_carryover_hits:
            remaining = [c for c in merged if _chunk_id(c.get("id")) not in anchor_set]
            merged = carryover_sorted + remaining

    chunks = merged[:safe_top_k]
    chunk_ids = _dedupe_preserve_order([_chunk_id(c.get("id")) for c in chunks if c.get("id") is not None])
    latency_ms = int((time.time() - started) * 1000)

    def _five_words(text):
        words = (text or "").split()
        return " ".join(words[:5]) + ("..." if len(words) > 5 else "")

    top_chunks_preview = [
        {"material_id": c.get("material_id"), "snippet": _five_words(c.get("chunk_text", ""))}
        for c in chunks[:3]
    ]

    return {
        "text": _format_search_payload(cleaned_query, chunks),
        "chunk_ids": chunk_ids,
        "chunks": top_chunks_preview,
        "chat_image_chunks": chat_image_chunks,
        "meta": {
            "tool": "search_materials",
            "mode": mode,
            "query": cleaned_query,
            "result_count": len(chunks),
            "material_scope_count": len(scoped_material_ids),
            "top_k": safe_top_k,
            "carryover_count": len([c for c in chunks if c.get("source_branch") == "carryover"]),
            "fresh_count": len([c for c in chunks if c.get("source_branch") == "fresh"]),
            "weights": weights,
            "latency_ms": latency_ms,
        },
    }


_TAVILY_URL = "https://api.tavily.com/search"


def execute_web_search(conn, query: str, ttl_seconds: int = 3600) -> dict:
    """
    Web search tool with cache-first logic using web_cache table.
    Falls back to Tavily API on cache miss.
    """
    enabled = os.environ.get("AGENTIC_WEB_SEARCH_ENABLED", "false").lower() == "true"
    query_hash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()

    if not enabled:
        return {
            "text": "Web search is disabled in this environment.",
            "chunk_ids": [],
            "meta": {"tool": "web_search", "enabled": False, "query_hash": query_hash},
        }

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return {
            "text": "Web search unavailable: TAVILY_API_KEY not configured.",
            "chunk_ids": [],
            "meta": {"tool": "web_search", "enabled": True, "error": "missing_api_key"},
        }

    # Cache lookup
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT snippet FROM web_cache
                WHERE query_hash = %s
                  AND fetched_at + (ttl_seconds * interval '1 second') > NOW()
                LIMIT 1
                """,
                (query_hash,),
            )
            row = cur.fetchone()
        if row:
            cached_text = row[0]
            cached_urls = [
                {"url": m.group(1), "title": m.group(1)}
                for m in re.finditer(r'\[W\d+\] url=(\S+)', cached_text or "")
            ]
            return {
                "text": cached_text,
                "chunk_ids": [],
                "meta": {"tool": "web_search", "query": query, "cache_hit": True, "urls": cached_urls},
            }
    except Exception:
        pass  # Cache read failure is non-fatal; proceed to live search

    # Cache miss — call Tavily
    started = time.time()
    try:
        resp = requests.post(
            _TAVILY_URL,
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {
            "text": f"Web search failed: {exc}",
            "chunk_ids": [],
            "meta": {"tool": "web_search", "query": query, "error": str(exc)},
        }

    latency_ms = int((time.time() - started) * 1000)
    results = data.get("results", [])

    # Format results
    lines = [f"Web search results for query: '{query}'"]
    for i, r in enumerate(results, 1):
        snippet = (r.get("content") or "")[:300]
        lines.append(f"[W{i}] url={r.get('url', '')}\n{snippet}")
    result_text = "\n\n".join(lines)

    # Concatenate all snippets for storage (single row per query_hash)
    stored_snippet = result_text

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO web_cache (query_hash, url, snippet, fetched_at, ttl_seconds)
                VALUES (%s, %s, %s, NOW(), %s)
                ON CONFLICT (query_hash) DO UPDATE
                    SET snippet = EXCLUDED.snippet,
                        fetched_at = EXCLUDED.fetched_at,
                        ttl_seconds = EXCLUDED.ttl_seconds
                """,
                (query_hash, results[0].get("url", "") if results else "", stored_snippet, ttl_seconds),
            )
        conn.commit()
    except Exception:
        pass  # Cache write failure is non-fatal

    urls = [
        {"url": r.get("url", ""), "title": r.get("title", "") or r.get("url", "")}
        for r in results
        if r.get("url")
    ]

    return {
        "text": result_text,
        "chunk_ids": [],
        "meta": {
            "tool": "web_search",
            "query": query,
            "result_count": len(results),
            "latency_ms": latency_ms,
            "cache_hit": False,
            "urls": urls,
        },
    }


_VOYAGE_RERANK_URL = "https://api.voyageai.com/v1/rerank"


def execute_rerank(conn, query: str, chunk_ids: list, top_n: int = 5) -> dict:
    """
    Rerank candidate chunks using Voyage rerank-2 model.
    Accepts chunk UUIDs from a prior search_materials call, fetches their text,
    calls Voyage rerank, and returns the top_n chunks in relevance order.
    """
    enabled = os.environ.get("AGENTIC_RERANK_ENABLED", "false").lower() == "true"
    if not enabled:
        return {
            "text": "Rerank is disabled in this environment.",
            "chunk_ids": chunk_ids or [],
            "meta": {"tool": "rerank_results", "enabled": False},
        }

    if not chunk_ids:
        return {
            "text": "No chunk IDs provided to rerank.",
            "chunk_ids": [],
            "meta": {"tool": "rerank_results", "error": "no_chunk_ids"},
        }

    api_key = os.environ.get("VOYAGE_API_KEY", "")
    if not api_key:
        return {
            "text": "Rerank unavailable: VOYAGE_API_KEY not configured.",
            "chunk_ids": chunk_ids,
            "meta": {"tool": "rerank_results", "error": "missing_api_key"},
        }

    if not _fetch_chunk_context:
        return {
            "text": "Rerank unavailable: chunk context fetcher not loaded.",
            "chunk_ids": chunk_ids,
            "meta": {"tool": "rerank_results", "error": "missing_fetch_context"},
        }

    # Fetch chunk texts
    try:
        rows = _fetch_chunk_context(conn, list(chunk_ids))
    except Exception as exc:
        return {
            "text": f"Rerank failed to fetch chunks: {exc}",
            "chunk_ids": chunk_ids,
            "meta": {"tool": "rerank_results", "error": "fetch_failed"},
        }

    if not rows:
        return {
            "text": "Rerank found no chunks for given IDs.",
            "chunk_ids": [],
            "meta": {"tool": "rerank_results", "error": "chunks_not_found"},
        }

    # Build ordered doc list aligned to rows
    documents = [r.get("chunk_text") or r.get("content") or "" for r in rows]
    safe_top_n = min(top_n, len(rows))

    started = time.time()
    try:
        resp = requests.post(
            _VOYAGE_RERANK_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "rerank-2",
                "query": query,
                "documents": documents,
                "top_k": safe_top_n,
                "return_documents": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        # Graceful fallback: return original order truncated to top_n
        fallback_ids = _dedupe_preserve_order([_chunk_id(r.get("id")) for r in rows])[:safe_top_n]
        return {
            "text": f"Rerank API failed ({exc}); returning original order.",
            "chunk_ids": fallback_ids,
            "meta": {"tool": "rerank_results", "error": str(exc), "fallback": True},
        }

    latency_ms = int((time.time() - started) * 1000)

    # Map Voyage result indices back to rows
    reranked = sorted(data.get("data", []), key=lambda x: x.get("relevance_score", 0), reverse=True)
    reranked_rows = []
    for item in reranked:
        idx = item.get("index")
        if idx is not None and 0 <= idx < len(rows):
            row = dict(rows[idx])
            row["similarity"] = float(item.get("relevance_score", 0))
            reranked_rows.append(row)

    chunk_ids_out = _dedupe_preserve_order([_chunk_id(r.get("id")) for r in reranked_rows if r.get("id")])

    return {
        "text": _format_search_payload(query, reranked_rows),
        "chunk_ids": chunk_ids_out,
        "meta": {
            "tool": "rerank_results",
            "query": query,
            "input_count": len(rows),
            "result_count": len(reranked_rows),
            "top_n": safe_top_n,
            "latency_ms": latency_ms,
        },
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
        SELECT id, role, content, retrieved_chunk_ids, message_index, created_at,
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
        "query_embedding": query_embedding,
    }
