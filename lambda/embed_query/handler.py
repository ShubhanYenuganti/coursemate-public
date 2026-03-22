"""
AWS Lambda handler — embed_query

Accepts a query string and returns its Cohere embedding.
Called from api/rag.py on Vercel via boto3 direct invoke.

Input (direct boto3 invoke):
    {"query": "text to embed"}

Output:
    {"embedding": [0.12, ...], "dim": 1024}
"""
import json
import os

import cohere

_co = None


def _get_client() -> cohere.Client:
    global _co
    if _co is None:
        _co = cohere.Client(os.environ['COHERE_API_KEY'])
    return _co


def lambda_handler(event, context):
    # Support both Function URL invocation (body is a JSON string) and
    # direct boto3 invoke (event is already the parsed dict).
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

    response = _get_client().embed(
        texts=[query],
        model='embed-english-v3.0',
        input_type='search_query',
    )
    embedding = response.embeddings[0]

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
