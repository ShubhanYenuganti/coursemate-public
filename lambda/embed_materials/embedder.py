"""
Cohere Embed v3.5 document embedder for the embed_materials Lambda.
Uses input_type='search_document' for asymmetric retrieval alignment with
query-side input_type='search_query' in embed_query Lambda.
Model is instantiated once at module level so Lambda warm starts reuse it.
"""
import os
from typing import List, Dict, Any

import cohere

_co = None


def _get_client() -> cohere.Client:
    global _co
    if _co is None:
        _co = cohere.Client(os.environ['COHERE_API_KEY'])
    return _co


def embed_chunks(chunks: List[Dict[str, Any]], batch_size: int = 96) -> List[Dict[str, Any]]:
    """
    Add an 'embedding' key (list[float], length 1024) to every chunk dict.
    Processes in batches of 96 (Cohere API maximum per call).
    Returns the same list mutated in-place for memory efficiency.
    """
    client = _get_client()
    texts = [c['text'] for c in chunks]

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embed(
            texts=batch,
            model='embed-english-v3.0',
            input_type='search_document',
        )
        for chunk, vec in zip(chunks[i:i + batch_size], response.embeddings):
            chunk['embedding'] = vec

    return chunks
