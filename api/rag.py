"""
RAG retrieval — embed a query via the embed_query Lambda (boto3 direct invoke),
then run dual-index cosine similarity search against material_chunks using pgvector.

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

TOP_K = 10
PARENT_SEARCH_K = 20

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
    Embed `query` via the embed_query Lambda, run dual-index cosine similarity search
    against material_chunks filtered to `material_ids`, return top_k re-ranked rows.

    Returns a list of dicts with keys:
        id, chunk_text, chunk_type, page_number, material_id, token_count,
        source_type, section_title, week, problem_id, related_chunk_ids,
        parent_id, parent_text, similarity, (optionally linked_context)
    """
    if not material_ids:
        return []

    vec = _embed_query(query)
    vec_str = '[' + ','.join(str(x) for x in vec) + ']'

    cursor = conn.cursor()

    # Step 1: parent search → get top-PARENT_SEARCH_K parent chunk IDs + similarities
    cursor.execute("""
        SELECT id, 1 - (embedding <=> %s::vector) AS similarity
        FROM material_chunks
        WHERE material_id = ANY(%s::int[]) AND is_parent = TRUE
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (vec_str, material_ids, vec_str, PARENT_SEARCH_K))
    parent_hits = {r['id']: r['similarity'] for r in cursor.fetchall()}

    # If no parents exist yet (e.g. legacy flat chunks), fall back to flat search
    if not parent_hits:
        cursor.execute("""
            SELECT id, chunk_text, chunk_type, page_number, material_id, token_count,
                   source_type, section_title, week, problem_id, related_chunk_ids,
                   parent_id, 1 - (embedding <=> %s::vector) AS similarity
            FROM material_chunks
            WHERE material_id = ANY(%s::int[])
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (vec_str, material_ids, vec_str, top_k))
        rows = cursor.fetchall()
        cursor.close()
        results = []
        for r in rows:
            row = dict(r)
            row['parent_text'] = ''
            results.append(row)
        return results

    # Step 2: child search — only children whose parent is in parent_hits
    parent_id_list = list(parent_hits.keys())
    cursor.execute("""
        SELECT id, chunk_text, chunk_type, page_number, material_id, token_count,
               source_type, section_title, week, problem_id, related_chunk_ids,
               parent_id, 1 - (embedding <=> %s::vector) AS child_sim
        FROM material_chunks
        WHERE material_id = ANY(%s::int[])
          AND is_parent = FALSE
          AND parent_id = ANY(%s::int[])
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (vec_str, material_ids, parent_id_list, vec_str, PARENT_SEARCH_K))
    children = cursor.fetchall()

    # Step 3: re-rank with combined parent + child similarity
    reranked = []
    for c in children:
        parent_sim = parent_hits.get(c['parent_id'], 0)
        score = c['child_sim'] * 0.6 + parent_sim * 0.4
        reranked.append({**dict(c), 'similarity': score})
    reranked.sort(key=lambda x: x['similarity'], reverse=True)

    # Step 4: fetch parent text for top results
    results = []
    fetched_parent_texts = {}
    for c in reranked[:top_k]:
        pid = c['parent_id']
        if pid and pid not in fetched_parent_texts:
            cursor.execute("SELECT chunk_text FROM material_chunks WHERE id = %s", (pid,))
            row = cursor.fetchone()
            fetched_parent_texts[pid] = row['chunk_text'] if row else ''
        c['parent_text'] = fetched_parent_texts.get(pid, '')
        results.append(c)

    # Step 5: assessment special case — fetch linked lecture/hw chunk for quiz/exam results
    assessment_types = {'quiz', 'exam'}
    for c in results:
        if c.get('source_type') in assessment_types and c.get('related_chunk_ids'):
            related_ids = c['related_chunk_ids']
            if related_ids:
                cursor.execute("""
                    SELECT id, chunk_text, source_type
                    FROM material_chunks
                    WHERE id = ANY(%s::int[])
                      AND source_type IN ('lecture_note', 'hw_instruction')
                    LIMIT 1
                """, (related_ids,))
                linked = cursor.fetchone()
                if linked:
                    c['linked_context'] = dict(linked)

    cursor.close()
    return results
