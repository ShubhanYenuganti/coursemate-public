"""
Report template contracts — system+user prompt builders and output normalizer.

Each template produces a `sections[]` payload compatible with ReportsViewer's DocBlock.
"""
from __future__ import annotations

import json

VALID_TEMPLATES = ("study-guide", "briefing", "summary", "custom")
MAX_SECTIONS = 16
VALID_BLOCK_TYPES = frozenset({
    "heading", "subheading", "paragraph", "bullet_list",
    "callout", "equation", "page_break",
})

_COMMON_RULES = (
    "Return valid JSON only. No markdown fences, no preamble. "
    "Output must be json.loads() parseable.\n"
    "Rules:\n"
    "- Base all content strictly on provided course materials\n"
    "- Be thorough and detailed; cover all major topics in the provided material\n"
    "- Max 16 sections total\n"
    "- Keep page_count at the specified value\n"
    "- Each section should be substantive — paragraphs 3-5 sentences, bullet lists 4-8 items\n"
    "- IMPORTANT: If the provided materials contain substantial information, you MUST fill all "
    "page_count pages completely. Do not produce a short or thin report when rich source material "
    "is available. Aim for depth: expand each concept, define terms precisely, include examples, "
    "and cover every significant topic present in the materials.\n"
)

_STUDY_GUIDE_SYSTEM = (
    "You are an academic study guide generator. " + _COMMON_RULES +
    "Output format:\n"
    '{"title":"...","subtitle":"...","page_count":3,"sections":[\n'
    '  {"type":"heading","content":"Overview"},\n'
    '  {"type":"paragraph","content":"3-5 sentence overview of the full topic"},\n'
    '  {"type":"heading","content":"Key Concepts"},\n'
    '  {"type":"subheading","content":"<Concept Name>"},\n'
    '  {"type":"paragraph","content":"<Full definition with context, 3-4 sentences>"},\n'
    '  {"type":"subheading","content":"<Concept Name 2>"},\n'
    '  {"type":"paragraph","content":"<Full definition>"},\n'
    '  {"type":"heading","content":"Core Topics"},\n'
    '  {"type":"subheading","content":"<Topic Name>"},\n'
    '  {"type":"bullet_list","items":["detailed point 1","detailed point 2","detailed point 3","point 4"]},\n'
    '  {"type":"subheading","content":"<Topic Name 2>"},\n'
    '  {"type":"bullet_list","items":["point 1","point 2","point 3"]},\n'
    '  {"type":"heading","content":"Examples & Applications"},\n'
    '  {"type":"bullet_list","items":["concrete example 1","concrete example 2","concrete example 3"]},\n'
    '  {"type":"heading","content":"Summary"},\n'
    '  {"type":"callout","content":"5-7 key takeaways as a comprehensive paragraph"}\n'
    "]}"
)

_BRIEFING_SYSTEM = (
    "You are an executive briefing writer. " + _COMMON_RULES +
    "Output format:\n"
    '{"title":"...","subtitle":"Executive Summary","page_count":1,"sections":[\n'
    '  {"type":"heading","content":"Background"},\n'
    '  {"type":"paragraph","content":"3-4 sentence situation overview"},\n'
    '  {"type":"heading","content":"Key Points"},\n'
    '  {"type":"bullet_list","items":["point — one sentence each, 5-7 items"]},\n'
    '  {"type":"heading","content":"Critical Terms"},\n'
    '  {"type":"bullet_list","items":["Term — brief definition"]},\n'
    '  {"type":"heading","content":"Implications"},\n'
    '  {"type":"paragraph","content":"What this means and why it matters"},\n'
    '  {"type":"callout","content":"Bottom line in one sentence"}\n'
    "]}"
)

_SUMMARY_SYSTEM = (
    "You are a document summarizer. " + _COMMON_RULES +
    "Output format:\n"
    '{"title":"Summary — <source topic>","subtitle":"","page_count":3,"sections":[\n'
    '  {"type":"heading","content":"Overview"},\n'
    '  {"type":"paragraph","content":"3-4 sentence scope description"},\n'
    '  {"type":"heading","content":"<LLM-generated topic name 1>"},\n'
    '  {"type":"paragraph","content":"4-5 sentence summary of this topic"},\n'
    '  {"type":"heading","content":"<LLM-generated topic name 2>"},\n'
    '  {"type":"paragraph","content":"4-5 sentence summary"},\n'
    '  {"type":"heading","content":"<LLM-generated topic name 3>"},\n'
    '  {"type":"paragraph","content":"4-5 sentence summary"},\n'
    '  {"type":"heading","content":"<LLM-generated topic name 4>"},\n'
    '  {"type":"paragraph","content":"4-5 sentence summary"},\n'
    '  {"type":"heading","content":"Key Takeaways"},\n'
    '  {"type":"bullet_list","items":["takeaway 1","takeaway 2","takeaway 3","takeaway 4","takeaway 5"]}\n'
    "]}"
)

_CUSTOM_FILL_SYSTEM = (
    "You are a document content generator. " + _COMMON_RULES +
    "You are given a JSON schema with 'instructions' fields. "
    "Replace every 'instructions' value with actual content generated from the course materials. "
    "Preserve all other fields (type, name, page_count) exactly. "
    "Output the completed schema JSON."
)


def build_report_prompt(
    *,
    template_id: str,
    material_context: str,
    custom_prompt: str | None,
    synthesized_schema: dict | None,
) -> tuple[str, str]:
    del custom_prompt
    context_block = f"Course materials:\n{material_context or 'No materials provided.'}"

    if template_id == "study-guide":
        return _STUDY_GUIDE_SYSTEM, context_block

    if template_id == "briefing":
        return _BRIEFING_SYSTEM, context_block

    if template_id == "summary":
        return _SUMMARY_SYSTEM, context_block

    if template_id == "custom":
        if not synthesized_schema:
            raise ValueError("custom template requires synthesized_schema (from Call 1)")
        schema_str = json.dumps(synthesized_schema, ensure_ascii=False)
        user = f"Schema to fill:\n{schema_str}\n\n{context_block}"
        return _CUSTOM_FILL_SYSTEM, user

    raise ValueError(f"Unknown template_id: {template_id!r}")


def _safe_page_count(value: object) -> int:
    try:
        if isinstance(value, bool):
            return 2
        parsed = int(value)
        return parsed if parsed > 0 else 2
    except (TypeError, ValueError):
        return 2


def normalize_report_sections(raw: dict) -> dict:
    """Normalize LLM output to a ReportsViewer-compatible payload."""
    raw = raw or {}
    title = str(raw.get("title") or "Report").strip() or "Report"
    subtitle = str(raw.get("subtitle") or "").strip()
    page_count = _safe_page_count(raw.get("page_count") or 2)

    raw_sections = raw.get("sections") or raw.get("sections_json") or []
    if not isinstance(raw_sections, list):
        raw_sections = []

    normalized = []
    for block in raw_sections:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type") or "").lower().strip()
        if btype not in VALID_BLOCK_TYPES:
            if isinstance(block.get("items"), list):
                btype = "bullet_list"
            else:
                btype = "paragraph"

        content = str(block.get("content") or block.get("text") or "").strip()
        lines = block.get("lines")
        if isinstance(lines, list):
            lines = [str(line).strip() for line in lines if str(line).strip()]
        else:
            lines = None
        items = block.get("items")
        if isinstance(items, list):
            items = [str(i) for i in items if str(i).strip()]
        else:
            items = None

        if not content and not items and not lines and btype != "page_break":
            continue

        entry: dict = {"type": btype}
        if content:
            entry["content"] = content
        if lines is not None:
            entry["lines"] = lines
        if items is not None:
            entry["items"] = items

        normalized.append(entry)
        if len(normalized) >= MAX_SECTIONS:
            break

    return {
        "title": title,
        "subtitle": subtitle,
        "page_count": page_count,
        "sections": normalized,
    }
