"""
Message persistence for conversation grounding.
Stores messages with text embeddings from the embed_query Lambda.
"""
import json
import os


def _embed_via_lambda(text: str) -> list | None:
    """Invoke embed_query Lambda and return the text embedding."""
    import boto3

    region = os.environ.get('AWS_REGION', 'us-east-1')
    client = boto3.client(
        'lambda',
        region_name=region,
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )

    payload = json.dumps({'query': text})
    response = client.invoke(
        FunctionName='embed_query',
        InvocationType='RequestResponse',
        Payload=payload,
    )

    if response.get('FunctionError'):
        return None

    raw = response['Payload'].read()
    result = json.loads(raw)
    body = json.loads(result['body']) if 'body' in result else result
    return body.get('text_embedding') or body.get('embedding')


def _vec_str(emb: list) -> str:
    return '[' + ','.join(str(x) for x in emb) + ']'


def persist_message(conn, session_id: str, role: str, content: str,
                    tool_calls: list = None, grounding_refs: list = None) -> None:
    """
    Insert a message into the `messages` table with a text embedding.
    Non-critical — callers should catch exceptions.
    """
    tool_calls = tool_calls or []
    grounding_refs = grounding_refs or []

    try:
        emb = _embed_via_lambda(content) if content else None
    except Exception:
        emb = None

    cursor = conn.cursor()
    if emb:
        vec = _vec_str(emb)
        cursor.execute("""
            INSERT INTO messages (session_id, role, content, embedding, tool_calls, grounding_refs)
            VALUES (%s, %s, %s, %s::vector, %s, %s)
        """, (session_id, role, content, vec, json.dumps(tool_calls), json.dumps(grounding_refs)))
    else:
        cursor.execute("""
            INSERT INTO messages (session_id, role, content, tool_calls, grounding_refs)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, role, content, json.dumps(tool_calls), json.dumps(grounding_refs)))
    cursor.close()
