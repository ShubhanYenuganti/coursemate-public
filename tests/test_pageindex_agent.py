import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from llm import _format_routing_index_block


def test_format_routing_index_block_basic():
    materials = [
        {
            "material_id": 624,
            "title": "Lecture 1 - Intro",
            "doc_type": "lecture",
            "page_count": 42,
            "summary": "Overview of networking concepts.",
            "tags": ["networking", "intro"],
        },
        {
            "material_id": 625,
            "title": "HW 1",
            "doc_type": "homework",
            "page_count": 5,
            "summary": "Subnetting practice problems.",
            "tags": ["subnetting"],
        },
    ]
    block = _format_routing_index_block(materials)
    assert "<course_materials>" in block
    assert "</course_materials>" in block
    assert "[624]" in block
    assert "[625]" in block
    assert "Lecture 1 - Intro" in block
    assert "lecture" in block
    assert "42p" in block
    assert "networking" in block
    assert "Subnetting practice problems." in block
    assert "[624] Lecture 1 - Intro | lecture | 42p" in block
    assert "tags: networking, intro" in block


def test_format_routing_index_block_empty():
    block = _format_routing_index_block([])
    assert "<course_materials>" in block
    assert "(no materials available)" in block


def test_format_routing_index_block_handles_missing_optional_fields():
    materials = [
        {
            "material_id": 1,
            "title": "T",
            "doc_type": None,
            "page_count": None,
            "summary": None,
            "tags": [],
        }
    ]
    block = _format_routing_index_block(materials)
    assert "[1]" in block
    assert "T" in block
    assert "unknown" in block
    assert "?p" in block
    assert "tags: none" in block
