"""
Jina v4 multimodal embedder for the embed_materials Lambda.
Uses task='retrieval.passage' for document-side embedding.
For visual source types (slide, quiz, exam), renders PDF pages as JPEG and sends images.
For text types, sends chunk_text directly.
"""
import os
import base64
import requests
import fitz  # PyMuPDF — already in requirements

_JINA_URL = "https://api.jina.ai/v1/embeddings"
_DIMS = 1024
_VISUAL_TYPES = {'slide', 'quiz', 'exam'}


def _render_page_jpeg(pdf_bytes: bytes, page_number: int) -> str:
    """Render one PDF page (1-indexed) to base64 JPEG."""
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    page = doc[page_number - 1]
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes('jpeg')
    doc.close()
    return base64.b64encode(img_bytes).decode()


def _jina_request(inputs: list) -> list:
    resp = requests.post(
        _JINA_URL,
        headers={'Authorization': f"Bearer {os.environ['JINA_API_KEY']}",
                 'Content-Type': 'application/json'},
        json={'model': 'jina-embeddings-v4', 'task': 'retrieval.passage',
              'dimensions': _DIMS, 'input': inputs},
        timeout=120,
    )
    resp.raise_for_status()
    return [d['embedding'] for d in resp.json()['data']]


def embed_chunks(chunks: list, source_type: str, pdf_bytes: bytes = None,
                 batch_size: int = 32) -> list:
    """
    Embed chunks via Jina v4.
    - For visual source types with pdf_bytes: render page_numbers[0] as JPEG.
    - Otherwise: send chunk_text as text.
    Returns chunks with 'embedding' key added in-place.
    """
    use_visual = source_type in _VISUAL_TYPES and pdf_bytes is not None

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        inputs = []
        for c in batch:
            if use_visual and c.get('page_numbers'):
                b64 = _render_page_jpeg(pdf_bytes, c['page_numbers'][0])
                inputs.append({'type': 'image_url',
                                'image_url': {'url': f"data:image/jpeg;base64,{b64}"}})
            else:
                inputs.append({'text': c['chunk_text']})
        embeddings = _jina_request(inputs)
        for chunk, vec in zip(batch, embeddings):
            chunk['embedding'] = vec

    return chunks
