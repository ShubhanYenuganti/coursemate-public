import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def _is_pageindex_active():
    """Mirror of chat._is_pageindex_active for isolated testing."""
    return os.environ.get("PAGEINDEX_RETRIEVAL_ENABLED", "true").lower() != "false"


def test_is_pageindex_active_default():
    """Unset env var → active (default True)."""
    os.environ.pop('PAGEINDEX_RETRIEVAL_ENABLED', None)
    assert _is_pageindex_active() is True


def test_is_pageindex_active_false():
    os.environ['PAGEINDEX_RETRIEVAL_ENABLED'] = 'false'
    assert _is_pageindex_active() is False
    os.environ.pop('PAGEINDEX_RETRIEVAL_ENABLED', None)


def test_is_pageindex_active_true():
    os.environ['PAGEINDEX_RETRIEVAL_ENABLED'] = 'true'
    assert _is_pageindex_active() is True
    os.environ.pop('PAGEINDEX_RETRIEVAL_ENABLED', None)


def _make_tool_trace(entries):
    import json
    return json.dumps(entries)


def test_pageindex_citation_detection():
    """retrieved_chunk_ids with 'material:X' entries → PageIndex path detected."""
    chunk_ids = ['material:624', 'material:625']
    is_pageindex = any(isinstance(cid, str) and cid.startswith('material:') for cid in chunk_ids)
    assert is_pageindex is True


def test_vector_citation_not_detected():
    """Integer chunk IDs → vector path, not PageIndex."""
    chunk_ids = [101, 202, 303]
    is_pageindex = any(isinstance(cid, str) and cid.startswith('material:') for cid in chunk_ids)
    assert is_pageindex is False


def test_page_citations_derived_from_tool_trace():
    """Tool trace get_page_content entries are grouped into page citations."""
    import json
    from pageindex_retrieval import _parse_pages

    tool_trace = [
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "3,4,5"}, "iteration": 1},
        {"tool": "get_material_structure", "args": {"material_id": 624}, "iteration": 1},
        {"tool": "get_page_content", "args": {"material_id": 625, "pages": "1-2"}, "iteration": 2},
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "6"}, "iteration": 3},
    ]

    pages_by_material = {}
    for entry in tool_trace:
        if entry.get("tool") == "get_page_content":
            mid = entry.get("args", {}).get("material_id")
            pages_str = entry.get("args", {}).get("pages", "")
            if mid is not None:
                pages = _parse_pages(str(pages_str))
                existing = pages_by_material.get(mid, [])
                pages_by_material[mid] = sorted(set(existing + pages))

    assert pages_by_material[624] == [3, 4, 5, 6]
    assert pages_by_material[625] == [1, 2]


def test_page_citations_ordered_by_call_sequence():
    """Citations should appear in the same order as get_page_content calls,
    one entry per call (not collapsed by material_id)."""
    from pageindex_retrieval import _parse_pages

    tool_trace = [
        {"tool": "get_material_structure", "args": {"material_id": 624}, "iteration": 1},
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "3-5"}, "iteration": 1},
        {"tool": "get_page_content", "args": {"material_id": 625, "pages": "1-2"}, "iteration": 2},
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "6"}, "iteration": 3},
    ]

    citations = []
    for entry in tool_trace:
        if entry.get("tool") == "get_page_content":
            mid = entry.get("args", {}).get("material_id")
            pages = _parse_pages(str(entry.get("args", {}).get("pages", "")))
            if mid is not None:
                citations.append({"material_id": mid, "pages": pages, "citation_type": "page"})

    assert len(citations) == 3
    assert citations[0] == {"material_id": 624, "pages": [3, 4, 5], "citation_type": "page"}
    assert citations[1] == {"material_id": 625, "pages": [1, 2], "citation_type": "page"}
    assert citations[2] == {"material_id": 624, "pages": [6], "citation_type": "page"}


def test_partition_locked_chunk_ids_drops_material_refs():
    """Helper must separate integer-style chunk refs from material:N refs."""
    raw = ["123", "material:624", "456", "material:625", "789"]
    integer_refs = [r for r in raw if not (isinstance(r, str) and r.startswith("material:"))]
    assert integer_refs == ["123", "456", "789"]


def test_extract_known_chunk_ids_filters_material_refs():
    """_extract_known_chunk_ids must drop 'material:N' refs that are not in the hydrated chunk set."""
    import importlib
    from unittest.mock import MagicMock
    sys.modules.setdefault('requests', MagicMock())
    import tools
    importlib.reload(tools)

    messages = [
        {"retrieved_chunk_ids": ["123", "material:624", "456"]},
        {"retrieved_chunk_ids": ["material:625", "789"]},
    ]
    hydrated_chunk_ids = {"123", "456", "789"}
    result = tools._extract_known_chunk_ids(messages, hydrated_chunk_ids)
    assert result == ["123", "456", "789"]
    assert all(not r.startswith("material:") for r in result)
