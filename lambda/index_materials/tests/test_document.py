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
