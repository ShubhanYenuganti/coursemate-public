import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from unittest.mock import MagicMock
from services.query.pageindex_retrieval import _parse_pages, get_page_content, get_course_routing_index, get_material_relations


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
        }
    ]
    conn.cursor.return_value = cursor
    results = get_course_routing_index(conn, course_id=10)
    assert len(results) == 1
    assert results[0]["title"] == "Lecture 5"
    assert results[0]["doc_type"] == "lecture_slide"


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
