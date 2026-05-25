from experiments.rag_page_index_eval.agentic_adapter import (
    QasperPageIndexAdapter,
    fetched_locations_from_tool_trace,
)
from experiments.rag_page_index_eval.types import PageRecord, QueryExample


def _adapter():
    pages = [
        PageRecord("paper-a", 1, "intro text", "Intro", ("Intro",)),
        PageRecord("paper-a", 2, "sparse attention evidence", "Method", ("Method",)),
        PageRecord("paper-b", 1, "rnn evidence", "Background", ("Background",)),
    ]
    queries = [
        QueryExample("q1", "paper-a", "what attention?", {2}, metadata={"title": "Paper A"}),
        QueryExample("q2", "paper-b", "what model?", {1}, metadata={"title": "Paper B"}),
    ]
    return QasperPageIndexAdapter(pages, queries)


def test_adapter_exposes_course_routing_index_in_production_shape():
    adapter = _adapter()

    rows = adapter.get_course_routing_index(conn=None, course_id=1)

    assert rows[0]["material_id"] == 1
    assert rows[0]["title"] == "Paper A"
    assert rows[0]["page_count"] == 2
    assert rows[0]["sections"][0]["start_page"] == 1
    assert rows[0]["sections"][0]["end_page"] == 1
    assert rows[0]["sections"][0]["summary"].startswith("Intro: intro text")
    assert "keywords:" in rows[0]["sections"][0]["summary"]
    assert rows[1]["material_id"] == 2


def test_adapter_fetches_page_content_with_material_and_page_spec():
    adapter = _adapter()

    rows = adapter.get_page_content(conn=None, material_id=1, pages="2-3")

    assert rows == [
        {
            "page_number": 2,
            "text_content": "sparse attention evidence",
            "has_images": False,
        }
    ]


def test_adapter_returns_material_structure_nodes():
    adapter = _adapter()

    structure = adapter.get_material_structure(conn=None, material_id=1)

    assert structure["material_id"] == 1
    assert structure["paper_id"] == "paper-a"
    assert structure["nodes"][0]["title"] == "Intro"
    assert structure["nodes"][0]["source"] in {"regex", "fallback_window"}
    assert structure["nodes"][1]["start_page"] == 2
    assert structure["nodes"][1]["keywords"]


def test_adapter_routing_sections_include_builder_keywords_and_summaries():
    adapter = _adapter()

    rows = adapter.get_course_routing_index(conn=None, course_id=1, material_ids=[1])

    assert rows[0]["sections"][0]["summary"].startswith("Intro:")
    assert "keywords:" in rows[0]["sections"][1]["summary"]
    assert "sparse" in rows[0]["sections"][1]["summary"]


def test_fetched_locations_from_tool_trace_preserves_tool_order_and_uniqueness():
    adapter = _adapter()
    trace = [
        {"tool": "get_material_structure", "args": {"material_id": 1}},
        {"tool": "get_page_content", "args": {"material_id": 1, "pages": "2,1"}},
        {"tool": "get_page_content", "args": {"material_id": 1, "pages": "2"}},
        {"tool": "get_page_content", "args": {"material_id": 2, "pages": "1"}},
    ]

    locations = fetched_locations_from_tool_trace(trace, adapter, limit=5)

    assert locations == [("paper-a", 2), ("paper-a", 1), ("paper-b", 1)]
