"""
RAG retrieval — embed a query and run cosine similarity search against material_chunks.
Uses the same model as the Lambda embedder (all-MiniLM-L6-v2, vector dim 384).
"""

TOP_K = 5

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def retrieve_chunks(conn, query: str, material_ids: list, top_k: int = TOP_K) -> list:
    """
    Embed `query`, run cosine similarity search against material_chunks
    filtered to `material_ids`, return top_k rows ordered by similarity.

    Returns a list of dicts with keys:
        id, chunk_text, chunk_type, page_number, material_id, token_count, similarity
    """
    if not material_ids:
        return []

    vec = _get_model().encode(query).tolist()
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
