"""
Embedding helpers for chat message persistence.

This module centralizes embed_query Lambda invocation and updating
`chat_messages.message_embedding` on existing rows.
"""
import json
import os
import logging


logger = logging.getLogger(__name__)


def embed_text_via_lambda(text: str) -> list | None:
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
        logger.warning("embed_query function error for message embedding")
        return None

    raw = response['Payload'].read()
    result = json.loads(raw)
    body = json.loads(result['body']) if 'body' in result else result
    return body.get('text_embedding') or body.get('embedding')


def embed_image_via_lambda(image_bytes: bytes) -> list | None:
    """Invoke embed_query Lambda with image_base64 and return the visual embedding."""
    import base64
    import boto3

    region = os.environ.get('AWS_REGION', 'us-east-1')
    client = boto3.client(
        'lambda',
        region_name=region,
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )

    payload = json.dumps({'image_base64': base64.b64encode(image_bytes).decode('utf-8')})
    response = client.invoke(
        FunctionName='embed_query',
        InvocationType='RequestResponse',
        Payload=payload,
    )

    if response.get('FunctionError'):
        logger.warning("embed_query function error for image embedding")
        return None

    raw = response['Payload'].read()
    result = json.loads(raw)
    body = json.loads(result['body']) if 'body' in result else result
    return body.get('visual_embedding')


def _vec_str(emb: list) -> str:
    return '[' + ','.join(str(x) for x in emb) + ']'


def write_chat_message_embedding(conn, message_id: int, emb: list) -> None:
    """Write vector embedding onto an existing chat_messages row."""
    if not emb:
        return
    vec = _vec_str(emb)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE chat_messages
        SET message_embedding = %s::vector
        WHERE id = %s
    """, (vec, message_id))
    cursor.close()
