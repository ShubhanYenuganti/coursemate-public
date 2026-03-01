"""
Sentence-transformers wrapper. Model is loaded once at module level so Lambda
warm starts reuse the in-memory model without re-loading from disk.
"""
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def embed_chunks(chunks: List[Dict[str, Any]], batch_size: int = 64) -> List[Dict[str, Any]]:
    """
    Add an 'embedding' key (list[float], length 384) to every chunk dict.
    Returns the same list mutated in-place for memory efficiency.
    """
    model = _get_model()
    texts = [c['text'] for c in chunks]
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    for chunk, vec in zip(chunks, embeddings):
        chunk['embedding'] = vec.tolist()
    return chunks
