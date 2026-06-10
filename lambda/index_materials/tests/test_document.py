import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.document import _extract_headings, build_from_pages


def test_extract_headings_finds_h2():
    pages = [
        "## Introduction\nSome text here",
        "Continuation of intro",
        "## Methods\nAnother section",
    ]
    headings = _extract_headings(pages)
    assert len(headings) == 2
    assert headings[0] == (0, "Introduction")
    assert headings[1] == (2, "Methods")


def test_extract_headings_h3_under_h2():
    pages = [
        "## Chapter 1\nIntro",
        "### Section 1.1\nContent",
        "### Section 1.2\nMore content",
    ]
    headings = _extract_headings(pages)
    assert any(t == "Chapter 1" for _, t in headings) or any(t == "Section 1.1" for _, t in headings)


def test_build_from_pages_creates_nodes():
    pages = [
        "## Introduction\nSome content",
        "More content",
        "## Methods\nMethod description",
    ]
    mi = build_from_pages(pages, doc_type="reading", title="My Paper")
    assert mi.doc_type == "reading"
    assert mi.title == "My Paper"
    titles = [n.title for n in mi.nodes]
    assert "Introduction" in titles
    assert "Methods" in titles


def test_build_from_pages_no_headings_single_node():
    pages = [
        "Some text without headings.",
        "More body text.",
    ]
    mi = build_from_pages(pages, doc_type="reading", title="Flat Doc")
    assert len(mi.nodes) == 1
    assert mi.nodes[0].start_page == 1
    assert mi.nodes[0].end_page == 2


def test_build_large_section_split_into_chunks():
    pages = [f"Page {i} content" for i in range(15)]
    pages[0] = "## Big Section\nContent"
    mi = build_from_pages(pages, doc_type="reading", title="Big Doc", headings_override=[(0, "Big Section")])
    assert len(mi.nodes) == 1
    assert len(mi.nodes[0].nodes) > 0


def test_long_section_creates_child_page_windows():
    pages = [f"Page {i}" for i in range(1, 8)]
    pages[0] = "## Long Section\nPage 1"

    mi = build_from_pages(
        pages,
        doc_type="reading",
        title="Paper",
        headings_override=[(0, "Long Section")],
    )

    root = mi.nodes[0]
    assert root.title == "Long Section"
    assert root.nodes
    assert all(child.end_page - child.start_page <= 2 for child in root.nodes)


def test_document_builder_creates_caption_nodes():
    pages = [
        (
            "## Results\nFigure 1: Accuracy by model.\n"
            "Table 1: Dataset statistics.\nEquation 1: y = mx + b."
        ),
    ]

    mi = build_from_pages(pages, doc_type="reading", title="Paper")
    child_types = [child.node_type for node in mi.nodes for child in node.nodes]

    assert "figure" in child_types
    assert "table" in child_types
    assert "equation" in child_types


def test_document_builder_ids_are_stable():
    pages = ["## Intro\nText", "## Methods\nMore text"]
    a = build_from_pages(pages, doc_type="reading", title="Paper").to_dict()
    b = build_from_pages(pages, doc_type="reading", title="Paper").to_dict()
    assert a == b


def test_document_builder_populates_section_summaries_and_keywords():
    pages = [
        (
            "## Sparse Attention\n"
            "Sparse attention restricts token interactions to local and global patterns. "
            "This reduces quadratic memory cost for long documents."
        ),
        "More details about long documents and efficient transformers.",
    ]

    mi = build_from_pages(pages, doc_type="reading", title="Paper")
    node = mi.nodes[0]

    assert "Sparse attention restricts token interactions" in node.summary
    assert "attention" in node.keywords
    assert "documents" in node.keywords


def test_document_builder_populates_page_window_summaries_and_keywords():
    pages = [f"Page {i} discusses retrieval evidence and transformer attention." for i in range(1, 6)]
    pages[0] = "## Long Section\nPage 1 discusses retrieval evidence and transformer attention."

    mi = build_from_pages(
        pages,
        doc_type="reading",
        title="Paper",
        headings_override=[(0, "Long Section")],
    )
    child = mi.nodes[0].nodes[0]

    assert child.node_type == "page_window"
    assert "retrieval evidence" in child.summary
    assert "retrieval" in child.keywords
