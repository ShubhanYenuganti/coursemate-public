"""
Tool execution helpers for the PageIndex agent.

Only the web-search tool remains. The legacy vector-RAG tools
(execute_search_materials / resolve_references_llm / pull_grounding_context /
execute_rerank) were removed together with the chunk/embedding (embed_materials)
pipeline; PageIndex retrieval lives in api/services/query/pageindex_retrieval.py.
"""
import hashlib
import os
import re
import time

import requests

logger = __import__("logging").getLogger(__name__)

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
