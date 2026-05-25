import re

from builders.base import IndexNode, MaterialIndex, stable_node_id

_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)
_H2_RE = re.compile(r'^##\s+(.+)$', re.MULTILINE)
_H3_RE = re.compile(r'^###\s+(.+)$', re.MULTILINE)
CAPTION_RE = re.compile(
    r"^(Figure|Fig\.|Table|Equation|Eq\.)\s*\d+[:.].+",
    re.IGNORECASE | re.MULTILINE,
)
MAX_PAGES_PER_NODE = 10
MAX_LEAF_PAGES = 2


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


def _window_children(
    title: str,
    start_page: int,
    end_page: int,
    parent_path: list[str],
) -> list[IndexNode]:
    children = []
    page = start_page
    while page <= end_page:
        child_end = min(page + MAX_LEAF_PAGES - 1, end_page)
        child_title = f"{title} pages {page}-{child_end}"
        children.append(IndexNode(
            node_id=stable_node_id(child_title, page, child_end, parent_path + [title]),
            title=child_title,
            start_page=page,
            end_page=child_end,
            node_type="page_window",
            parent_path=parent_path + [title],
            source="fallback_window",
            confidence=0.6,
            evidence_pages=list(range(page, child_end + 1)),
        ))
        page = child_end + 1
    return children


def _caption_nodes(page_text: str, page_num: int, parent_path: list[str]) -> list[IndexNode]:
    nodes = []
    for match in CAPTION_RE.finditer(page_text):
        raw = match.group(0).strip()
        kind = raw.split()[0].lower().rstrip(".")
        if kind in {"figure", "fig"}:
            node_type = "figure"
        elif kind == "table":
            node_type = "table"
        else:
            node_type = "equation"
        nodes.append(IndexNode(
            node_id=stable_node_id(raw, page_num, page_num, parent_path),
            title=raw[:160],
            start_page=page_num,
            end_page=page_num,
            node_type=node_type,
            parent_path=parent_path,
            source="caption_regex",
            confidence=0.9,
            evidence_pages=[page_num],
            char_start=match.start(),
            char_end=match.end(),
        ))
    return nodes


def _section_caption_nodes(
    pages: list[str],
    start_page: int,
    end_page: int,
    parent_path: list[str],
) -> list[IndexNode]:
    nodes = []
    for page_num in range(start_page, end_page + 1):
        nodes.extend(_caption_nodes(pages[page_num - 1], page_num, parent_path))
    return nodes


def build_from_pages(
    pages: list[str],
    doc_type: str = "reading",
    title: str = "Document",
    headings_override: list[tuple[int, str]] | None = None,
) -> MaterialIndex:
    page_count = len(pages)
    headings = headings_override if headings_override is not None else _extract_headings(pages)

    if not headings:
        root = IndexNode(
            node_id=stable_node_id(title, 1, page_count, []),
            title=title,
            start_page=1,
            end_page=page_count,
            parent_path=[],
        )
        if page_count > MAX_LEAF_PAGES:
            root.nodes.extend(_window_children(title, 1, page_count, []))
        root.nodes.extend(_section_caption_nodes(pages, 1, page_count, [title]))
        return MaterialIndex(
            title=title,
            doc_type=doc_type,
            page_count=page_count,
            nodes=[root],
        )

    nodes = []
    boundaries = [h[0] for h in headings] + [page_count]
    for idx, (page_i, heading_title) in enumerate(headings):
        end_i = boundaries[idx + 1] - 1
        start_page = page_i + 1
        end_page = end_i + 1
        span = end_page - start_page + 1
        parent = IndexNode(
            node_id=stable_node_id(heading_title, start_page, end_page, []),
            title=heading_title,
            start_page=start_page,
            end_page=end_page,
            parent_path=[],
            node_type="section",
            source="regex",
            confidence=0.8,
        )
        if span > MAX_LEAF_PAGES:
            parent.nodes.extend(_window_children(heading_title, start_page, end_page, []))
        parent.nodes.extend(
            _section_caption_nodes(pages, start_page, end_page, [heading_title])
        )
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
