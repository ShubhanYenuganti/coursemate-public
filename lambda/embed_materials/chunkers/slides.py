"""
Chunker for: lecture_slide

One chunk per page. Detects lecture title from first H1 heading.
"""
import re
import fitz  # PyMuPDF
import pymupdf4llm

from chunkers import ChunkSpec


def chunk(pdf_path: str, full_md: str) -> list[ChunkSpec]:
    doc = fitz.open(pdf_path)
    chunks = []

    # Try to detect overall title from first page H1
    title_match = re.search(r'^#\s+(.+)$', full_md, re.MULTILINE)
    lecture_title = title_match.group(1).strip() if title_match else ""

    for i in range(len(doc)):
        page_md = pymupdf4llm.to_markdown(doc, pages=[i])
        if not page_md.strip():
            continue

        chunks.append(ChunkSpec(
            text=page_md.strip(),
            visual_page=i,
            chunk_index=i,
            modal_meta={
                "slide_number": i + 1,
                "lecture_title": lecture_title,
            },
        ))

    doc.close()
    return chunks
