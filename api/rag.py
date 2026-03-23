"""
RAG retrieval — hybrid Voyage AI dual-embedding search with parent-filter re-ranking.

Replaces the previous embed_query Lambda invocation. Calls Voyage AI directly
via the sync voyageai.Client (compatible with Vercel's sync runtime).

Required environment variable:
    VOYAGE_API_KEY  — Voyage AI API key
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TOP_K = 8


def retrieve_chunks(conn, query: str, material_ids: list, top_k: int = TOP_K) -> list:
    """
    Hybrid dual-embedding search over the `chunks` table filtered to `material_ids`.

    Returns a list of dicts with keys compatible with api/llm.py _format_context():
        chunk_text, chunk_type, page_number, similarity, parent_text
    Falls back to legacy `material_chunks` search if no chunks exist yet.
    """
    if not material_ids:
        return []

    # Check if new chunks table has data for these materials
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.material_id = ANY(%s::int[])
        LIMIT 1
    """, (material_ids,))
    has_new_chunks = cursor.fetchone() is not None
    cursor.close()

    if has_new_chunks:
        from services.query.retrieval import hybrid_vector_search
        context, _chunk_ids = hybrid_vector_search(
            conn, query, top_k=top_k, material_ids=material_ids
        )
        return context
    else:
        # Legacy fallback: material_chunks with Lambda embed
        return _legacy_retrieve(conn, query, material_ids, top_k)


def _legacy_retrieve(conn, query: str, material_ids: list, top_k: int) -> list:
    """Legacy retrieval via embed_query Lambda + material_chunks table."""
    import json
    import boto3

    region = os.environ.get('AWS_REGION', 'us-east-1')
    client = boto3.client(
        'lambda',
        region_name=region,
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )

    payload = json.dumps({'query': query})
    response = client.invoke(
        FunctionName='embed_query',
        InvocationType='RequestResponse',
        Payload=payload,
    )

    raw = response['Payload'].read()
    result = json.loads(raw)

    if response.get('FunctionError'):
        raise RuntimeError(f"Lambda function error: {result}")

    if 'body' in result:
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        vec = body['embedding']
    else:
        vec = result['embedding']

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
