import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from llm_client import build_node_summary_prompt, build_doc_summary_prompt, summarize, extract_tags


def test_node_summary_prompt_for_slides():
    prompt = build_node_summary_prompt("lecture_slide", "Chain Rule\n\ndy/dx = dy/du * du/dx")
    assert "120 tokens" in prompt or "equation" in prompt.lower() or "concept" in prompt.lower()


def test_node_summary_prompt_for_hw():
    prompt = build_node_summary_prompt("hw_instruction", "Problem 1\nDerive the gradient.")
    assert "concept" in prompt.lower() or "problem" in prompt.lower()


def test_doc_summary_prompt_includes_nodes():
    prompt = build_doc_summary_prompt("Lecture 5", "lecture_slide", ["Intro", "Backprop", "Conclusion"])
    assert "Lecture 5" in prompt
    assert "Intro" in prompt


def test_summarize_calls_openai_and_returns_text():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Summary of content."}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("llm_client.requests.post", return_value=mock_resp) as mock_post:
        result = summarize("Some prompt", "sk-test")
        assert result == "Summary of content."
        mock_post.assert_called_once()
        call_json = mock_post.call_args[1]["json"]
        assert call_json["model"] == "gpt-4o-mini"


def test_extract_tags_parses_json_array():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '["backpropagation", "chain-rule", "gradient-descent"]'}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("llm_client.requests.post", return_value=mock_resp):
        tags = extract_tags("extract tags prompt", "sk-test")
    assert "backpropagation" in tags
    assert "chain-rule" in tags


def test_extract_tags_returns_empty_on_bad_json():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "No tags found."}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("llm_client.requests.post", return_value=mock_resp):
        tags = extract_tags("prompt", "sk-test")
    assert tags == []
