"""
Chunker for: quiz, exam

Each question + answer choices is one atomic chunk (never split).
Extracts question number and point value from the text.
"""
import re
from chunkers.base import ChunkSpec

_QUESTION_RE = re.compile(
    r'^(?:Q|Question|Problem)\s*(\d+)\.?|^(\d+)\.',
    re.MULTILINE | re.IGNORECASE,
)
_POINTS_RE = re.compile(r'\((\d+)\s*points?\)', re.IGNORECASE)


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
    matches = list(_QUESTION_RE.finditer(full_md))

    if not matches:
        # No recognizable question structure — treat whole doc as one chunk
        return [ChunkSpec(
            text=full_md.strip(),
            visual_page=0,
            chunk_index=0,
            modal_meta={},
        )]

    chunks = []
    # Preamble before first question
    preamble = full_md[:matches[0].start()].strip()

    for i, m in enumerate(matches):
        num = m.group(1) or m.group(2)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_md)
        text = full_md[start:end].strip()

        points_match = _POINTS_RE.search(text)
        point_value = int(points_match.group(1)) if points_match else None

        # Prepend preamble (header/instructions) to first question only for context
        if i == 0 and preamble:
            text = preamble + "\n\n" + text

        page = _find_page(text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=text,
            visual_page=page,
            chunk_index=i,
            modal_meta={
                "question_number": int(num) if num.isdigit() else num,
                "point_value": point_value,
            },
        ))

    return chunks
