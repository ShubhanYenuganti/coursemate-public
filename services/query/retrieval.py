"""
Hybrid vector search using pre-computed dual embeddings (visual + text).

Embeddings are computed externally (embed_query Lambda) and passed in.
Implements RRF merge + parent-filter re-ranking.
"""


def _vec_str(emb: list) -> str:
    return '[' + ','.join(str(x) for x in emb) + ']'


def _search_chunks(conn, emb: list, retrieval_type: str, limit: int, material_ids=None) -> list:
    vec = _vec_str(emb)
    mat_filter = "AND d.material_id = ANY(%s::int[])" if material_ids else ""
    params = [vec, retrieval_type]
    if material_ids:
        params.append(material_ids)
    params.append(vec)
    params.append(limit)

    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT c.id, c.content, c.retrieval_type, c.parent_id, c.chunk_index,
               c.modal_meta, c.source_type, c.problem_id,
               (c.embedding <=> %s::vector) AS distance
        FROM   chunks c
        JOIN   documents d ON d.id = c.document_id
        WHERE  c.is_parent = false
          AND  c.retrieval_type = %s
          {mat_filter}
        ORDER  BY c.embedding <=> %s::vector
        LIMIT  %s
    """, params)
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def _search_parent_chunks(conn, emb: list, limit: int, material_ids=None) -> list:
    vec = _vec_str(emb)
    mat_filter = "AND d.material_id = ANY(%s::int[])" if material_ids else ""
    params = [vec]
    if material_ids:
        params.append(material_ids)
    params.append(vec)
    params.append(limit)

    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT c.id, c.content, c.retrieval_type,
               (c.embedding <=> %s::vector) AS distance
        FROM   chunks c
        JOIN   documents d ON d.id = c.document_id
        WHERE  c.is_parent = true
          {mat_filter}
        ORDER  BY c.embedding <=> %s::vector
        LIMIT  %s
    """, params)
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def _reciprocal_rank_fusion(vis_hits: list, txt_hits: list, k: int = 60) -> list:
    scores = {}
    docs = {}
    for rank, row in enumerate(vis_hits):
        rid = str(row['id'])
        scores[rid] = scores.get(rid, 0) + 1 / (k + rank + 1)
        docs[rid] = row
    for rank, row in enumerate(txt_hits):
        rid = str(row['id'])
        scores[rid] = scores.get(rid, 0) + 1 / (k + rank + 1)
        docs[rid] = row
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [docs[rid] for rid, _ in ranked]


def _fetch_chunk_context(conn, chunk_ids: list) -> list:
    if not chunk_ids:
        return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.content AS chunk_text, c.retrieval_type AS chunk_type,
               c.chunk_index AS page_number, c.modal_meta, c.source_type,
               p.content AS parent_text,
               d.material_id
        FROM   chunks c
        LEFT JOIN chunks p ON p.id = c.parent_id
        LEFT JOIN documents d ON d.id = c.document_id
        WHERE  c.id = ANY(%s::uuid[])
    """, (chunk_ids,))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def hybrid_vector_search(conn, vis_emb: list, txt_emb: list, top_k: int = 8,
                         material_ids=None):
    """
    Dual-embedding hybrid search with parent-filter re-ranking.

    Accepts pre-computed embeddings (from embed_query Lambda).
    Returns (context_rows, chunk_ids) where context_rows is a list of dicts
    compatible with api/llm.py _format_context().
    """
    # 1. Search child chunks for both retrieval types
    vis_hits = _search_chunks(conn, vis_emb, "visual", top_k * 2, material_ids)
    txt_hits = _search_chunks(conn, txt_emb, "text",   top_k * 2, material_ids)

    # 3. RRF merge
    merged = _reciprocal_rank_fusion(vis_hits, txt_hits)[:top_k]

    # 4. Parallel parent search (top-20 by text embedding)
    parent_hits = _search_parent_chunks(conn, txt_emb, 20, material_ids)
    valid_parent_ids = {str(r['id']) for r in parent_hits}
    parent_sim_map   = {str(r['id']): 1 - r['distance'] for r in parent_hits}

    # 5. Filter: keep only children whose parent is in top-20
    filtered = [r for r in merged if r.get('parent_id') and str(r['parent_id']) in valid_parent_ids]
    if not filtered:
        filtered = merged  # fallback: use all merged results

    # 6. Re-rank: child_sim * 0.6 + parent_sim * 0.4
    for r in filtered:
        child_sim  = 1 - r['distance']
        parent_sim = parent_sim_map.get(str(r.get('parent_id')), 0)
        r['combined_score'] = child_sim * 0.6 + parent_sim * 0.4
    filtered.sort(key=lambda r: r['combined_score'], reverse=True)

    # 7. Fetch full context rows (with parent text)
    top = filtered[:top_k]
    chunk_ids = [str(r['id']) for r in top]
    context = _fetch_chunk_context(conn, chunk_ids)

    # Add similarity for downstream use
    score_map = {str(r['id']): r.get('combined_score', 0) for r in top}
    for row in context:
        row['similarity'] = score_map.get(str(row['id']), 0)

    return context, chunk_ids
