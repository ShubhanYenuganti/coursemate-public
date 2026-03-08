"""
RAG retrieval — embed a query via the embed_query Lambda (boto3 direct invoke),
then run cosine similarity search against material_chunks using pgvector.

Embedding is intentionally offloaded to a separate Lambda (Docker image on ECR)
because sentence-transformers cannot be installed in the Vercel Python runtime.

Required environment variables:
    AWS_ACCESS_KEY_ID       — IAM credentials for the coursemate-s3-uploader user
    AWS_SECRET_ACCESS_KEY   — IAM credentials for the coursemate-s3-uploader user
    AWS_REGION              — (optional) defaults to us-east-1
"""

import json
import os

import boto3

TOP_K = 5

LAMBDA_FUNCTION_NAME = 'embed_query'


def _embed_query(query: str) -> list:
    region = os.environ.get('AWS_REGION', 'us-east-1')
    print(f"[DEBUG] Invoking Lambda '{LAMBDA_FUNCTION_NAME}' in region '{region}'")

    client = boto3.client(
        'lambda',
        region_name=region,
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )

    payload = json.dumps({'query': query})
    print(f"[DEBUG] Lambda invoke payload: {payload}")

    response = client.invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType='RequestResponse',
        Payload=payload,
    )

    print(f"[DEBUG] Lambda StatusCode: {response.get('StatusCode')}")
    print(f"[DEBUG] Lambda FunctionError: {response.get('FunctionError')}")

    raw = response['Payload'].read()
    print(f"[DEBUG] Lambda raw payload response: {raw[:500]}")

    result = json.loads(raw)
    print(f"[DEBUG] Lambda parsed result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

    if response.get('FunctionError'):
        raise RuntimeError(f"Lambda function error: {result}")

    # Lambda handler wraps the response in {statusCode, body}
    if 'body' in result:
        body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        print(f"[DEBUG] Embedding dim: {body.get('dim')}")
        return body['embedding']

    # Direct result (no HTTP wrapper)
    return result['embedding']


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
