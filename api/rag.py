"""
RAG retrieval — hybrid dual-embedding search with parent-filter re-ranking.

Embeddings are computed by invoking the embed_query Lambda (no voyageai in Vercel).
Required environment variables:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TOP_K = 8


def _invoke_embed_query(query: str):
    """Invoke the embed_query Lambda and return (vis_emb, txt_emb)."""
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
    else:
        body = result

    return body['visual_embedding'], body['text_embedding']


def retrieve_chunks(conn, query: str, material_ids: list, top_k: int = TOP_K) -> list:
    """
    Hybrid dual-embedding search over the `chunks` table filtered to `material_ids`.

    Returns a list of dicts with keys compatible with api/llm.py _format_context():
        chunk_text, chunk_type, page_number, similarity, parent_text
    """
    if not material_ids:
        return []

    from services.query.retrieval import hybrid_vector_search
    vis_emb, txt_emb = _invoke_embed_query(query)
    context, _chunk_ids = hybrid_vector_search(
        conn, vis_emb, txt_emb, top_k=top_k, material_ids=material_ids
    )
    return context
