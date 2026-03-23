"""
Chunker for: general, lecture_note, discussion_note

Splits markdown at heading boundaries. Merges indivisible blocks
(equations, worked examples) into their enclosing section.
"""
import re
from chunkers import ChunkSpec

# Indivisible block patterns
_EQUATION_RE  = re.compile(r'^\$\$', re.MULTILINE)
_EXAMPLE_RE   = re.compile(r'^(Example|Proof|Solution|Lemma|Theorem|Definition):', re.MULTILINE | re.IGNORECASE)


def _find_page(text: str, full_md: str, page_breaks: list[int]) -> int:
    """Return the 0-based page index where `text` first appears in full_md."""
    pos = full_md.find(text[:100]) if len(text) >= 100 else full_md.find(text)
    if pos == -1:
        return 0
    for i, bp in enumerate(page_breaks):
        if pos < bp:
            return max(0, i - 1)
    return max(0, len(page_breaks) - 1)


def _extract_page_breaks(full_md: str) -> list[int]:
    """Return character positions of page-break markers (e.g. '---' lines)."""
    breaks = [0]
    for m in re.finditer(r'^---+$', full_md, re.MULTILINE):
        breaks.append(m.start())
    return breaks


def chunk(pdf_path: str, full_md: str) -> list[ChunkSpec]:
    page_breaks = _extract_page_breaks(full_md)

    # Split at headings (##+ lines)
    heading_re = re.compile(r'^(#{1,6}\s+.+)$', re.MULTILINE)
    sections = heading_re.split(full_md)

    # sections alternates: [pre-heading, heading, content, heading, content, ...]
    chunks = []
    idx = 0

    # Collect (heading, content) pairs
    pairs = []
    if sections[0].strip():
        pairs.append(("", sections[0]))
    for i in range(1, len(sections), 2):
        heading = sections[i]
        content = sections[i + 1] if i + 1 < len(sections) else ""
        pairs.append((heading, content))

    # Check for indivisible blocks and merge with previous section
    merged_pairs = []
    for heading, content in pairs:
        combined = heading + content
        is_indivisible = bool(_EQUATION_RE.search(combined)) or bool(_EXAMPLE_RE.search(combined))
        if is_indivisible and merged_pairs:
            prev_h, prev_c = merged_pairs[-1]
            merged_pairs[-1] = (prev_h, prev_c + "\n" + combined)
        else:
            merged_pairs.append((heading, content))

    for heading, content in merged_pairs:
        text = (heading + "\n" + content).strip()
        if not text:
            continue
        page = _find_page(text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=text,
            visual_page=page,
            chunk_index=idx,
            modal_meta={},
        ))
        idx += 1

    return chunks
