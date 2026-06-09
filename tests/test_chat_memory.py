"""Unit tests for multi-turn chat memory helpers in api/llm.py."""
import sys
import os
from unittest.mock import MagicMock

# Stub heavy imports so llm.py can load without a real environment.
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
    # reserve=RESPONSE_RESERVE_TOKENS, margin=SAFETY_MARGIN_RATIO of window.
    budget = llm._history_budget(
        window=10000,
        system_text="s" * 160,
        current_user_text="u" * 40,
    )
    expected = 10000 - 40 - llm.RESPONSE_RESERVE_TOKENS - 10 - int(10000 * llm.SAFETY_MARGIN_RATIO)
    assert budget == expected


def test_history_budget_never_negative():
    budget = llm._history_budget(window=10, system_text="x" * 1000, current_user_text="y" * 1000)
    assert budget == 0


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
