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
    lines = [
        f'data: {json.dumps({"choices": [{"delta": {"content": content}, "finish_reason": None}]})}',
        'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}',
        "data: [DONE]",
    ]
    resp.iter_lines.return_value = iter(lines)
    return resp


def test_run_agent_pageindex_preloads_routing_and_drops_search_tool():
    """The agent should receive the routing index in the system prompt
    and the search_course_materials tool should not be exposed."""
    from llm import run_agent_pageindex

    conn = MagicMock()

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
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


def _stub_openai_tool_call(material_id: int, pages: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    args_json = json.dumps({"material_id": material_id, "pages": pages})
    lines = [
        f'data: {json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "get_page_content", "arguments": args_json}}]}, "finish_reason": None}]})}',
        'data: {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}',
        "data: [DONE]",
    ]
    resp.iter_lines.return_value = iter(lines)
    return resp


def test_run_agent_pageindex_forced_synthesis_when_iterations_exhausted():
    """When MAX_TOOL_ITERATIONS is exhausted without a final answer, the agent
    makes one additional no-tool call to synthesize from the accumulated context
    (Q08 fix) rather than returning an error."""
    from llm import run_agent_pageindex

    conn = MagicMock()
    payloads = []

    # All iterations consume tool calls — loop exhausts without a text answer.
    responses = [
        _stub_openai_tool_call(10, "2-3"),
        _stub_openai_tool_call(10, "4-5"),
        _stub_openai_tool_call(10, "6-7"),
        _stub_openai_tool_call(10, "8-9"),
        # forced synthesis call (no tools in request)
        _stub_openai_response_no_tools(
            "<REPLY>\nSynthesized from evidence.\n</REPLY>\n"
            '<META>\n{"summary": "ok", "follow_ups": [], "clarifying_question": null}\n</META>'
        ),
    ]

    import copy

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        payloads.append(copy.deepcopy(json))
        return responses[len(payloads) - 1]

    routing_rows = [
        {
            "material_id": 10,
            "title": "L1",
            "doc_type": "lecture",
            "page_count": 9,
            "summary": "s",
            "tags": [],
            "sections": [],
        }
    ]
    page_rows = [{"page_number": 2, "text_content": "content"}]

    with patch("llm.requests.post", side_effect=fake_post), \
         patch("pageindex_retrieval.get_course_routing_index", return_value=routing_rows), \
         patch("pageindex_retrieval.get_page_content", return_value=page_rows):
        final_text, grounding_refs, tool_trace, *_ = run_agent_pageindex(
            conn=conn,
            user_message="Complex question.",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=None,
            course_id=7,
            context_material_ids=[10],
        )

    # 4 retrieval iterations + 1 forced synthesis = 5 calls total
    assert len(payloads) == 5
    # Forced synthesis carries no tools
    assert "tools" not in payloads[4]
    # The accumulated context is passed (not a fresh lean prompt)
    assert payloads[4]["messages"][0]["content"] != ""
    assert final_text == "Synthesized from evidence."
    assert grounding_refs == ["material:10"] * 4
    assert any(t.get("phase") == "forced_synthesis" for t in tool_trace)


def test_synthesize_pageindex_infers_course_from_chat_without_material_scope():
    from llm import synthesize

    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = {"course_id": 42}
    conn.cursor.return_value = cursor

    with patch("llm._get_api_key", return_value="sk-test"), \
         patch("llm.run_agent_pageindex", return_value=("answer", ["material:1"], {}, [], "summary", [], None)) as run_agent:
        synthesize(
            conn=conn,
            user_id=1,
            ai_provider="openai",
            ai_model="gpt-4o-mini",
            user_message="Explain attention",
            chunks=[],
            chat_id=99,
            context_material_ids=[],
        )

    cursor.execute.assert_called_with("SELECT course_id FROM chats WHERE id = %s", (99,))
    assert run_agent.call_args.kwargs["course_id"] == 42
    assert run_agent.call_args.kwargs["context_material_ids"] == []


def test_pageindex_prompt_documents_citation_numbering():
    """PAGEINDEX_SYSTEM_PROMPT must explain how [N] markers map to fetched pages."""
    from llm import PAGEINDEX_SYSTEM_PROMPT
    text = PAGEINDEX_SYSTEM_PROMPT.lower()
    assert "get_page_content" in text
    assert ("order" in text and "call" in text) or "nth call" in text, \
        "Prompt must instruct agent to use call-order for citation numbers"


def test_dispatch_pageindex_tool_get_page_content_appends_grounding():
    from unittest.mock import patch, MagicMock
    import llm
    grounding = []
    events = []
    rows = [{"page_number": 5, "text_content": "Hello page 5"}]
    with patch("pageindex_retrieval.get_page_content", return_value=rows):
        out = llm._dispatch_pageindex_tool(
            conn=MagicMock(), name="get_page_content",
            args={"material_id": 7, "pages": "5"},
            course_id=1,
            grounding_refs=grounding, on_event=events.append,
        )
    assert "Hello page 5" in out
    assert "material:7" in grounding
    assert any(e.get("tool") == "get_page_content" for e in events)


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


import json


def _stub_anthropic_tool_use(tool_id, name, input_obj):
    """Mock Anthropic streaming response that returns a single tool_use block."""
    resp = MagicMock()
    resp.status_code = 200
    payload = json.dumps(input_obj)
    resp.iter_lines.return_value = iter([
        b'event: content_block_start',
        b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"' + tool_id.encode() + b'","name":"' + name.encode() + b'","input":{}}}',
        b'event: content_block_delta',
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":' + json.dumps(payload).encode() + b'}}',
        b'event: message_delta',
        b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
    ])
    return resp


def _stub_anthropic_text(text):
    """Mock Anthropic streaming response that returns a text block (final answer)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.iter_lines.return_value = iter([
        b'event: content_block_start',
        b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","id":null,"name":null,"input":{}}}',
        b'event: content_block_delta',
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":' + json.dumps(text).encode() + b'}}',
        b'event: message_delta',
        b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
    ])
    return resp


def test_run_agent_pageindex_claude_calls_tool_and_returns_answer():
    """Claude provider: one tool call then a final text answer."""
    from unittest.mock import patch, MagicMock, call
    from llm import run_agent_pageindex

    events = []
    tool_stub = _stub_anthropic_tool_use("tid1", "get_material_structure", {"course_id": 1})
    text_stub = _stub_anthropic_text('{"answer":"Structure answer","cited_pages":[]}')

    with patch("requests.post", side_effect=[tool_stub, text_stub]) as mock_post, \
         patch("llm._dispatch_pageindex_tool", return_value="<structure>...</structure>") as mock_dispatch, \
         patch("llm._format_routing_index_block", return_value="<course_materials></course_materials>"):
        result = run_agent_pageindex(
            conn=MagicMock(),
            user_message="what is the structure of this course?",
            model="claude-sonnet-4-6",
            api_key="sk-ant-test",
            chat_id=1,
            course_id=7,
            context_material_ids=[101],
            on_event=events.append,
            provider="claude",
        )

    # Should have called requests.post twice (tool call + final)
    assert mock_post.call_count == 2
    # Should have dispatched get_material_structure
    assert mock_dispatch.call_count == 1
    # result[0] is the answer string
    assert "Structure answer" in result[0]


def _stub_gemini_function_call(name, args_obj):
    """Mock Gemini SSE response with a single functionCall part."""
    resp = MagicMock()
    resp.status_code = 200
    data = json.dumps({
        "candidates": [{"content": {"parts": [{"functionCall": {"name": name, "args": args_obj}}]}}]
    })
    resp.iter_lines.return_value = iter([
        b'data: ' + data.encode(),
    ])
    return resp


def _stub_gemini_text(text):
    """Mock Gemini SSE response with a text part (final answer)."""
    resp = MagicMock()
    resp.status_code = 200
    data = json.dumps({
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    })
    resp.iter_lines.return_value = iter([
        b'data: ' + data.encode(),
    ])
    return resp


def test_run_agent_pageindex_gemini_calls_tool_and_returns_answer():
    """Gemini provider: one tool call then a final text answer."""
    from unittest.mock import patch, MagicMock
    from llm import run_agent_pageindex

    events = []
    tool_stub = _stub_gemini_function_call("get_material_structure", {"course_id": 1})
    text_stub = _stub_gemini_text('{"answer":"Gemini structure answer","cited_pages":[]}')

    with patch("requests.post", side_effect=[tool_stub, text_stub]) as mock_post, \
         patch("llm._dispatch_pageindex_tool", return_value="<structure>...</structure>") as mock_dispatch, \
         patch("llm._format_routing_index_block", return_value="<course_materials></course_materials>"):
        result = run_agent_pageindex(
            conn=MagicMock(),
            user_message="what is the structure of this course?",
            model="gemini-2.0-flash",
            api_key="gm-test",
            chat_id=1,
            course_id=7,
            context_material_ids=[101],
            on_event=events.append,
            provider="gemini",
        )

    assert mock_post.call_count == 2
    assert mock_dispatch.call_count == 1
    assert "Gemini structure answer" in result[0]
