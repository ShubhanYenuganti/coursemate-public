import re

from builders.base import IndexNode, MaterialIndex, stable_node_id

_PROBLEM_RE = re.compile(
    r'^(?:Problem|Q\.?|Question)\s+(\d+)',
    re.MULTILINE | re.IGNORECASE,
)
_SUBPART_RE = re.compile(r'^\(([a-z])\)', re.MULTILINE)
_PAGE_SEP_RE = re.compile(r'^---\s*$', re.MULTILINE)


def _find_page(pos: int, page_offsets: list[int]) -> int:
    for i in range(len(page_offsets) - 1, -1, -1):
        if pos >= page_offsets[i]:
            return i + 1
    return 1


def _split_problems(md: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(_PROBLEM_RE.finditer(md))
    if not matches:
        return md, []
    preamble = md[: matches[0].start()]
    problems = []
    for i, m in enumerate(matches):
        num = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        problems.append((num, md[start:end]))
    return preamble, problems


def _split_subparts(text: str) -> list[tuple[str, str]]:
    matches = list(_SUBPART_RE.finditer(text))
    if not matches:
        return []
    parts = []
    for i, m in enumerate(matches):
        letter = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts.append((letter, text[start:end]))
    return parts


def build_from_markdown(full_md: str, doc_type: str, page_count: int) -> MaterialIndex:
    page_offsets = [0] + [m.start() for m in _PAGE_SEP_RE.finditer(full_md)]
    preamble, problems = _split_problems(full_md)

    if not problems:
        return MaterialIndex(
            title=doc_type,
            doc_type=doc_type,
            page_count=page_count,
            nodes=[IndexNode(
                node_id=stable_node_id("Full Document", 1, page_count, []),
                title="Full Document",
                start_page=1,
                end_page=page_count,
                parent_path=[],
            )],
        )

    nodes = []
    for num, text in problems:
        text_start = full_md.find(text)
        start_page = _find_page(text_start if text_start >= 0 else 0, page_offsets)
        subparts = _split_subparts(text)
        children = []
        parent_title = f"Problem {num}"
        for letter, sub_text in subparts:
            sub_start_pos = full_md.find(sub_text)
            sub_page = _find_page(sub_start_pos if sub_start_pos >= 0 else text_start, page_offsets)
            child_title = f"Problem {num}({letter})"
            children.append(IndexNode(
                node_id=stable_node_id(child_title, sub_page, sub_page, [parent_title]),
                title=child_title,
                start_page=sub_page,
                end_page=sub_page,
                parent_path=[parent_title],
            ))
        nodes.append(IndexNode(
            node_id=stable_node_id(parent_title, start_page, start_page, []),
            title=parent_title,
            start_page=start_page,
            end_page=start_page,
            nodes=children,
            parent_path=[],
        ))

    return MaterialIndex(
        title=doc_type,
        doc_type=doc_type,
        page_count=page_count,
        nodes=nodes,
    )


def build(pdf_path: str, full_md: str, doc_type: str = "hw_instruction") -> MaterialIndex:
    import fitz
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    doc.close()
    return build_from_markdown(full_md, doc_type=doc_type, page_count=page_count)
