"""Unit tests for multi-turn chat memory helpers in api/llm.py."""
import sys
import os
from unittest.mock import MagicMock

# Stub heavy imports so llm.py can load without a real environment.
# Note: pageindex_retrieval is NOT stubbed here — it's imported locally inside
# run_agent_pageindex, so we scope that mock inside the one test that exercises it.
for mod in ("middleware", "models", "db", "boto3", "crypto_utils"):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import llm  # noqa: E402


def test_estimate_tokens_uses_char_heuristic():
    # ~4 chars per token, floor of 1.
    assert llm._estimate_tokens("") == 1
    assert llm._estimate_tokens("abcd") == 1
    assert llm._estimate_tokens("a" * 400) == 100


def test_context_window_known_model():
    # gpt-4o-mini has a 128k window.
    assert llm._context_window_for("gpt-4o-mini") == 128000


def test_context_window_unknown_model_falls_back():
    assert llm._context_window_for("totally-made-up-model") == llm._DEFAULT_CONTEXT_WINDOW


def test_history_budget_subtracts_reserves_and_margin():
    # window=10000, system=40 tokens (160 chars), current user=10 tokens (40 chars).
    # reserve=RESPONSE_RESERVE_TOKENS, margin=SAFETY_MARGIN_RATIO of window,
    # capped by HISTORY_CONTEXT_RATIO of the window.
    budget = llm._history_budget(
        window=10000,
        system_text="s" * 160,
        current_user_text="u" * 40,
    )
    available = 10000 - 40 - llm.RESPONSE_RESERVE_TOKENS - 10 - int(10000 * llm.SAFETY_MARGIN_RATIO)
    expected = min(int(10000 * llm.HISTORY_CONTEXT_RATIO), available)
    assert budget == expected


def test_history_budget_uses_percentage_cap_for_large_windows():
    budget = llm._history_budget(
        window=128000,
        system_text="s",
        current_user_text="u",
    )
    assert budget == int(128000 * llm.HISTORY_CONTEXT_RATIO)


def test_history_budget_never_negative():
    budget = llm._history_budget(window=10, system_text="x" * 1000, current_user_text="y" * 1000)
    assert budget == 0


def test_output_token_cap_uses_bounded_context_ratio():
    assert llm._output_token_cap("gpt-4o-mini") == 6400
    assert llm._output_token_cap("gemini-2.5-pro") == llm.MAX_OUTPUT_TOKENS


def test_openai_reasoning_models_use_responses_api():
    for model in ("gpt-5-mini", "o1", "o1-pro", "o3", "o3-mini", "o4-mini", "gpt-oss-120b"):
        assert llm._openai_should_use_responses_api(model) is True
    for model in ("gpt-4o", "gpt-4o-mini", "gpt-4.1"):
        assert llm._openai_should_use_responses_api(model) is False


def test_non_vision_model_rejects_image_input():
    try:
        llm._validate_model_supports_images("gpt-oss-120b", ["chat-images/1/a.png"])
    except ValueError as exc:
        assert "does not support image input" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_responses_api_sets_model_output_cap(monkeypatch):
    captured = {}
    response = MagicMock()
    response.json.return_value = {"output_text": "answer"}
    response.raise_for_status.return_value = None

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return response

    monkeypatch.setattr(llm.requests, "post", fake_post)

    llm._pageindex_call_responses(
        api_key="sk-test",
        model="gpt-5-mini",
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        on_event=None,
    )

    assert captured["json"]["max_output_tokens"] == llm._output_token_cap("gpt-5-mini")


def test_claude_pageindex_call_sets_model_output_cap(monkeypatch):
    captured = {}
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_lines.return_value = iter([])

    def fake_post(url, headers=None, json=None, stream=None, timeout=None):
        captured["json"] = json
        return response

    monkeypatch.setattr(llm.requests, "post", fake_post)

    llm._pageindex_stream_call_claude(
        api_key="sk-test",
        model="claude-sonnet-4-6",
        system="system",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        on_event=None,
    )

    assert captured["json"]["max_tokens"] == llm._output_token_cap("claude-sonnet-4-6")


def test_gemini_pageindex_call_sets_model_output_cap(monkeypatch):
    captured = {}
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_lines.return_value = iter([])

    def fake_post(url, json=None, stream=None, timeout=None):
        captured["json"] = json
        return response

    monkeypatch.setattr(llm.requests, "post", fake_post)

    llm._pageindex_stream_call_gemini(
        api_key="gm-test",
        model="gemini-2.5-flash",
        system="system",
        contents=[{"role": "user", "parts": [{"text": "hi"}]}],
        tools=[],
        on_event=None,
    )

    assert captured["json"]["generationConfig"]["maxOutputTokens"] == llm._output_token_cap("gemini-2.5-flash")


def test_format_pageindex_evidence_blocks_course_and_web_results():
    evidence = llm._format_pageindex_evidence(
        course_contents=["page one", "page two"],
        web_contents=["web result"],
    )

    assert "Retrieved course material:" in evidence
    assert "page one\n\n---\n\npage two" in evidence
    assert "Web search results" in evidence
    assert "web result" in evidence


def test_format_pageindex_evidence_empty_returns_empty_string():
    assert llm._format_pageindex_evidence([], []) == ""


def test_compose_history_keeps_all_when_under_budget():
    turns = [
        {"role": "user", "content": "aaaa"},       # 1 token
        {"role": "assistant", "content": "bbbb"},  # 1 token
    ]
    out = llm._compose_history(turns, budget_tokens=100)
    assert out == turns  # unchanged, chronological order preserved


def test_compose_history_drops_oldest_first_when_over_budget():
    turns = [
        {"role": "user", "content": "a" * 400},       # 100 tokens (oldest)
        {"role": "assistant", "content": "b" * 400},  # 100 tokens
        {"role": "user", "content": "c" * 400},       # 100 tokens (newest)
    ]
    # Budget only fits the two newest (200 tokens).
    out = llm._compose_history(turns, budget_tokens=200)
    assert [t["content"][0] for t in out] == ["b", "c"]  # oldest "a" dropped


def test_compose_history_empty_budget_returns_empty():
    turns = [{"role": "user", "content": "a" * 400}]
    assert llm._compose_history(turns, budget_tokens=0) == []


def test_load_chat_history_queries_active_branch_and_maps_rows():
    rows = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor

    out = llm._load_chat_history(conn, chat_id=7, before_index=5)

    assert out == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    # Query must filter is_deleted and message_index < before_index, ordered asc.
    sql, params = cursor.execute.call_args[0]
    assert "is_deleted = FALSE" in sql
    assert "message_index <" in sql
    assert "ORDER BY message_index ASC" in sql
    assert params == (7, 5)


def test_load_chat_history_none_chat_returns_empty():
    assert llm._load_chat_history(MagicMock(), chat_id=None, before_index=5) == []
    assert llm._load_chat_history(MagicMock(), chat_id=1, before_index=None) == []


def test_build_history_turns_end_to_end(monkeypatch):
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "a" * 400},       # 100 tokens
        {"role": "assistant", "content": "b" * 400},  # 100 tokens
    ])
    # Big window -> both kept.
    kept = llm._build_history_turns(
        conn=MagicMock(), chat_id=1, before_index=9,
        model="gpt-4o-mini", system_text="s", current_user_text="u",
    )
    assert len(kept) == 2


def test_shape_history_openai_roles_passthrough():
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert llm._shape_history_openai(turns) == turns


def test_shape_history_gemini_maps_assistant_to_model():
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    out = llm._shape_history_gemini(turns)
    assert out == [
        {"role": "user", "parts": [{"text": "hi"}]},
        {"role": "model", "parts": [{"text": "yo"}]},
    ]


def test_shape_history_claude_roles_passthrough():
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert llm._shape_history_claude(turns) == turns


def test_run_agent_seeds_openai_history(monkeypatch):
    from unittest.mock import patch

    # No images, no real network.
    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ])

    captured = {}

    def fake_stream(api_key, model, msgs, tools, on_event):
        captured["msgs"] = msgs
        # Return message dict shape matching _pageindex_stream_call contract
        return ({"content": "Final answer.", "tool_calls": None}, "stop")

    monkeypatch.setattr(llm, "_pageindex_stream_call", fake_stream)

    # Scope the pageindex_retrieval stub to this test only so it doesn't pollute
    # other test files (test_pageindex_retrieval.py, test_chat_citations.py).
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="current question",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="openai",
            history_before_index=9,
        )

    contents = [m["content"] for m in captured["msgs"] if m["role"] in ("user", "assistant")]
    assert "earlier question" in contents
    assert "earlier answer" in contents
    # Current user turn is last.
    assert captured["msgs"][-1]["content"] == "current question"


def test_run_agent_gpt5_synthesis_preserves_history_and_current_turn(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ])
    monkeypatch.setattr(
        llm,
        "_dispatch_pageindex_tool",
        lambda **kwargs: ("retrieved page content", {}),
    )

    calls = []

    def fake_stream(api_key, model, msgs, tools, on_event):
        import copy
        calls.append({"model": model, "msgs": copy.deepcopy(msgs), "tools": tools})
        if tools:
            return (
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_page_content",
                                "arguments": '{"material_id": 10, "pages": "1"}',
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        return ({"content": "Final answer.", "tool_calls": None}, "stop")

    monkeypatch.setattr(llm, "_pageindex_stream_call", fake_stream)

    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="current follow-up",
            model="gpt-5-mini",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="openai",
            history_before_index=9,
        )

    retrieval_msgs = calls[0]["msgs"]
    retrieval_contents = [
        m.get("content")
        for m in retrieval_msgs
        if m.get("role") in ("user", "assistant")
    ]
    assert retrieval_contents == ["earlier question", "earlier answer", "current follow-up"]
    assert "Conversation history" in retrieval_msgs[0]["content"]

    synthesis_msgs = calls[-1]["msgs"]
    contents = [
        m.get("content")
        for m in synthesis_msgs
        if m.get("role") in ("user", "assistant")
    ]
    assert contents == ["earlier question", "earlier answer", "current follow-up"]
    assert "Conversation history" in synthesis_msgs[0]["content"]
    assert "retrieved page content" in synthesis_msgs[0]["content"]
    assert "Retrieval is complete" in synthesis_msgs[0]["content"]
    assert "Use the material IDs above when calling" not in synthesis_msgs[0]["content"]
    assert "get_page_content" not in synthesis_msgs[0]["content"]


def test_run_agent_openai_chat_synthesis_uses_clean_prompt(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ])
    monkeypatch.setattr(llm, "_dispatch_pageindex_tool", lambda **kwargs: ("retrieved page content", {}))

    calls = []

    def fake_stream(api_key, model, msgs, tools, on_event):
        import copy
        calls.append({"model": model, "msgs": copy.deepcopy(msgs), "tools": tools})
        if tools:
            return ({
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_page_content", "arguments": '{"material_id": 10, "pages": "1"}'},
                }],
            }, "tool_calls")
        return ({"content": "Final answer.", "tool_calls": None}, "stop")

    monkeypatch.setattr(llm, "_pageindex_stream_call", fake_stream)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="current follow-up",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="openai",
            history_before_index=9,
        )

    synthesis_msgs = calls[-1]["msgs"]
    assert synthesis_msgs[0]["role"] == "system"
    assert "Retrieval is complete" in synthesis_msgs[0]["content"]
    assert "retrieved page content" in synthesis_msgs[0]["content"]
    assert "get_page_content" not in synthesis_msgs[0]["content"]
    assert [m["content"] for m in synthesis_msgs[1:]] == [
        "earlier question",
        "earlier answer",
        "current follow-up",
    ]


def test_run_agent_claude_synthesis_uses_clean_prompt(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ])
    monkeypatch.setattr(llm, "_dispatch_pageindex_tool", lambda **kwargs: ("retrieved page content", {}))

    calls = []

    def fake_claude(api_key, model, system, messages, tools, on_event):
        import copy
        calls.append({"system": system, "messages": copy.deepcopy(messages), "tools": tools})
        if tools:
            return ([{"type": "tool_use", "id": "tool_1", "name": "get_page_content", "input_json": '{"material_id": 10, "pages": "1"}', "text": ""}], "tool_use")
        return ([{"type": "text", "text": "Final answer."}], "end_turn")

    monkeypatch.setattr(llm, "_pageindex_stream_call_claude", fake_claude)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="current follow-up",
            model="claude-sonnet-4-6",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="claude",
            history_before_index=9,
        )

    final_call = calls[-1]
    assert final_call["tools"] == []
    assert "Retrieval is complete" in final_call["system"]
    assert "retrieved page content" in final_call["system"]
    assert "get_page_content" not in final_call["system"]
    assert [m["content"] for m in final_call["messages"]] == [
        "earlier question",
        "earlier answer",
        "current follow-up",
    ]


def test_run_agent_gemini_synthesis_uses_clean_prompt(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ])
    monkeypatch.setattr(llm, "_dispatch_pageindex_tool", lambda **kwargs: ("retrieved page content", {}))

    calls = []

    def fake_gemini(api_key, model, system, contents, tools, on_event):
        import copy
        calls.append({"system": system, "contents": copy.deepcopy(contents), "tools": tools})
        if tools:
            return ([{"functionCall": {"name": "get_page_content", "args": {"material_id": 10, "pages": "1"}, "id": "fc1"}}], True)
        return ([{"text": "Final answer."}], False)

    monkeypatch.setattr(llm, "_pageindex_stream_call_gemini", fake_gemini)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="current follow-up",
            model="gemini-2.5-flash",
            api_key="gm-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="gemini",
            history_before_index=9,
        )

    final_call = calls[-1]
    assert final_call["tools"] == []
    assert "Retrieval is complete" in final_call["system"]
    assert "retrieved page content" in final_call["system"]
    assert "get_page_content" not in final_call["system"]
    assert [
        item["parts"][0]["text"]
        for item in final_call["contents"]
        if item["role"] in ("user", "model")
    ] == ["earlier question", "earlier answer", "current follow-up"]


def test_claude_retrieval_text_is_not_streamed(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [])
    monkeypatch.setattr(llm, "_dispatch_pageindex_tool", lambda **kwargs: ("retrieved page content", {}))
    events = []

    def fake_claude(api_key, model, system, messages, tools, on_event):
        if tools:
            if on_event:
                on_event({"type": "text", "chunk": "retrieval preamble"})
            return ([{"type": "tool_use", "id": "tool_1", "name": "get_page_content", "input_json": '{"material_id": 10, "pages": "1"}', "text": ""}], "tool_use")
        if on_event:
            on_event({"type": "text", "chunk": "final answer"})
        return ([{"type": "text", "text": "final answer"}], "end_turn")

    monkeypatch.setattr(llm, "_pageindex_stream_call_claude", fake_claude)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="question",
            model="claude-sonnet-4-6",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="claude",
            on_event=events.append,
        )

    streamed_text = "".join(e["chunk"] for e in events if e.get("type") == "text")
    assert "retrieval preamble" not in streamed_text
    assert "final answer" in streamed_text


def test_gemini_retrieval_text_is_not_streamed(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [])
    monkeypatch.setattr(llm, "_dispatch_pageindex_tool", lambda **kwargs: ("retrieved page content", {}))
    events = []

    def fake_gemini(api_key, model, system, contents, tools, on_event):
        if tools:
            if on_event:
                on_event({"type": "text", "chunk": "retrieval preamble"})
            return ([{"functionCall": {"name": "get_page_content", "args": {"material_id": 10, "pages": "1"}, "id": "fc1"}}], True)
        if on_event:
            on_event({"type": "text", "chunk": "final answer"})
        return ([{"text": "final answer"}], False)

    monkeypatch.setattr(llm, "_pageindex_stream_call_gemini", fake_gemini)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="question",
            model="gemini-2.5-flash",
            api_key="gm-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="gemini",
            on_event=events.append,
        )

    streamed_text = "".join(e["chunk"] for e in events if e.get("type") == "text")
    assert "retrieval preamble" not in streamed_text
    assert "final answer" in streamed_text


def test_openai_propose_generation_returns_non_empty_message(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])

    def fake_stream(api_key, model, msgs, tools, on_event):
        return ({
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "propose_generation",
                    "arguments": '{"generation_type": "quiz", "title": "Quiz", "discussion_summary": "Summary"}',
                },
            }],
        }, "tool_calls")

    monkeypatch.setattr(llm, "_pageindex_stream_call", fake_stream)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        result = llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="make a quiz",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="openai",
        )

    assert result[0] == llm.GENERATION_PROPOSAL_READY_MESSAGE


def test_claude_propose_generation_returns_non_empty_message(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])

    def fake_claude(api_key, model, system, messages, tools, on_event):
        return ([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "propose_generation",
            "input_json": '{"generation_type": "quiz", "title": "Quiz", "discussion_summary": "Summary"}',
            "text": "",
        }], "tool_use")

    monkeypatch.setattr(llm, "_pageindex_stream_call_claude", fake_claude)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        result = llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="make a quiz",
            model="claude-sonnet-4-6",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="claude",
        )

    assert result[0] == llm.GENERATION_PROPOSAL_READY_MESSAGE


def test_gemini_propose_generation_returns_non_empty_message(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])

    def fake_gemini(api_key, model, system, contents, tools, on_event):
        return ([{"functionCall": {
            "name": "propose_generation",
            "args": {"generation_type": "quiz", "title": "Quiz", "discussion_summary": "Summary"},
            "id": "fc1",
        }}], True)

    monkeypatch.setattr(llm, "_pageindex_stream_call_gemini", fake_gemini)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        result = llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="make a quiz",
            model="gemini-2.5-flash",
            api_key="gm-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="gemini",
        )

    assert result[0] == llm.GENERATION_PROPOSAL_READY_MESSAGE


def test_openai_synthesis_retries_retrieval_preamble(monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "_dispatch_pageindex_tool", lambda **kwargs: ("retrieved page content", {}))
    final_calls = 0

    def fake_stream(api_key, model, msgs, tools, on_event):
        nonlocal final_calls
        if tools:
            return ({
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_page_content", "arguments": '{"material_id": 10, "pages": "1"}'},
                }],
            }, "tool_calls")
        final_calls += 1
        if final_calls == 1:
            return ({"content": "I'll fetch the relevant pages and summarize them.", "tool_calls": None}, "stop")
        return ({"content": "MDPs are decision models.", "tool_calls": None}, "stop")

    monkeypatch.setattr(llm, "_pageindex_stream_call", fake_stream)
    pageindex_mock = MagicMock()
    pageindex_mock.get_course_routing_index.return_value = []
    with patch.dict(sys.modules, {"pageindex_retrieval": pageindex_mock}):
        result = llm.run_agent_pageindex(
            conn=MagicMock(),
            user_message="What are MDPs?",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=1,
            course_id=2,
            context_material_ids=[],
            provider="openai",
        )

    assert result[0] == "MDPs are decision models."
    assert result[3]["repair_invoked"] is True


def test_retrieval_budget_for_128k_model_window():
    budget = llm._retrieval_budget_for("gpt-4o-mini")

    assert budget["window"] == 128000
    assert budget["base_tokens"] == 15360
    assert budget["max_tokens"] == 32000
    assert budget["raw_tokens"] == 9984
    assert budget["summary_tokens"] == 5376


def test_retrieval_budget_clamps_large_model_window():
    budget = llm._retrieval_budget_for("gpt-4.1")

    assert budget["window"] == 1000000
    assert budget["base_tokens"] == 48000
    assert budget["max_tokens"] == 48000


def test_retrieval_budget_can_expand_for_broad_questions():
    budget = llm._retrieval_budget_for("gpt-4o-mini", expanded=True)

    assert budget["base_tokens"] == 15360
    assert budget["active_tokens"] == 32000


def test_parse_retrieval_scope_accepts_agent_outputs():
    assert llm._parse_retrieval_scope("broad") == "broad"
    assert llm._parse_retrieval_scope('{"scope":"broad"}') == "broad"
    assert llm._parse_retrieval_scope("This is specific.") == "specific"


def test_retrieval_budget_uses_scope_to_choose_base_or_max_slice():
    specific = llm._retrieval_budget_for_scope("gpt-4o-mini", "specific")
    broad = llm._retrieval_budget_for_scope("gpt-4o-mini", "broad")

    assert specific["active_tokens"] == specific["base_tokens"]
    assert broad["active_tokens"] == broad["max_tokens"]


def test_history_budget_subtracts_reserved_retrieval_tokens():
    budget = llm._history_budget(
        window=10000,
        system_text="s" * 400,
        current_user_text="u" * 400,
        reserved_retrieval_tokens=1000,
    )

    expected_without_history_cap = (
        10000
        - 100
        - llm.RESPONSE_RESERVE_TOKENS
        - 100
        - int(10000 * llm.SAFETY_MARGIN_RATIO)
        - 1000
    )
    assert budget == min(int(10000 * llm.HISTORY_CONTEXT_RATIO), expected_without_history_cap)


def test_normalize_page_candidates_expands_and_dedupes_pages():
    candidates = [
        {"material_id": 742, "pages": "6-8", "reason": "definition", "priority": "core"},
        {"material_id": 742, "pages": "8,9", "reason": "continuation", "priority": "supporting"},
        {"material_id": 743, "pages": "2", "reason": "example", "priority": "background"},
    ]

    normalized, dropped = llm._normalize_page_candidates(candidates)

    assert dropped == 0
    assert normalized == [
        {"material_id": 742, "page": 6, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 7, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 8, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 9, "reason": "continuation", "priority": "supporting"},
        {"material_id": 743, "page": 2, "reason": "example", "priority": "background"},
    ]


def test_normalize_page_candidates_drops_malformed_candidates():
    candidates = [
        {"material_id": "bad", "pages": "1"},
        {"material_id": 742, "pages": "x-y"},
        {"material_id": 742, "pages": "3"},
    ]

    normalized, dropped = llm._normalize_page_candidates(candidates)

    assert dropped == 2
    assert normalized == [
        {"material_id": 742, "page": 3, "reason": "", "priority": "supporting"},
    ]


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params):
        pass

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


def test_get_page_section_summaries_returns_matching_sections():
    from pageindex_retrieval import get_page_section_summaries

    conn = _FakeConn(
        [
            {
                "material_id": 742,
                "material_title": "Lecture 4",
                "nodes": [
                    {"start_page": 1, "end_page": 3, "summary": "Intro", "token_count": 300},
                    {"start_page": 4, "end_page": 6, "summary": "MDP setup", "token_count": 600},
                ],
            }
        ]
    )

    summaries = get_page_section_summaries(conn, [742])

    assert summaries[(742, 4)]["summary"] == "MDP setup"
    assert summaries[(742, 4)]["token_count"] == 600
    assert summaries[(742, 6)]["title"] == "Lecture 4"
