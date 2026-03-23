"""
Chunker for: code_file

Splits Python/JS source at function and class boundaries.
"""
import re
from chunkers import ChunkSpec

# Python: def/async def/class at start of line
_PY_RE = re.compile(r'^(?:async\s+)?def\s+\w+|^class\s+\w+', re.MULTILINE)
# JavaScript/TypeScript: function/arrow/class declarations
_JS_RE = re.compile(r'^(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\(|class\s+\w+)', re.MULTILINE)


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

    # Try Python pattern first, then JS
    matches = list(_PY_RE.finditer(full_md))
    if not matches:
        matches = list(_JS_RE.finditer(full_md))

    if not matches:
        # No recognizable code structure — one chunk for the whole file
        return [ChunkSpec(
            text=full_md.strip(),
            visual_page=0,
            chunk_index=0,
            modal_meta={},
        )]

    chunks = []
    preamble = full_md[:matches[0].start()].strip()
    if preamble:
        page = _find_page(preamble, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=preamble,
            visual_page=page,
            chunk_index=0,
            modal_meta={},
        ))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_md)
        text = full_md[start:end].strip()
        if not text:
            continue

        page = _find_page(text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=text,
            visual_page=page,
            chunk_index=i + (1 if preamble else 0),
            modal_meta={},
        ))

    return chunks
