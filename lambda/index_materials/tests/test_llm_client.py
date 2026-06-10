import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from llm_client import (
    build_doc_summary_prompt,
    build_node_keywords_prompt,
    build_node_summary_prompt,
    describe_visuals,
    extract_tags,
    summarize,
)


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


def test_build_node_keywords_prompt_requests_json_array():
    prompt = build_node_keywords_prompt("reading", "Transformer attention datasets")
    assert "JSON array" in prompt
    assert "Transformer attention datasets" in prompt


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


def test_describe_visuals_sends_multimodal_message():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"visual_summary": "A diagram", "detected_figures": [], "detected_tables": []}'}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("llm_client.requests.post", return_value=mock_resp) as mock_post:
        result = describe_visuals("abc123base64encoded", "sk-test")

    assert "visual_summary" in result
    call_json = mock_post.call_args[1]["json"]
    assert call_json["model"] == "gpt-4o-mini"
    content = call_json["messages"][0]["content"]
    assert any(c.get("type") == "image_url" for c in content)
    assert any(c.get("type") == "text" for c in content)
    image_part = next(c for c in content if c.get("type") == "image_url")
    assert "abc123base64encoded" in image_part["image_url"]["url"]
