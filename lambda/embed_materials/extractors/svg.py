"""
Pass 1 extractor for SVG files using lxml.

XPaths all <text> and <tspan> elements and joins their text content.
Returns an empty list (handler marks job 'skipped') if no text elements found.
"""
from lxml import etree
from typing import List, Dict, Any


def extract_svg(file_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        tree = etree.fromstring(file_bytes)
    except etree.XMLSyntaxError:
        return []

    text_nodes: List[str] = tree.xpath(
        '//*[local-name()="text" or local-name()="tspan"]/text()'
    )

    if not text_nodes:
        return []  # handler will mark job as skipped

    combined = " ".join(t.strip() for t in text_nodes if t.strip())

    chunks: List[Dict[str, Any]] = []
    for block in combined.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        chunks.append({
            "text": block,
            "chunk_type": "text",
            "page_number": None,
            "token_count": len(block.split()),
        })

    # Fallback: if double-newline splitting produced nothing, treat whole text as one chunk
    if not chunks and combined.strip():
        chunks.append({
            "text": combined.strip(),
            "chunk_type": "text",
            "page_number": None,
            "token_count": len(combined.split()),
        })

    return chunks
