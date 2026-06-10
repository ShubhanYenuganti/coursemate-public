import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from unittest.mock import MagicMock
from pageindex_retrieval import _parse_pages, get_page_content, get_course_routing_index, get_material_relations


def test_parse_pages_range():
    assert _parse_pages("5-7") == [5, 6, 7]


def test_parse_pages_comma():
    assert _parse_pages("3,8") == [3, 8]


def test_parse_pages_single():
    assert _parse_pages("12") == [12]


def test_parse_pages_mixed():
    assert _parse_pages("1-3,7") == [1, 2, 3, 7]


def test_parse_pages_invalid_ignored():
    assert _parse_pages("abc") == []


def test_get_page_content_queries_correct_pages():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"page_number": 5, "text_content": "Chain rule derivation", "has_images": False},
    ]
    conn.cursor.return_value = cursor
    rows = get_page_content(conn, material_id=42, pages="5")
    assert len(rows) == 1
    assert rows[0]["page_number"] == 5


def test_get_course_routing_index_formats_output():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {
            "material_id": 1,
            "material_title": "Lecture 5",
            "doc_type": "lecture_slide",
            "page_count": 30,
            "material_summary": "Covers backprop.",
            "metadata_tags": ["backpropagation"],
            "nodes": [
                {"start_page": 1, "end_page": 2, "summary": "Chain rule"},
            ],
        }
    ]
    conn.cursor.return_value = cursor
    results = get_course_routing_index(conn, course_id=10)
    assert len(results) == 1
    assert results[0]["title"] == "Lecture 5"
    assert results[0]["doc_type"] == "lecture_slide"
    section = results[0]["sections"][0]
    assert section["start_page"] == 1
    assert section["end_page"] == 2
    assert section["summary"] == "Chain rule"


def test_get_material_relations_returns_formatted_list():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {
            "source_id": 5, "target_id": 10, "relation_type": "practice_for",
            "shared_tags": ["backpropagation"], "similarity_score": 0.85,
        },
    ]
    conn.cursor.return_value = cursor
    result = get_material_relations(conn, course_id=1, material_id=10)
    assert len(result) == 1
    assert result[0]["relation_type"] == "practice_for"
    assert result[0]["other_material_id"] == 5


def test_get_material_relations_both_directions():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"source_id": 10, "target_id": 20, "relation_type": "extends",
         "shared_tags": [], "similarity_score": 0.7},
    ]
    conn.cursor.return_value = cursor
    result = get_material_relations(conn, course_id=1, material_id=10)
    assert len(result) == 1
    assert result[0]["other_material_id"] == 20


def test_get_page_content_returns_token_count():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"page_number": 1, "text_content": "Intro", "has_images": False, "token_count": 7},
    ]
    conn.cursor.return_value = cursor
    rows = get_page_content(conn, material_id=742, pages="1")
    assert rows[0]["token_count"] == 7


def test_extract_page_summaries_recurses_into_nested_nodes():
    from pageindex_retrieval import _extract_page_summaries

    nodes = [
        {
            "start_page": 1,
            "end_page": 10,
            "summary": "Whole lecture",
            "nodes": [
                {"start_page": 3, "end_page": 4, "summary": "Bellman backup", "nodes": []},
            ],
        },
    ]
    sections = _extract_page_summaries(nodes)
    summaries = [s["summary"] for s in sections]
    assert "Whole lecture" in summaries
    assert "Bellman backup" in summaries


def test_get_page_section_summaries_prefers_deepest_section():
    from pageindex_retrieval import get_page_section_summaries

    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {
            "material_id": 742,
            "material_title": "Lecture 4",
            "nodes": [
                {
                    "start_page": 1,
                    "end_page": 10,
                    "summary": "Whole lecture",
                    "nodes": [
                        {"start_page": 3, "end_page": 4, "summary": "Bellman backup", "nodes": []},
                    ],
                },
            ],
        }
    ]
    conn.cursor.return_value = cursor

    summaries = get_page_section_summaries(conn, [742])

    # Pages inside the nested section get its tighter summary...
    assert summaries[(742, 3)]["summary"] == "Bellman backup"
    assert summaries[(742, 4)]["summary"] == "Bellman backup"
    # ...while other pages keep the parent's.
    assert summaries[(742, 1)]["summary"] == "Whole lecture"
