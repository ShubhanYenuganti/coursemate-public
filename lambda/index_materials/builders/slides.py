import re

from builders.base import IndexNode, MaterialIndex, stable_node_id

_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)
_BODY_LINE_RE = re.compile(r'^(?!#|\s*$).+$', re.MULTILINE)


def _is_section_title_slide(md: str) -> bool:
    if not md.strip():
        return False
    if not _H1_RE.search(md):
        return False
    body_lines = [l for l in _BODY_LINE_RE.findall(md) if l.strip()]
    return len(body_lines) <= 1


def _extract_h1(md: str, fallback: str) -> str:
    m = _H1_RE.search(md)
    return m.group(1).strip() if m else fallback


def build_from_pages(
    pages: list[str],
    doc_type: str = "lecture_slide",
    page_count: int | None = None,
    lecture_title: str = "Lecture",
    section_indices_override: list[int] | None = None,
) -> MaterialIndex:
    if page_count is None:
        page_count = len(pages)

    if section_indices_override is not None:
        section_indices = section_indices_override
    else:
        section_indices = [i for i, md in enumerate(pages) if _is_section_title_slide(md)]

    if not section_indices:
        nodes = []
        for i, md in enumerate(pages):
            if md.strip():
                title = _extract_h1(md, f"Slide {i + 1}")
                nodes.append(IndexNode(
                    node_id=stable_node_id(title, i + 1, i + 1, []),
                    title=title,
                    start_page=i + 1,
                    end_page=i + 1,
                    parent_path=[],
                ))
        return MaterialIndex(title=lecture_title, doc_type=doc_type, page_count=page_count, nodes=nodes)

    nodes = []
    boundaries = section_indices + [page_count]
    for idx, sec_i in enumerate(section_indices):
        sec_end_i = boundaries[idx + 1] - 1
        sec_title = _extract_h1(pages[sec_i], f"Section {idx + 1}")
        children = []
        for p_i in range(sec_i + 1, sec_end_i + 1):
            if p_i < len(pages) and pages[p_i].strip():
                child_title = _extract_h1(pages[p_i], f"Slide {p_i + 1}")
                children.append(IndexNode(
                    node_id=stable_node_id(child_title, p_i + 1, p_i + 1, [sec_title]),
                    title=child_title,
                    start_page=p_i + 1,
                    end_page=p_i + 1,
                    parent_path=[sec_title],
                ))
        nodes.append(IndexNode(
            node_id=stable_node_id(sec_title, sec_i + 1, sec_end_i + 1, []),
            title=sec_title,
            start_page=sec_i + 1,
            end_page=sec_end_i + 1,
            nodes=children,
            parent_path=[],
        ))

    return MaterialIndex(title=lecture_title, doc_type=doc_type, page_count=page_count, nodes=nodes)


def build(pdf_path: str, full_md: str, api_key: str | None = None) -> MaterialIndex:
    import fitz
    import pymupdf4llm
    from hybrid_detector import HybridSectionDetector

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    pages = [pymupdf4llm.to_markdown(doc, pages=[i]).strip() for i in range(page_count)]
    doc.close()

    lecture_title = _extract_h1(pages[0] if pages else "", "Lecture")

    detector = HybridSectionDetector(doc_type="lecture_slide")
    candidates = detector.detect(pdf_path, pages, api_key=api_key)
    section_indices = [c.page_num - 1 for c in candidates]

    return build_from_pages(
        pages,
        doc_type="lecture_slide",
        page_count=page_count,
        lecture_title=lecture_title,
        section_indices_override=section_indices,
    )
