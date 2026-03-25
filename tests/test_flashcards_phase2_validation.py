import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda", "flashcards_generate"))


def test_flashcards_token_estimator_output_shape_and_sanity():
    from api.services.flashcards_token_estimator import estimate_flashcards_token_ranges

    estimate = estimate_flashcards_token_ranges(
        system_prompt="You are a flashcards generator.",
        user_prompt="Generate cards on topic X.",
        card_count=12,
        depth="moderate",
    )

    keys = {
        "estimated_prompt_tokens_low",
        "estimated_prompt_tokens_high",
        "estimated_total_tokens_low",
        "estimated_total_tokens_high",
    }
    assert set(estimate.keys()) == keys
    assert estimate["estimated_prompt_tokens_low"] >= 0
    assert estimate["estimated_prompt_tokens_high"] >= estimate["estimated_prompt_tokens_low"]
    assert estimate["estimated_total_tokens_low"] >= estimate["estimated_prompt_tokens_low"]
    assert estimate["estimated_total_tokens_high"] >= estimate["estimated_total_tokens_low"]


def test_worker_normalization_aliases_and_count_trim():
    from handler import _validate_and_normalize_cards

    raw = {
        "title": "Deck",
        "cards": [
            {"front": "F1", "back": "B1", "hint": "H1"},
            {"term": "F2", "definition": "B2"},
            {"question": "F3", "answer": "B3"},
        ],
    }

    title, cards = _validate_and_normalize_cards(raw, expected_count=2)
    assert title == "Deck"
    assert len(cards) == 2
    assert cards[0]["front_text"] == "F1"
    assert cards[1]["front_text"] == "F2"


def test_worker_normalization_rejects_missing_front_or_back():
    import pytest
    from handler import _validate_and_normalize_cards

    with pytest.raises(ValueError, match="missing front text"):
        _validate_and_normalize_cards({"cards": [{"back": "Only back"}]}, expected_count=1)

    with pytest.raises(ValueError, match="missing back text"):
        _validate_and_normalize_cards({"cards": [{"front": "Only front"}]}, expected_count=1)


def test_flashcards_pdf_builder_builds_bytes_with_mock_weasyprint(monkeypatch):
    class FakeHTML:
        def __init__(self, string=None):
            self.string = string

        def write_pdf(self):
            return b"%PDF-1.4\n%fake\n"

    fake_weasyprint = types.SimpleNamespace(HTML=FakeHTML)
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)

    from api.services.flashcards_pdf_builder import build_flashcards_pdf_bytes

    pdf = build_flashcards_pdf_bytes(
        deck={
            "title": "Deck 1",
            "topic": "Topic",
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "generated_at": "2026-03-25",
            "cards": [
                {"card_index": 0, "front": "What is X?", "back": "X is ...", "hint": "starts with X"},
            ],
        }
    )
    assert isinstance(pdf, (bytes, bytearray))
    assert len(pdf) > 8
    assert bytes(pdf).startswith(b"%PDF")
