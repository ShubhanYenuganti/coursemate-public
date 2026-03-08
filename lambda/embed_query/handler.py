"""
AWS Lambda handler — embed_query

Accepts a query string and returns its sentence-transformer embedding.
Called from api/rag.py on Vercel via a Lambda Function URL.

Input (Function URL or direct invoke):
    {"query": "text to embed"}

Output:
    {"embedding": [0.12, ...], "dim": 384}
"""
import json

from sentence_transformers import SentenceTransformer

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


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

    embedding = _get_model().encode(query).tolist()

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
