"""
Chunker for: reading

Heading-based split (same logic as notes.py) but prefixes each chunk
with the document title and section heading for better retrieval context.
"""
import re
from chunkers.base import ChunkSpec


def _extract_page_breaks(full_md: str) -> list[int]:
    breaks = [0]
    for m in re.finditer(r'^---+$', full_md, re.MULTILINE):
        breaks.append(m.start())
    return breaks


def _find_page(text: str, full_md: str, page_breaks: list[int]) -> int:
    pos = full_md.find(text[:100]) if len(text) >= 100 else full_md.find(text)
    if pos == -1:
        return 0
    for i, bp in enumerate(page_breaks):
        if pos < bp:
            return max(0, i - 1)
    return max(0, len(page_breaks) - 1)


def chunk(pdf_path: str, full_md: str) -> list[ChunkSpec]:
    page_breaks = _extract_page_breaks(full_md)

    # Extract document title (first H1)
    title_match = re.search(r'^#\s+(.+)$', full_md, re.MULTILINE)
    doc_title = title_match.group(1).strip() if title_match else "Reading"

    heading_re = re.compile(r'^(#{1,6}\s+.+)$', re.MULTILINE)
    sections = heading_re.split(full_md)

    chunks = []
    idx = 0

    pairs = []
    if sections[0].strip():
        pairs.append(("", sections[0]))
    for i in range(1, len(sections), 2):
        heading = sections[i]
        content = sections[i + 1] if i + 1 < len(sections) else ""
        pairs.append((heading, content))

    for heading, content in pairs:
        raw_text = (heading + "\n" + content).strip()
        if not raw_text:
            continue

        # Prefix with document title and section heading
        heading_clean = re.sub(r'^#+\s*', '', heading).strip()
        if heading_clean:
            text = f"{doc_title} — {heading_clean}\n\n{content.strip()}"
        else:
            text = raw_text

        page = _find_page(raw_text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=text,
            visual_page=page,
            chunk_index=idx,
            modal_meta={
                "reading_title": doc_title,
                "section_heading": heading_clean,
            },
        ))
        idx += 1

    return chunks
