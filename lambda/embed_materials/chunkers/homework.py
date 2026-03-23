"""
Chunker for: hw_instruction, hw_solution

Splits at problem/question boundaries. For hw_instruction, prepends
the preamble to each problem chunk.
"""
import re
from chunkers.base import ChunkSpec

_PROBLEM_RE = re.compile(
    r'^(?:Problem|Question|Part|Exercise)\s+(\d+[\.\w]*)|^(\d+)[\.\)]',
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


def _split_problems(full_md: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Returns (preamble, [(problem_number, problem_text), ...]).
    """
    matches = list(_PROBLEM_RE.finditer(full_md))
    if not matches:
        return full_md, []

    preamble = full_md[:matches[0].start()].strip()
    problems = []
    for i, m in enumerate(matches):
        num = m.group(1) or m.group(2)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_md)
        text = full_md[start:end].strip()
        problems.append((num, text))

    return preamble, problems


def chunk_instruction(pdf_path: str, full_md: str) -> list[ChunkSpec]:
    page_breaks = _extract_page_breaks(full_md)
    preamble, problems = _split_problems(full_md)
    chunks = []
    idx = 0

    if preamble:
        page = _find_page(preamble, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=preamble,
            visual_page=page,
            chunk_index=idx,
            modal_meta={"problem_number": "preamble"},
        ))
        idx += 1

    for num, text in problems:
        # Prepend preamble for context
        combined = (preamble + "\n\n" + text).strip() if preamble else text
        page = _find_page(text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=combined,
            visual_page=page,
            chunk_index=idx,
            modal_meta={"problem_number": num},
            problem_id=str(num),
        ))
        idx += 1

    return chunks


def chunk_solution(pdf_path: str, full_md: str) -> list[ChunkSpec]:
    page_breaks = _extract_page_breaks(full_md)
    preamble, problems = _split_problems(full_md)
    chunks = []
    idx = 0

    if preamble:
        page = _find_page(preamble, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=preamble,
            visual_page=page,
            chunk_index=idx,
            modal_meta={"problem_number": "preamble"},
        ))
        idx += 1

    for num, text in problems:
        page = _find_page(text, full_md, page_breaks)
        chunks.append(ChunkSpec(
            text=text,
            visual_page=page,
            chunk_index=idx,
            modal_meta={"problem_number": num},
            problem_id=str(num),
        ))
        idx += 1

    return chunks
