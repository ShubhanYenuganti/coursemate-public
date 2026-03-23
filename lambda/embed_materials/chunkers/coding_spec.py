"""
Chunker for: coding_spec

Splits at numbered milestone/requirement boundaries.
"""
import re
from chunkers.base import ChunkSpec

_MILESTONE_RE = re.compile(
    r'^##\s*(Milestone|Requirement|Req\.?)\s*([\d\.]+)',
    re.MULTILINE | re.IGNORECASE,
)


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
    matches = list(_MILESTONE_RE.finditer(full_md))

    if not matches:
        # Fall back to heading-based split
        from chunkers.notes import chunk as notes_chunk
        return notes_chunk(pdf_path, full_md)

    chunks = []
    preamble = full_md[:matches[0].start()].strip()
    if preamble:
        page = _find_page(preamble, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=preamble,
            visual_page=page,
            chunk_index=0,
            modal_meta={"milestone_id": "preamble"},
        ))

    for i, m in enumerate(matches):
        req_type = m.group(1)
        req_id   = m.group(2)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_md)
        text = full_md[start:end].strip()

        page = _find_page(text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=text,
            visual_page=page,
            chunk_index=i + (1 if preamble else 0),
            modal_meta={
                "milestone_id": req_id,
                "requirement_id": f"{req_type} {req_id}",
            },
        ))

    return chunks
