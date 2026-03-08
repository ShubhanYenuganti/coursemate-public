"""
RAG retrieval — embed a query via the embed_query Lambda, then run cosine
similarity search against material_chunks using pgvector.

Embedding is intentionally offloaded to a separate Lambda (Docker image on ECR)
because sentence-transformers cannot be installed in the Vercel Python runtime.

Required environment variable:
    EMBED_QUERY_LAMBDA_URL  — Lambda Function URL for the embed_query function
                              e.g. https://<id>.lambda-url.<region>.on.aws/
"""

import json
import os

import requests

TOP_K = 5


def _embed_query(query: str) -> list:
    url = os.environ.get('EMBED_QUERY_LAMBDA_URL')
    if not url:
        raise RuntimeError("EMBED_QUERY_LAMBDA_URL environment variable is not set")

    headers = {'Content-Type': 'application/json'}
    print(f"[DEBUG embed_query] POST {url}")
    print(f"[DEBUG embed_query] Request headers: {headers}")
    resp = requests.post(url, json={'query': query}, headers=headers, timeout=30)
    print(f"[DEBUG embed_query] Response status: {resp.status_code}")
    print(f"[DEBUG embed_query] Response body: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()['embedding']


def retrieve_chunks(conn, query: str, material_ids: list, top_k: int = TOP_K) -> list:
    """
    Embed `query` via the embed_query Lambda, run cosine similarity search
    against material_chunks filtered to `material_ids`, return top_k rows.

    Returns a list of dicts with keys:
        id, chunk_text, chunk_type, page_number, material_id, token_count, similarity
    """
    if not material_ids:
        return []

    vec = _embed_query(query)
    vec_str = '[' + ','.join(str(x) for x in vec) + ']'

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, chunk_text, chunk_type, page_number, material_id, token_count,
               1 - (embedding <=> %s::vector) AS similarity
        FROM   material_chunks
        WHERE  material_id = ANY(%s::int[])
        ORDER  BY embedding <=> %s::vector
        LIMIT  %s
    """, (vec_str, material_ids, vec_str, top_k))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]
