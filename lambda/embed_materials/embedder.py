"""
Voyage AI async embedder for the embed_materials Lambda.

Provides two embedding functions:
- embed_visual: voyage-multimodal-3.5 for image/page embeddings
- embed_text:   voyage-3.5 for text embeddings
"""
import base64
import os
import voyageai

_vo = None


def _get_client() -> voyageai.AsyncClient:
    global _vo
    if _vo is None:
        _vo = voyageai.AsyncClient(api_key=os.environ['VOYAGE_API_KEY'])
    return _vo


async def embed_visual(png_bytes: bytes) -> list[float]:
    """Embed a page image using voyage-multimodal-3.5."""
    b64 = base64.standard_b64encode(png_bytes).decode()
    vo = _get_client()
    result = await vo.multimodal_embed(
        inputs=[[{"type": "image_base64", "image_base64": f"data:image/png;base64,{b64}"}]],
        model="voyage-multimodal-3.5",
        input_type="document",
    )
    return result.embeddings[0]


async def embed_text(text: str) -> list[float] | None:
    """Embed text using voyage-3.5. Returns None for empty text."""
    if not text or not text.strip():
        return None
    vo = _get_client()
    result = await vo.embed(
        texts=[text],
        model="voyage-3.5",
        input_type="document",
    )
    return result.embeddings[0]


async def embed_visual_text(text: str) -> list[float] | None:
    """Embed text using voyage-multimodal-3.5 (for parent visual embedding)."""
    if not text or not text.strip():
        return None
    vo = _get_client()
    result = await vo.multimodal_embed(
        inputs=[[{"type": "text", "text": text[:2000]}]],
        model="voyage-multimodal-3.5",
        input_type="document",
    )
    return result.embeddings[0]
