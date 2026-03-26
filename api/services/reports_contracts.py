"""Prompt contracts and normalization for reports generation."""
from __future__ import annotations

import json
from typing import Iterable

VALID_TEMPLATES = ("study-guide", "briefing", "summary", "custom")
MAX_SECTIONS = 8
_VALID_SECTION_TYPES = {
    "heading",
    "section",
    "subheading",
    "subsection",
    "paragraph",
    "bullet_list",
    "list",
    "callout",
    "equation",
    "display_equation",
    "page_break",
}

_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "sections"],
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "date": {"type": "string"},
        "sections": {
            "type": "array",
            "maxItems": MAX_SECTIONS,
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["type"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": sorted(_VALID_SECTION_TYPES),
                    },
                    "content": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                    "lines": {"type": "array", "items": {"type": "string"}},
                    "page": {"type": "string"},
                },
            },
        },
    },
}

_TEMPLATE_GUIDANCE = {
    "study-guide": (
        "Create a structured study guide with clear headings, concise explanations, "
        "and bullet points for key facts, definitions, and examples."
    ),
    "briefing": (
        "Create an executive briefing optimized for rapid comprehension. Prioritize "
        "high-signal synthesis, risks, takeaways, and short sections."
    ),
    "summary": (
        "Create a concise summary of the selected material. Focus on the main ideas, "
        "supporting points, and the most important conclusions."
    ),
    "custom": (
        "Follow the user's custom reporting objective while still returning the exact "
        "JSON shape described by the schema."
    ),
}


def _schema_text(synthesized_schema: str | None) -> str:
    if synthesized_schema:
        return synthesized_schema.strip()
    return json.dumps(_OUTPUT_SCHEMA, indent=2, sort_keys=True)


def _coerce_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _coerce_text(value)
        if text:
            result.append(text)
    return result


def _infer_type(section: dict) -> str:
    raw_type = _coerce_text(section.get("type")).lower().replace("-", "_")
    if raw_type in _VALID_SECTION_TYPES:
        return raw_type
    if section.get("items"):
        return "bullet_list"
    if section.get("lines"):
        return "equation"
    page = _coerce_text(section.get("page"))
    if page:
        return "page_break"
    content = _coerce_text(section.get("content") or section.get("text"))
    if len(content) <= 90 and content and content == content.upper():
        return "heading"
    if len(content) <= 90 and content:
        return "paragraph"
    return "paragraph"


def build_report_prompt(
    *,
    template_id: str,
    material_context: str,
    custom_prompt: str | None,
    synthesized_schema: str | None,
) -> tuple[str, str]:
    template_key = template_id if template_id in VALID_TEMPLATES else "summary"
    if template_key == "custom" and not _coerce_text(synthesized_schema):
        raise ValueError("template_id='custom' requires synthesized_schema")
    schema_text = _schema_text(synthesized_schema)
    system = (
        "You generate structured course reports. Return valid JSON only. "
        "Do not wrap the output in markdown or prose. Use no more than "
        f"{MAX_SECTIONS} sections.\n\n"
        "Output schema:\n"
        f"{schema_text}\n\n"
        "Requirements:\n"
        "- Include a concise title.\n"
        "- Use section types supported by the schema only.\n"
        "- Prefer bullet_list for enumerations and paragraph for exposition.\n"
        "- Keep claims grounded in the provided material context."
    )

    guidance = _TEMPLATE_GUIDANCE[template_key]
    custom_line = (
        f"Custom instructions:\n{custom_prompt.strip()}\n\n"
        if template_key == "custom" and _coerce_text(custom_prompt)
        else ""
    )
    user = (
        f"Template: {template_key}\n"
        f"Goal: {guidance}\n\n"
        f"{custom_line}"
        "Material context:\n"
        f"{_coerce_text(material_context)}"
    )
    return system, user


def normalize_report_sections(raw: dict | None) -> dict:
    raw = raw or {}
    normalized = {
        "title": _coerce_text(raw.get("title")) or "Untitled Report",
        "subtitle": _coerce_text(raw.get("subtitle")),
        "date": _coerce_text(raw.get("date") or raw.get("generated_at")),
        "sections": [],
    }

    sections = raw.get("sections")
    if not isinstance(sections, list):
        sections = []

    for raw_section in sections:
        if not isinstance(raw_section, dict):
            continue
        section_type = _infer_type(raw_section)
        content = _coerce_text(raw_section.get("content") or raw_section.get("text"))
        items = _string_list(raw_section.get("items") or [])
        lines = _string_list(raw_section.get("lines") or [])
        page = _coerce_text(raw_section.get("page"))

        section: dict[str, object] = {"type": section_type}
        if section_type in {"bullet_list", "list"}:
            if items:
                section["items"] = items
            elif content:
                section["items"] = [content]
            else:
                continue
        elif section_type in {"equation", "display_equation"}:
            if lines:
                section["lines"] = lines
            elif content:
                section["lines"] = [content]
            else:
                continue
        elif section_type == "page_break":
            if page:
                section["page"] = page
            elif content:
                section["page"] = content
        else:
            if not content:
                if items:
                    section = {"type": "bullet_list", "items": items}
                else:
                    continue
            else:
                section["content"] = content

        normalized["sections"].append(section)
        if len(normalized["sections"]) >= MAX_SECTIONS:
            break

    return normalized
