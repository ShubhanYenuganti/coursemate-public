"""
AWS Lambda handler — embed_query (legacy)

Embeds a query string using Voyage AI voyage-3.5.
Still called by api/rag.py as a fallback for old material_chunks data.

Input:  {"query": "text to embed"}
Output: {"embedding": [0.12, ...], "dim": 1024}
"""
import json
import os

import voyageai

_vo = None


def _get_client() -> voyageai.Client:
    global _vo
    if _vo is None:
        _vo = voyageai.Client(api_key=os.environ['VOYAGE_API_KEY'])
    return _vo


def lambda_handler(event, context):
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except (json.JSONDecodeError, TypeError):
            return _error(400, "Invalid JSON body")
    else:
        body = event

    query = body.get('query', '')
    if not query or not isinstance(query, str):
        return _error(400, "'query' (non-empty string) is required")

    result = _get_client().embed(
        texts=[query],
        model='voyage-3.5',
        input_type='query',
    )
    embedding = result.embeddings[0]

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'embedding': embedding, 'dim': len(embedding)}),
    }


def _error(status, message):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': message}),
    }
