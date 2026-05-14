import re
import uuid

from builders.base import IndexNode, MaterialIndex

_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)
_H2_RE = re.compile(r'^##\s+(.+)$', re.MULTILINE)
_H3_RE = re.compile(r'^###\s+(.+)$', re.MULTILINE)
MAX_PAGES_PER_NODE = 10


def make_id() -> str:
    return uuid.uuid4().hex[:8]


def _extract_headings(pages: list[str]) -> list[tuple[int, str]]:
    """Return list of (0-based page index, title) for H2/H3 headings, fallback to H1."""
    headings = []
    seen_pages = set()
    for i, md in enumerate(pages):
        for m in _H3_RE.finditer(md):
            headings.append((i, m.group(1).strip()))
            seen_pages.add(i)
        for m in _H2_RE.finditer(md):
            if i not in seen_pages:
                headings.append((i, m.group(1).strip()))
                seen_pages.add(i)
    if not headings:
        for i, md in enumerate(pages):
            for m in _H1_RE.finditer(md):
                headings.append((i, m.group(1).strip()))
    return sorted(headings, key=lambda h: h[0])


def build_from_pages(
    pages: list[str],
    doc_type: str = "reading",
    title: str = "Document",
    headings_override: list[tuple[int, str]] | None = None,
) -> MaterialIndex:
    page_count = len(pages)
    headings = headings_override if headings_override is not None else _extract_headings(pages)

    if not headings:
        return MaterialIndex(
            title=title,
            doc_type=doc_type,
            page_count=page_count,
            nodes=[IndexNode(
                node_id=make_id(),
                title=title,
                start_page=1,
                end_page=page_count,
            )],
        )

    nodes = []
    boundaries = [h[0] for h in headings] + [page_count]
    for idx, (page_i, heading_title) in enumerate(headings):
        end_i = boundaries[idx + 1] - 1
        span = end_i - page_i + 1
        if span <= MAX_PAGES_PER_NODE:
            nodes.append(IndexNode(
                node_id=make_id(),
                title=heading_title,
                start_page=page_i + 1,
                end_page=end_i + 1,
            ))
        else:
            parent = IndexNode(
                node_id=make_id(),
                title=heading_title,
                start_page=page_i + 1,
                end_page=end_i + 1,
            )
            for chunk_start in range(page_i, end_i + 1, MAX_PAGES_PER_NODE):
                chunk_end = min(chunk_start + MAX_PAGES_PER_NODE - 1, end_i)
                parent.nodes.append(IndexNode(
                    node_id=make_id(),
                    title=f"{heading_title} (pp. {chunk_start + 1}–{chunk_end + 1})",
                    start_page=chunk_start + 1,
                    end_page=chunk_end + 1,
                ))
            nodes.append(parent)

    return MaterialIndex(title=title, doc_type=doc_type, page_count=page_count, nodes=nodes)


def build(pdf_path: str, full_md: str, doc_type: str = "reading", api_key: str | None = None) -> MaterialIndex:
    import fitz
    import pymupdf4llm
    from hybrid_detector import HybridSectionDetector

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    pages = [pymupdf4llm.to_markdown(doc, pages=[i]).strip() for i in range(page_count)]
    doc.close()

    title = ""
    h1 = _H1_RE.search(pages[0] if pages else "")
    if h1:
        title = h1.group(1).strip()

    detector = HybridSectionDetector(doc_type=doc_type)
    candidates = detector.detect(pdf_path, pages, api_key=api_key)

    if candidates:
        headings = [(c.page_num - 1, c.text) for c in candidates]
    else:
        headings = _extract_headings(pages)

    return build_from_pages(pages, doc_type=doc_type, title=title or "Document", headings_override=headings)
