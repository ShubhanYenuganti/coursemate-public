"""
AWS Lambda handler — embed_query

Embeds a query string using both Voyage AI modalities in a single invocation.

Input (text):  {"query": "text to embed"}
Output: {
    "text_embedding": [...],      # voyage-3.5 text embedding
    "visual_embedding": [...],    # voyage-multimodal-3.5 embedding
    "embedding": [...],           # alias for text_embedding (backward compat)
    "dim": 1024
}

Input (image): {"image_base64": "<base64-encoded PNG or JPEG>"}
Output: {
    "visual_embedding": [...],    # voyage-multimodal-3.5 image embedding
    "dim": 1024
}
"""
import base64
import io
import json
import os

import voyageai
from PIL import Image

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

    image_base64 = body.get('image_base64')
    query = body.get('query', '')

    if image_base64:
        # Image embedding path
        try:
            image_bytes = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            return _error(400, "Invalid image_base64: could not decode or open as image")

        vo = _get_client()
        visual_result = vo.multimodal_embed(
            inputs=[[img]],
            model='voyage-multimodal-3.5',
            input_type='document',
        )
        visual_embedding = visual_result.embeddings[0]

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'visual_embedding': visual_embedding,
                'dim': len(visual_embedding),
            }),
        }

    if not query or not isinstance(query, str):
        return _error(400, "'query' (non-empty string) or 'image_base64' is required")

    vo = _get_client()

    text_result = vo.embed(
        texts=[query],
        model='voyage-3.5',
        input_type='query',
    )
    text_embedding = text_result.embeddings[0]

    visual_result = vo.multimodal_embed(
        inputs=[[query]],
        model='voyage-multimodal-3.5',
        input_type='query',
    )
    visual_embedding = visual_result.embeddings[0]

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'text_embedding': text_embedding,
            'visual_embedding': visual_embedding,
            'embedding': text_embedding,
            'dim': len(text_embedding),
        }),
    }


def _error(status, message):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': message}),
    }
