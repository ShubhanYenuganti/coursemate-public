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


def test_format_routing_index_block_with_sections():
    materials = [
        {
            "material_id": 1,
            "title": "Lecture 1",
            "doc_type": "lecture_slide",
            "page_count": 10,
            "summary": "Intro lecture.",
            "tags": [],
            "sections": [
                {"start_page": 1, "end_page": 1, "summary": "overview of the course"},
                {"start_page": 2, "end_page": 4, "summary": "TCP slow start and AIMD"},
                {"start_page": 5, "end_page": 5, "summary": "congestion window mechanics"},
            ],
        }
    ]
    block = _format_routing_index_block(materials)
    assert "pages:" in block
    assert "1:overview of the course" in block
    assert "2-4:TCP slow start and AIMD" in block
    assert "5:congestion window mechanics" in block


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


import json
from unittest.mock import patch, MagicMock


def _stub_openai_response_no_tools(content: str = "All done.") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ]
    }
    return resp


def test_run_agent_pageindex_preloads_routing_and_drops_search_tool():
    """The agent should receive the routing index in the system prompt
    and the search_course_materials tool should not be exposed."""
    from llm import run_agent_pageindex

    conn = MagicMock()

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _stub_openai_response_no_tools(
            '{"reply": "ok", "summary": "ok", "follow_ups": [], "clarifying_question": null}'
        )

    routing_rows = [
        {
            "material_id": 10,
            "title": "L1",
            "doc_type": "lecture",
            "page_count": 5,
            "summary": "s",
            "tags": ["t"],
            "sections": [
                {"start_page": 1, "end_page": 1, "summary": "intro to networking basics"},
                {"start_page": 2, "end_page": 3, "summary": "TCP handshake and connection setup"},
            ],
        }
    ]

    with patch("llm.requests.post", side_effect=fake_post), \
         patch("pageindex_retrieval.get_course_routing_index", return_value=routing_rows):
        run_agent_pageindex(
            conn=conn,
            user_message="What is in lecture 1?",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=None,
            course_id=7,
            context_material_ids=[10],
        )

    payload = captured["payload"]
    system_msg = payload["messages"][0]
    assert system_msg["role"] == "system"
    assert "<course_materials>" in system_msg["content"]
    assert "[10]" in system_msg["content"]
    assert "search_materials" not in system_msg["content"]
    assert "pages:" in system_msg["content"]
    assert "intro to networking basics" in system_msg["content"]

    tool_names = [t["function"]["name"] for t in payload["tools"]]
    assert "search_course_materials" not in tool_names
    assert "get_material_structure" in tool_names
    assert "get_page_content" in tool_names
    assert "get_related_materials" in tool_names


def test_pageindex_prompt_documents_citation_numbering():
    """PAGEINDEX_SYSTEM_PROMPT must explain how [N] markers map to fetched pages."""
    from llm import PAGEINDEX_SYSTEM_PROMPT
    text = PAGEINDEX_SYSTEM_PROMPT.lower()
    assert "get_page_content" in text
    assert ("order" in text and "call" in text) or "nth call" in text, \
        "Prompt must instruct agent to use call-order for citation numbers"


def test_pageindex_prompt_prefers_high_recall_fetching():
    """PageIndex prompt should bias the agent toward recall over minimal fetching."""
    from llm import PAGEINDEX_SYSTEM_PROMPT
    text = PAGEINDEX_SYSTEM_PROMPT.lower()
    assert "prefer recall" in text
    assert "2-4" in text and "candidate" in text
    assert "neighboring" in text
    assert "get_material_structure" in text and "conceptual" in text


def test_pageindex_prompt_requires_structure_first_for_broad_questions():
    """Broad/conceptual PageIndex questions should require structure inspection before answering."""
    from llm import PAGEINDEX_SYSTEM_PROMPT
    text = PAGEINDEX_SYSTEM_PROMPT.lower()
    assert "must call `get_material_structure" in text
    assert "before any final answer" in text
    assert "broad" in text and "conceptual" in text
