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
    import copy
    from llm import run_agent_pageindex

    conn = MagicMock()

    payloads = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        payloads.append(copy.deepcopy(json))
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

    payload = payloads[0]
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
    """When MAX_TOOL_ITERATIONS (6) is exhausted without a final answer, the agent
    still runs the separate synthesis call from the accumulated evidence rather
    than returning an error."""
    from llm import run_agent_pageindex

    conn = MagicMock()
    payloads = []

    # All iterations consume tool calls — loop exhausts without a text answer.
    responses = [
        _stub_openai_tool_call(10, "2-3"),
        _stub_openai_tool_call(10, "4-5"),
        _stub_openai_tool_call(10, "6-7"),
        _stub_openai_tool_call(10, "8-9"),
        _stub_openai_tool_call(10, "2-3"),
        _stub_openai_tool_call(10, "4-5"),
        # synthesis call (no tools in request)
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

    # 6 retrieval iterations + 1 synthesis = 7 calls total
    assert len(payloads) == 7
    # Synthesis carries no tools
    assert "tools" not in payloads[6]
    # The synthesis system prompt carries the retrieved evidence
    assert payloads[6]["messages"][0]["content"] != ""
    assert final_text == "Synthesized from evidence."
    assert grounding_refs == ["material:10"] * 6
    assert any(t.get("phase") == "synthesis" for t in tool_trace)


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


def test_pageindex_synthesis_prompt_documents_citation_numbering():
    """The synthesis prompt (the model that writes the answer) must explain how
    [N] markers map to the retrieved evidence blocks."""
    import llm
    prompt = llm._build_pageindex_synthesis_system_context(
        "Raw retrieved course material:\nevidence", clarification_depth=0
    )
    lower = prompt.lower()
    assert "citation" in lower
    assert "[1]" in prompt
    assert "order" in lower


def test_dispatch_pageindex_tool_get_page_content_appends_grounding():
    from unittest.mock import patch, MagicMock
    import llm
    grounding = []
    events = []
    rows = [{"page_number": 5, "text_content": "Hello page 5"}]
    with patch("pageindex_retrieval.get_page_content", return_value=rows):
        out, _meta = llm._dispatch_pageindex_tool(
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
    """Claude provider: one tool call, retrieval ends, then a separate synthesis call."""
    from unittest.mock import patch, MagicMock, call
    from llm import run_agent_pageindex

    events = []
    tool_stub = _stub_anthropic_tool_use("tid1", "get_material_structure", {"course_id": 1})
    text_stub = _stub_anthropic_text("Retrieval done.")
    synth_stub = _stub_anthropic_text("Structure answer")

    with patch("requests.post", side_effect=[tool_stub, text_stub, synth_stub]) as mock_post, \
         patch("llm._dispatch_pageindex_tool", return_value=("<structure>...</structure>", {})) as mock_dispatch, \
         patch("llm._recall_prior_chat_images", return_value=[]), \
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

    # tool call + retrieval end + separate synthesis call
    assert mock_post.call_count == 3
    # Should have dispatched get_material_structure
    assert mock_dispatch.call_count == 1
    # result[0] is the answer string from the synthesis call
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
    """Gemini provider: one tool call, retrieval ends, then a separate synthesis call."""
    from unittest.mock import patch, MagicMock
    from llm import run_agent_pageindex

    events = []
    tool_stub = _stub_gemini_function_call("get_material_structure", {"course_id": 1})
    text_stub = _stub_gemini_text("Retrieval done.")
    synth_stub = _stub_gemini_text("Gemini structure answer")

    with patch("requests.post", side_effect=[tool_stub, text_stub, synth_stub]) as mock_post, \
         patch("llm._dispatch_pageindex_tool", return_value=("<structure>...</structure>", {})) as mock_dispatch, \
         patch("llm._recall_prior_chat_images", return_value=[]), \
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

    assert mock_post.call_count == 3
    assert mock_dispatch.call_count == 1
    assert "Gemini structure answer" in result[0]


def test_synthesize_pageindex_routes_to_selected_provider():
    """When PageIndex is enabled and provider=claude, synthesize passes claude key+model."""
    from unittest.mock import patch, MagicMock
    from llm import synthesize

    captured = {}
    def fake_loop(**kwargs):
        captured.update(kwargs)
        return ("answer", ["material:1"], [], {}, "summary", [], None)

    with patch("llm._is_pageindex_enabled", return_value=True), \
         patch("llm.run_agent_pageindex", side_effect=fake_loop) as mock_loop, \
         patch("llm._get_api_key", return_value="sk-ant-test-key"):
        synthesize(
            MagicMock(),           # conn
            1,                     # user_id
            "claude",              # ai_provider
            "claude-sonnet-4-6",   # ai_model
            "what is TCP?",        # user_message
            [],                    # chunks
            chat_id=5,
            context_material_ids=[],
        )

    assert mock_loop.called
    assert captured.get("provider") == "claude"
    assert captured.get("model") == "claude-sonnet-4-6"


def test_pageindex_tool_list_includes_web_search_when_enabled(monkeypatch):
    """web_search tool appears only when web_search_enabled=True AND env var is set."""
    import llm
    monkeypatch.setenv("AGENTIC_WEB_SEARCH_ENABLED", "true")

    tools_on = llm._pageindex_tool_list(web_search_enabled=True)
    tools_off = llm._pageindex_tool_list(web_search_enabled=False)

    names_on = [t.get("function", t).get("name") for t in tools_on]
    names_off = [t.get("function", t).get("name") for t in tools_off]

    assert "web_search" in names_on
    assert "web_search" not in names_off


def test_dispatch_pageindex_tool_web_search_calls_execute_web_search(monkeypatch):
    """_dispatch_pageindex_tool routes web_search to execute_web_search."""
    from unittest.mock import patch, MagicMock
    import llm

    with patch("tools.execute_web_search", return_value={"text": "search result"}) as mock_ws:
        result = llm._dispatch_pageindex_tool(
            conn=MagicMock(), name="web_search",
            args={"query": "TCP handshake"},
            course_id=1, grounding_refs=[], on_event=None,
        )
    assert "search result" in result
    mock_ws.assert_called_once()


def test_synthesize_passes_web_search_enabled_to_pageindex(monkeypatch):
    """synthesize() threads web_search_enabled into run_agent_pageindex."""
    from unittest.mock import patch, MagicMock
    import os
    import llm

    captured = {}
    def fake_loop(**kwargs):
        captured.update(kwargs)
        return ("answer", ["material:1"], [], {}, "summary", [], None)

    monkeypatch.setenv("AGENTIC_WEB_SEARCH_ENABLED", "true")

    with patch("llm._is_pageindex_enabled", return_value=True), \
         patch("llm.run_agent_pageindex", side_effect=fake_loop), \
         patch("llm._get_api_key", return_value="sk-test"):
        llm.synthesize(
            MagicMock(), 1, "openai", "gpt-4o", "query", [],
            chat_id=5, web_search_enabled=True,
        )

    assert captured.get("web_search_enabled") is True


def _stub_openai_named_tool_call(name: str, args: dict) -> MagicMock:
    """Mock one streaming OpenAI response that emits a single named tool call."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    tool_args = json.dumps(args)
    lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1",'
        '"type":"function","function":{"name":"' + name + '",'
        '"arguments":' + json.dumps(tool_args) + '}}]}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        'data: [DONE]',
    ]
    resp.iter_lines.return_value = iter(lines)
    return resp


def test_run_agent_pageindex_propose_generation_emits_event():
    import copy
    from llm import run_agent_pageindex

    events = []
    first = _stub_openai_named_tool_call(
        "propose_generation",
        {
            "generation_type": "quiz",
            "title": "TCP Handshake Quiz",
            "discussion_summary": "We covered SYN/SYN-ACK/ACK and sequence numbers.",
            "params": {"tf_count": 3, "sa_count": 2, "la_count": 1},
        },
    )
    second = _stub_openai_response_no_tools("Here's a quiz on the handshake.")

    with patch("llm.requests.post", side_effect=[copy.deepcopy(first), copy.deepcopy(second)]), \
         patch("pageindex_retrieval.get_course_routing_index", return_value=[]), \
         patch("llm._recall_prior_chat_images", return_value=[]), \
         patch("llm._format_routing_index_block", return_value="<course_materials></course_materials>"):
        run_agent_pageindex(
            conn=MagicMock(),
            user_message="make me a quiz about the TCP handshake",
            model="gpt-4o",
            api_key="sk-test",
            chat_id=1,
            course_id=7,
            context_material_ids=[101, 102],
            on_event=events.append,
        )

    proposals = [e for e in events if e.get("type") == "generation_proposal"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["generation_type"] == "quiz"
    assert p["title"] == "TCP Handshake Quiz"
    assert p["material_ids"] == [101, 102]          # defaulted from context_material_ids
    assert p["params"]["tf_count"] == 3
    assert "SYN" in p["discussion_summary"]


def test_retrieval_loop_uses_user_selected_model():
    """The retrieval planning loop must run on the user-selected model,
    not the hardcoded gpt-4o-mini default."""
    import copy
    from llm import run_agent_pageindex

    payloads = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        payloads.append(copy.deepcopy(json))
        return _stub_openai_response_no_tools(
            '<REPLY>\nok\n</REPLY>\n'
            '<META>\n{"summary": "ok", "follow_ups": [], "clarifying_question": null}\n</META>'
        )

    with patch("llm.requests.post", side_effect=fake_post), \
         patch("pageindex_retrieval.get_course_routing_index", return_value=[]):
        run_agent_pageindex(
            conn=MagicMock(),
            user_message="Summarize lectures 1-3.",
            model="gpt-4.1",
            api_key="sk-test",
            chat_id=None,
            course_id=7,
            context_material_ids=[],
        )

    retrieval_payloads = [p for p in payloads if "tools" in p]
    assert retrieval_payloads, "expected at least one retrieval call with tools"
    assert all(p["model"] == "gpt-4.1" for p in retrieval_payloads)


def test_retrieval_loop_nudges_once_when_no_evidence():
    """If the planner stops without fetching any course material, the loop
    injects one corrective user message and gives it another chance."""
    import copy
    from llm import run_agent_pageindex

    payloads = []
    responses = [
        _stub_openai_response_no_tools("Routing summaries look sufficient."),
        _stub_openai_tool_call(10, "2-3"),
        _stub_openai_response_no_tools("Done."),
        _stub_openai_response_no_tools(
            '<REPLY>\nanswer\n</REPLY>\n'
            '<META>\n{"summary": "ok", "follow_ups": [], "clarifying_question": null}\n</META>'
        ),
    ]

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
            conn=MagicMock(),
            user_message="What does lecture 1 cover?",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=None,
            course_id=7,
            context_material_ids=[10],
        )

    # no-tool turn + nudged retry + post-fetch turn + synthesis
    assert len(payloads) == 4
    nudge_msgs = [
        m
        for p in payloads
        for m in p["messages"]
        if m["role"] == "user" and "without fetching" in str(m["content"])
    ]
    assert nudge_msgs, "expected a corrective nudge message in the retrieval conversation"
    assert grounding_refs == ["material:10"]
    assert any(t.get("phase") == "retrieval_nudge" for t in tool_trace)


def test_retrieval_nudge_fires_at_most_once():
    """The corrective nudge must not loop forever when the planner keeps
    returning no tool calls."""
    import copy
    from llm import run_agent_pageindex

    payloads = []
    responses = [
        _stub_openai_response_no_tools("Nothing relevant."),
        _stub_openai_response_no_tools("Still nothing relevant."),
        _stub_openai_response_no_tools(
            '<REPLY>\nNo relevant material.\n</REPLY>\n'
            '<META>\n{"summary": "ok", "follow_ups": [], "clarifying_question": null}\n</META>'
        ),
    ]

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        payloads.append(copy.deepcopy(json))
        return responses[len(payloads) - 1]

    with patch("llm.requests.post", side_effect=fake_post), \
         patch("pageindex_retrieval.get_course_routing_index", return_value=[]):
        run_agent_pageindex(
            conn=MagicMock(),
            user_message="What does lecture 99 cover?",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=None,
            course_id=7,
            context_material_ids=[],
        )

    # initial no-tool turn + single nudged retry + synthesis
    assert len(payloads) == 3
    last_retrieval = payloads[1]
    nudges = [
        m
        for m in last_retrieval["messages"]
        if m["role"] == "user" and "without fetching" in str(m["content"])
    ]
    assert len(nudges) == 1


def test_pageindex_retrieval_prompt_defines_planner_role():
    """The retrieval prompt must frame the model as a planner whose text is
    discarded, and must not contain the old contradictory instructions."""
    from llm import PAGEINDEX_SYSTEM_PROMPT
    text = PAGEINDEX_SYSTEM_PROMPT
    lower = text.lower()
    assert "retrieval planner" in lower
    assert "never shown to the user" in lower
    # No final-answer format in the planner prompt — its text is discarded.
    assert "<REPLY>" not in text
    # Old contradictions removed.
    assert "Do NOT call any other tools" not in text
    assert "only call `get_material_structure" not in lower
    assert "q`" not in text  # typo from the old citation paragraph


def test_format_routing_index_block_keeps_long_section_summaries():
    """Section summaries must not be truncated to unusably short snippets —
    the planner navigates by them."""
    long_summary = (
        "Dynamic programming value iteration convergence proof with Bellman "
        "operator contraction mapping argument, discount factor bounds, and "
        "stopping criteria, followed by worked gridworld examples comparing "
        "policy iteration sweep costs against value iteration sweep costs."
    )
    assert len(long_summary) > 200
    materials = [
        {
            "material_id": 1,
            "title": "Lecture 4",
            "doc_type": "lecture_slide",
            "page_count": 12,
            "summary": "MDP planning.",
            "tags": [],
            "sections": [
                {"start_page": 2, "end_page": 4, "summary": long_summary},
            ],
        }
    ]
    block = _format_routing_index_block(materials)
    assert long_summary[:200] in block
