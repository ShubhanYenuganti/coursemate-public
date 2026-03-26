import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.reports_contracts import (
    MAX_SECTIONS,
    VALID_TEMPLATES,
    build_report_prompt,
    normalize_report_sections,
)
from api.services.reports_pdf_builder import build_reports_pdf_html
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
        system_prompt="x" * 800,
        user_prompt="y" * 400,
        template_id="summary",
    )
    assert result["estimated_total_tokens_low"] >= result["estimated_prompt_tokens_low"]


def test_valid_templates_match_task_2_contract():
    assert VALID_TEMPLATES == ("study-guide", "briefing", "summary", "custom")


def test_prompt_shapes_for_builtins_match_task_2():
    for template_id in ("study-guide", "briefing", "summary"):
        system, user = build_report_prompt(
            template_id=template_id,
            material_context="Robotics notes.",
            custom_prompt=None,
            synthesized_schema=None,
        )
        assert user == "Course materials:\nRobotics notes."
        assert '"sections"' in system

    study_system, _ = build_report_prompt(
        template_id="study-guide",
        material_context="x",
        custom_prompt=None,
        synthesized_schema=None,
    )
    assert '"page_count":2' in study_system
    assert '{"type":"heading","content":"Key Concepts"}' in study_system
    assert '{"type":"heading","content":"Core Topics"}' in study_system
    assert '{"type":"heading","content":"Examples"}' in study_system

    briefing_system, _ = build_report_prompt(
        template_id="briefing",
        material_context="x",
        custom_prompt=None,
        synthesized_schema=None,
    )
    assert '"page_count":1' in briefing_system
    assert '{"type":"heading","content":"Key Points"}' in briefing_system
    assert '{"type":"heading","content":"Critical Terms"}' in briefing_system
    assert '{"type":"heading","content":"Implications"}' in briefing_system

    summary_system, _ = build_report_prompt(
        template_id="summary",
        material_context="x",
        custom_prompt=None,
        synthesized_schema=None,
    )
    assert '{"type":"heading","content":"<LLM-generated topic name 1>"}' in summary_system
    assert '{"type":"heading","content":"<LLM-generated topic name 2>"}' in summary_system
    assert '{"type":"heading","content":"Key Takeaways"}' in summary_system


def test_build_report_prompt_for_custom_starts_with_schema_to_fill():
    schema = {"type": "object", "properties": {"title": {"type": "string"}}}
    schema_json = json.dumps(schema, ensure_ascii=False)
    system, user = build_report_prompt(
        template_id="custom",
        material_context="Lecture excerpt.",
        custom_prompt="Ignored by Task 2 prompt shape.",
        synthesized_schema=schema,
    )
    assert "instructions" in system
    assert user.startswith(f"Schema to fill:\n{schema_json}\n\nCourse materials:\nLecture excerpt.")


def test_normalize_report_sections_defaults_inference_and_equation():
    raw = {
        "page_count": "oops",
        "sections": [
            {"type": "unknown", "items": ["a", "b"]},
            {"type": "unknown", "content": "Paragraph body"},
            {"type": "equation", "lines": ["E = mc^2"]},
        ],
    }
    result = normalize_report_sections(raw)
    assert result["title"] == "Report"
    assert result["subtitle"] == ""
    assert result["page_count"] == 2
    assert result["sections"] == [
        {"type": "bullet_list", "items": ["a", "b"]},
        {"type": "paragraph", "content": "Paragraph body"},
        {"type": "equation", "lines": ["E = mc^2"]},
    ]


def test_normalize_report_sections_caps_to_max_sections():
    raw = {
        "sections": [
            {"type": "paragraph", "content": f"section {idx}"}
            for idx in range(MAX_SECTIONS + 3)
        ]
    }
    result = normalize_report_sections(raw)
    assert len(result["sections"]) == MAX_SECTIONS


def test_custom_template_requires_synthesized_schema():
    with pytest.raises(ValueError, match=r"custom template requires synthesized_schema \(from Call 1\)"):
        build_report_prompt(
            template_id="custom",
            material_context="Lecture excerpt.",
            custom_prompt=None,
            synthesized_schema=None,
        )


def test_pdf_html_contains_title():
    html = build_reports_pdf_html(
        report={
            "title": "Robotics Study Guide",
            "sections": [{"type": "paragraph", "content": "This covers SLAM."}],
        }
    )
    assert "Robotics Study Guide" in html
