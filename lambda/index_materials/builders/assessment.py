import re
import uuid

from builders.base import IndexNode, MaterialIndex
from builders.problems import _split_problems, _find_page, _PAGE_SEP_RE

_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)
_ANSWER_KEY_RE = re.compile(r'\[ANSWER_KEY\]', re.IGNORECASE)


def make_id() -> str:
    return uuid.uuid4().hex[:8]


def build_from_markdown(full_md: str, doc_type: str, page_count: int) -> MaterialIndex:
    page_offsets = [0] + [m.start() for m in _PAGE_SEP_RE.finditer(full_md)]
    _, problems = _split_problems(full_md)

    if not problems:
        return MaterialIndex(
            title=doc_type,
            doc_type=doc_type,
            page_count=page_count,
            nodes=[IndexNode(
                node_id=make_id(),
                title="Full Assessment",
                start_page=1,
                end_page=page_count,
                nodes=[],
            )],
        )

    nodes = []
    for num, text in problems:
        text_start = full_md.find(text)
        start_page = _find_page(text_start if text_start >= 0 else 0, page_offsets)
        is_answer_key = bool(_ANSWER_KEY_RE.search(text))
        title = f"Answer Key – Question {num}" if is_answer_key else f"Question {num}"
        nodes.append(IndexNode(
            node_id=make_id(),
            title=title,
            start_page=start_page,
            end_page=start_page,
            nodes=[],
        ))

    return MaterialIndex(
        title=doc_type,
        doc_type=doc_type,
        page_count=page_count,
        nodes=nodes,
    )


def build(pdf_path: str, full_md: str, doc_type: str = "quiz") -> MaterialIndex:
    import fitz
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    doc.close()
    return build_from_markdown(full_md, doc_type=doc_type, page_count=page_count)
