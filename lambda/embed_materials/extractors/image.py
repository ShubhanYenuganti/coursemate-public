"""
Pass 1 extractor for JPEG, PNG, and GIF files via pytesseract OCR.

For GIF only frame 0 is processed.
Chunks shorter than MIN_CHUNK_CHARS characters are dropped as OCR noise.
"""
from PIL import Image
import pytesseract
from io import BytesIO
from typing import List, Dict, Any

MIN_CHUNK_CHARS = 30


def extract_image(file_bytes: bytes) -> List[Dict[str, Any]]:
    image = Image.open(BytesIO(file_bytes))

    # GIF: process only the first frame
    if getattr(image, "n_frames", 1) > 1:
        image.seek(0)

    raw_text: str = pytesseract.image_to_string(image, lang="eng")

    chunks: List[Dict[str, Any]] = []
    for block in raw_text.split("\n\n"):
        block = block.strip()
        if len(block) < MIN_CHUNK_CHARS:
            continue
        chunks.append({
            "text": block,
            "chunk_type": "ocr",
            "page_number": None,
            "token_count": len(block.split()),
        })

    return chunks
