import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.reports_token_estimator import estimate_reports_token_ranges


def test_estimate_returns_four_keys():
    result = estimate_reports_token_ranges(
        system_prompt="x" * 1000,
        user_prompt="y" * 500,
        template_id="study-guide",
    )
    for key in (
        "estimated_prompt_tokens_low",
        "estimated_prompt_tokens_high",
        "estimated_total_tokens_low",
        "estimated_total_tokens_high",
    ):
        assert key in result


def test_briefing_has_lower_output_than_study_guide():
    base = dict(system_prompt="x" * 1000, user_prompt="y" * 500)
    briefing = estimate_reports_token_ranges(**base, template_id="briefing")
    guide = estimate_reports_token_ranges(**base, template_id="study-guide")
    assert briefing["estimated_total_tokens_high"] < guide["estimated_total_tokens_high"]


def test_total_ge_prompt():
    result = estimate_reports_token_ranges(
        system_prompt="x" * 800, user_prompt="y" * 400, template_id="summary"
    )
    assert result["estimated_total_tokens_low"] >= result["estimated_prompt_tokens_low"]

from api.services.reports_contracts import (
    VALID_TEMPLATES,
    build_report_prompt,
    normalize_report_sections,
)


def test_valid_templates():
    assert set(VALID_TEMPLATES) == {"study-guide", "briefing", "summary", "custom"}


def test_build_prompt_returns_strings():
    system, user = build_report_prompt(
        template_id="study-guide",
        material_context="Some content about robotics.",
        custom_prompt=None,
        synthesized_schema=None,
    )
    assert isinstance(system, str) and len(system) > 50
    assert isinstance(user, str) and "robotics" in user


def test_custom_template_requires_synthesized_schema():
    try:
        build_report_prompt(
            template_id="custom",
            material_context="Some content about robotics.",
            custom_prompt="Focus on tradeoffs.",
            synthesized_schema=None,
        )
    except ValueError as exc:
        assert "synthesized_schema" in str(exc)
    else:
        raise AssertionError("Expected ValueError when custom schema is missing")


def test_normalize_sections_strips_bad_types():
    raw = {
        "title": "T",
        "sections": [
            {"type": "heading", "content": "A"},
            {"type": "UNKNOWN_TYPE", "content": "B"},
            {"items": ["x", "y"]},
        ],
    }
    result = normalize_report_sections(raw)
    assert result["title"] == "T"
    types = [s["type"] for s in result["sections"]]
    assert "heading" in types


def test_normalize_enforces_max_sections():
    raw = {
        "title": "T",
        "sections": [{"type": "paragraph", "content": str(i)} for i in range(20)],
    }
    result = normalize_report_sections(raw)
    assert len(result["sections"]) <= 8

from api.services.reports_pdf_builder import build_reports_pdf_html


def test_pdf_html_contains_title():
    payload = {
        "title": "Robotics Study Guide",
        "subtitle": "Key concepts",
        "sections": [
            {"type": "heading", "content": "Overview"},
            {"type": "paragraph", "content": "This covers SLAM."},
            {"type": "bullet_list", "items": ["point A", "point B"]},
        ],
    }
    html = build_reports_pdf_html(report=payload)
    assert "Robotics Study Guide" in html
    assert "Overview" in html
    assert "point A" in html
