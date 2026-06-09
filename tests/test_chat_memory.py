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
