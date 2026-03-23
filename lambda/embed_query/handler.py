"""
AWS Lambda handler — embed_query

Accepts a query string and returns its Jina v4 embedding.
Called from api/rag.py on Vercel via boto3 direct invoke.

Input (direct boto3 invoke):
    {"query": "text to embed"}

Output:
    {"embedding": [0.12, ...], "dim": 1024}
"""
import json
import os

import requests

_JINA_URL = "https://api.jina.ai/v1/embeddings"
_DIMS = 1024


def lambda_handler(event, context):
    body = event if isinstance(event, dict) and 'query' in event \
           else json.loads(event.get('body', '{}'))
    query = body.get('query', '')
    if not query:
        return {'statusCode': 400, 'body': json.dumps({'error': 'query required'})}

    resp = requests.post(
        _JINA_URL,
        headers={'Authorization': f"Bearer {os.environ['JINA_API_KEY']}",
                 'Content-Type': 'application/json'},
        json={'model': 'jina-embeddings-v4', 'task': 'retrieval.query',
              'dimensions': _DIMS, 'input': [{'text': query}]},
        timeout=30,
    )
    resp.raise_for_status()
    embedding = resp.json()['data'][0]['embedding']
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'embedding': embedding, 'dim': len(embedding)}),
    }
