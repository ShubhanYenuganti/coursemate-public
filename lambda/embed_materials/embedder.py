"""
Voyage AI async embedder for the embed_materials Lambda.

The Python SDK's multimodal_embed accepts:
  - PIL Image objects  (for image inputs)
  - plain str          (for text inputs inside a multimodal sequence)
NOT the REST API dict format {"type": "image_base64", ...}.
"""
import io
import os

import voyageai
from PIL import Image

_vo = None


def _get_client() -> voyageai.AsyncClient:
    global _vo
    if _vo is None:
        _vo = voyageai.AsyncClient(api_key=os.environ['VOYAGE_API_KEY'])
    return _vo


async def embed_visual(png_bytes: bytes) -> list[float]:
    """Embed a page image using voyage-multimodal-3.5 (PIL Image input)."""
    img = Image.open(io.BytesIO(png_bytes))
    vo = _get_client()
    result = await vo.multimodal_embed(
        inputs=[[img]],
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
    """Embed text via voyage-multimodal-3.5 (fallback when image render fails)."""
    if not text or not text.strip():
        return None
    vo = _get_client()
    result = await vo.multimodal_embed(
        inputs=[[text[:2000]]],
        model="voyage-multimodal-3.5",
        input_type="document",
    )
    return result.embeddings[0]
