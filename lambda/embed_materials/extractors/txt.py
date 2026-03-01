"""
Pass 1 extractor for plain-text files.

Splits on double newlines; each block becomes chunk_type='text'.
"""
from typing import List, Dict, Any


def extract_txt(file_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    chunks: List[Dict[str, Any]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        chunks.append({
            "text": block,
            "chunk_type": "text",
            "page_number": None,
            "token_count": len(block.split()),
        })

    return chunks
