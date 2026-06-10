import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.slides import _is_section_title_slide, _extract_h1, build_from_pages


def test_title_only_slide_detected():
    assert _is_section_title_slide("# Backpropagation\n") is True


def test_content_slide_not_section():
    md = "# Slide Title\n\nLet x = Wx + b\n\nThis is a derivation step.\n\nAnother line."
    assert _is_section_title_slide(md) is False


def test_empty_slide_not_section():
    assert _is_section_title_slide("") is False


def test_no_h1_not_section():
    assert _is_section_title_slide("## Subsection\nSome content") is False


def test_build_groups_slides_under_sections():
    pages = [
        "# Lecture 5: Backpropagation",
        "# Section 1: Chain Rule",
        "## Chain Rule\n\ndy/dx = dy/du * du/dx",
        "## Another Slide\n\nMore derivation.",
        "# Section 2: SGD",
        "## SGD Update\n\nθ = θ - η∇L",
    ]
    mi = build_from_pages(pages, doc_type="lecture_slide", page_count=6, lecture_title="Lecture 5")
    assert len(mi.nodes) >= 2
    section_titles = [n.title for n in mi.nodes]
    assert any("Section 1" in t or "Chain Rule" in t for t in section_titles)


def test_build_no_sections_flat():
    pages = [
        "# Intro\n\nSome intro content here.",
        "# Slide 2\n\nAnother content slide.",
    ]
    mi = build_from_pages(pages, doc_type="lecture_slide", page_count=2, lecture_title="Lecture")
    assert mi.page_count == 2
    assert all(n.nodes == [] for n in mi.nodes)


def test_build_section_indices_override():
    pages = [
        "# Root Slide",
        "## Content A",
        "# New Section",
        "## Content B",
    ]
    mi = build_from_pages(
        pages,
        doc_type="lecture_slide",
        page_count=4,
        lecture_title="Lecture",
        section_indices_override=[0, 2],
    )
    assert len(mi.nodes) == 2
    assert mi.nodes[0].start_page == 1
    assert mi.nodes[1].start_page == 3


def test_slides_builder_ids_are_stable():
    pages = [
        "# Section 1",
        "## Content A",
        "# Section 2",
        "## Content B",
    ]
    a = build_from_pages(
        pages,
        doc_type="lecture_slide",
        page_count=4,
        lecture_title="Lecture",
        section_indices_override=[0, 2],
    ).to_dict()
    b = build_from_pages(
        pages,
        doc_type="lecture_slide",
        page_count=4,
        lecture_title="Lecture",
        section_indices_override=[0, 2],
    ).to_dict()
    assert a == b


def test_slides_builder_populates_summaries_keywords_and_policy():
    pages = [
        "# Optimization",
        "## Gradient Descent\n\nUpdates parameters with learning rate and gradient.",
    ]

    mi = build_from_pages(
        pages,
        doc_type="lecture_slide",
        page_count=2,
        lecture_title="Lecture",
        section_indices_override=[0],
    )

    d = mi.to_dict()
    assert d["retrieval_policy"]["mode"] == "structure_first"
    assert "Optimization" in mi.nodes[0].summary
    assert "optimization" in mi.nodes[0].keywords
    assert "gradient" in mi.nodes[0].nodes[0].keywords
