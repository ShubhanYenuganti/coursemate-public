# Reports Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

---

## How to Execute This Plan (Subagent-Driven)

To pick this up in a new session, paste the following prompt to Claude Code:

```
Use the superpowers:subagent-driven-development skill to implement the plan at:
  docs/superpowers/plans/2026-03-25-reports-generation.md

Start at Task 1. Work task-by-task: dispatch a fresh subagent per task, review the output between tasks, check off completed steps, and move to the next task only after the current one passes review.

Key reference files for context:
  - api/flashcards.py          (estimate/generate/enqueue pattern)
  - lambda/flashcards_generate/handler.py   (Lambda lifecycle + dict_row pattern)
  - src/Quiz.jsx               (PROVIDER_MODELS, GenerationConfirmModal usage)
  - src/components/GenerationConfirmModal.jsx  (actual prop interface)
  - api/db.py                  (schema append location ~line 560)
  - api/services/              (existing service files to mirror)
```

The plan is fully reviewed and approved. All tasks have unchecked `- [ ]` boxes — check them off as each step completes.

---

**Goal:** Implement end-to-end async report generation with SQS + Lambda worker, 4 template contracts (study-guide, briefing, summary, custom layered-LLM), viewer-compatible structured output, and frontend estimate → confirm → poll → ReportsViewer flow.

**Architecture:** `api/reports.py` acts as queue-only orchestrator (estimate, generate→202, status/get/list, save, export, delete). The Lambda worker `reports_generate` runs all LLM work: fixed-schema contracts for built-in templates and a two-call pipeline for custom (schema synthesis → content fill). Output is a `sections[]` array stored in `report_versions` and rendered by the existing `ReportsViewer`.

**Tech Stack:** Python 3 / psycopg (PostgreSQL), requests (provider REST APIs), AWS SQS + Lambda, React + Tailwind CSS, Vercel Python Serverless, pytest

**Token strategy:** 2 focused pages max (Briefing = 1 page). Max 8 sections, ~150 words each → ~1,600–2,500 output tokens. Stays within all provider limits without timeouts.

---

## File Map

| File | Change | Responsibility |
|---|---|---|
| `api/db.py` | Modify | Add `report_generations` + `report_versions` tables, lifecycle constraints, indexes |
| `api/reports.py` | Create | All reports API actions and SQS queue orchestration (no LLM) |
| `api/services/reports_token_estimator.py` | Create | Deterministic token-range estimation by template |
| `api/services/reports_contracts.py` | Create | System+user prompt builders for all 4 templates |
| `api/services/reports_pdf_builder.py` | Create | HTML→PDF export from persisted sections_json |
| `lambda/reports_generate/handler.py` | Create | SQS-triggered worker: lifecycle transitions, dual-path LLM, persistence |
| `lambda/reports_generate/db.py` | Create | Worker DB helpers (mirror `lambda/flashcards_generate/db.py`) |
| `lambda/reports_generate/Dockerfile` | Create | Container image (mirror flashcards) |
| `lambda/reports_generate/requirements.txt` | Create | Worker runtime deps |
| `lambda/reports_generate/build.sh` | Create | ECR build/push + Lambda create/update + instructions |
| `lambda/reports_generate/iam/api-send-message-policy.json` | Create | API enqueue permission template |
| `lambda/reports_generate/iam/worker-consume-policy.json` | Create | Worker consume permission template |
| `scripts/infra/setup_reports_generation_infra.sh` | Create | Event source mapping + env var instructions |
| `src/Reports.jsx` | Modify | estimate → GenerationConfirmModal → generate → poll → ReportsViewer |
| `src/ReportsViewer.jsx` | Modify | Wire save/export/regenerate actions to backend |
| `tests/test_reports_validation.py` | Create | Estimator, contract normalization, PDF builder tests |

---

## Task 1: Database Schema

**Files:**
- Modify: `api/db.py`

### Background

Pattern: add a new `cursor.execute("""...""")` block after the flashcards block (line ~560). Use `ADD COLUMN IF NOT EXISTS` and `DROP CONSTRAINT IF EXISTS` + re-add for status, so re-running `init_db()` is idempotent.

- [x] **Step 1: Add `report_generations` + `report_versions` tables**

Append to `init_db()` in `api/db.py` after the flashcards section:

```python
        # Reports generation tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_generations (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                generated_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                template_id VARCHAR(30) NOT NULL DEFAULT 'study-guide',
                custom_prompt TEXT,
                provider VARCHAR(20),
                model_id VARCHAR(100),
                status VARCHAR(20) NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'queued', 'generating', 'ready', 'failed')),
                error TEXT,
                parent_generation_id INTEGER REFERENCES report_generations(id) ON DELETE SET NULL,
                artifact_material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                selected_material_ids JSONB,
                generation_settings JSONB,
                prompt_text TEXT,
                estimated_prompt_tokens_low INTEGER,
                estimated_prompt_tokens_high INTEGER,
                estimated_total_tokens_low INTEGER,
                estimated_total_tokens_high INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS report_versions (
                id SERIAL PRIMARY KEY,
                generation_id INTEGER NOT NULL REFERENCES report_generations(id) ON DELETE CASCADE,
                version_number INTEGER NOT NULL DEFAULT 1,
                title TEXT,
                subtitle TEXT,
                page_count INTEGER NOT NULL DEFAULT 2,
                sections_json JSONB NOT NULL DEFAULT '[]',
                template_snapshot JSONB,
                source_snapshot JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_gen_course ON report_generations(course_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_gen_course_user ON report_generations(course_id, generated_by, created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_gen_status ON report_generations(status, created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_versions_gen ON report_versions(generation_id);")
```

- [x] **Step 2: Verify schema compiles**

```bash
python3 -m py_compile api/db.py
```
Expected: no output (success).

- [x] **Step 3: Commit**

```bash
git add api/db.py
git commit -m "feat(db): add report_generations and report_versions tables"
```

---

## Task 2: Services Layer

**Files:**
- Create: `api/services/reports_token_estimator.py`
- Create: `api/services/reports_contracts.py`
- Create: `api/services/reports_pdf_builder.py`

- [x] **Step 0: Ensure services directory exists**

```bash
mkdir -p api/services
ls api/services/
```
Expected: directory exists (may already contain flashcards/quiz service files).

### 2a: Token Estimator

- [x] **Step 1: Write failing test**

In `tests/test_reports_validation.py`:

```python
from api.services.reports_token_estimator import estimate_reports_token_ranges


def test_estimate_returns_four_keys():
    result = estimate_reports_token_ranges(
        system_prompt="x" * 1000,
        user_prompt="y" * 500,
        template_id="study-guide",
    )
    for key in ("estimated_prompt_tokens_low", "estimated_prompt_tokens_high",
                "estimated_total_tokens_low", "estimated_total_tokens_high"):
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
```

- [x] **Step 2: Run to confirm failure**

```bash
python3 -m pytest tests/test_reports_validation.py::test_estimate_returns_four_keys -v
```
Expected: `ModuleNotFoundError` or `ImportError`.

- [x] **Step 3: Implement estimator**

Create `api/services/reports_token_estimator.py`:

```python
"""Reports token estimation heuristics."""
from __future__ import annotations

# Output token budgets per template (low, high)
_OUTPUT_BUDGETS = {
    "study-guide": (1_500, 2_500),
    "briefing":    (800,   1_200),
    "summary":     (1_200, 2_000),
    "custom":      (1_000, 2_500),  # two-call pipeline combined
}


def _approx_tokens(char_count: int, low_f: float, high_f: float) -> tuple[int, int]:
    base = max(0, char_count) / 4.0
    return int(base * low_f), int(base * high_f)


def estimate_reports_token_ranges(
    *,
    system_prompt: str,
    user_prompt: str,
    template_id: str,
) -> dict:
    prompt_chars = len(system_prompt or "") + len(user_prompt or "")
    p_low, p_high = _approx_tokens(prompt_chars, 0.85, 1.15)
    o_low, o_high = _OUTPUT_BUDGETS.get(template_id, (1_200, 2_000))
    return {
        "estimated_prompt_tokens_low": p_low,
        "estimated_prompt_tokens_high": p_high,
        "estimated_total_tokens_low": p_low + o_low,
        "estimated_total_tokens_high": p_high + o_high,
    }
```

- [x] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_reports_validation.py::test_estimate_returns_four_keys tests/test_reports_validation.py::test_briefing_has_lower_output_than_study_guide tests/test_reports_validation.py::test_total_ge_prompt -v
```
Expected: 3 PASSED.

### 2b: Template Contracts

The contracts module defines system+user prompt builders for each of the 4 templates. Each returns `(system: str, user: str)`. The system prompt embeds the exact JSON schema the LLM must output.

- [x] **Step 5: Write contract normalization test**

Add to `tests/test_reports_validation.py`:

```python
from api.services.reports_contracts import (
    build_report_prompt,
    normalize_report_sections,
    VALID_TEMPLATES,
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


def test_normalize_sections_strips_bad_types():
    raw = {"title": "T", "sections": [
        {"type": "heading", "content": "A"},
        {"type": "UNKNOWN_TYPE", "content": "B"},
        {"items": ["x", "y"]},  # missing type — should default to bullet_list
    ]}
    result = normalize_report_sections(raw)
    assert result["title"] == "T"
    types = [s["type"] for s in result["sections"]]
    assert "heading" in types


def test_normalize_enforces_max_sections():
    raw = {"title": "T", "sections": [{"type": "paragraph", "content": str(i)} for i in range(20)]}
    result = normalize_report_sections(raw)
    assert len(result["sections"]) <= 8
```

- [x] **Step 6: Run to confirm failure**

```bash
python3 -m pytest tests/test_reports_validation.py -k "contract or template or normalize" -v
```
Expected: `ImportError`.

- [x] **Step 7: Implement contracts**

Create `api/services/reports_contracts.py`:

```python
"""
Report template contracts — system+user prompt builders and output normalizer.

Each template produces a `sections[]` payload compatible with ReportsViewer's DocBlock.

Templates:
  study-guide — 2 pages: Overview, Key Concepts (subsections), Core Topics, Examples, Summary callout
  briefing    — 1 page:  Background, Key Points (bullets), Critical Terms, Implications
  summary     — 2 pages: Overview, topic paragraphs (LLM-named), Key Takeaways
  custom      — 1-2 pages via two-call pipeline; this module handles Call 2 (content fill)
                Call 1 (schema synthesis) is handled directly in the Lambda handler (handler.py)
"""
from __future__ import annotations

VALID_TEMPLATES = ("study-guide", "briefing", "summary", "custom")
MAX_SECTIONS = 8
VALID_BLOCK_TYPES = frozenset({
    "heading", "subheading", "paragraph", "bullet_list",
    "callout", "equation", "page_break",
})

# ─── System prompts ────────────────────────────────────────────────────────────

_COMMON_RULES = (
    "Return valid JSON only. No markdown fences, no preamble. "
    "Output must be json.loads() parseable.\n"
    "Rules:\n"
    "- Base all content strictly on provided course materials\n"
    "- Be concise and factual; no padding\n"
    "- Max 8 sections total\n"
    "- Keep page_count at the specified value\n"
)

_STUDY_GUIDE_SYSTEM = (
    "You are an academic study guide generator. " + _COMMON_RULES +
    "Output format:\n"
    '{"title":"...","subtitle":"...","page_count":2,"sections":[\n'
    '  {"type":"heading","content":"Overview"},\n'
    '  {"type":"paragraph","content":"2-3 sentence overview of the material"},\n'
    '  {"type":"heading","content":"Key Concepts"},\n'
    '  {"type":"subheading","content":"<Concept Name>"},\n'
    '  {"type":"paragraph","content":"<Definition and explanation>"},\n'
    '  {"type":"heading","content":"Core Topics"},\n'
    '  {"type":"subheading","content":"<Topic Name>"},\n'
    '  {"type":"bullet_list","items":["point 1","point 2","point 3"]},\n'
    '  {"type":"heading","content":"Examples"},\n'
    '  {"type":"bullet_list","items":["example 1","example 2","example 3"]},\n'
    '  {"type":"heading","content":"Summary"},\n'
    '  {"type":"callout","content":"3-5 key takeaways as a single paragraph"}\n'
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
    '{"title":"Summary — <source topic>","subtitle":"","page_count":2,"sections":[\n'
    '  {"type":"heading","content":"Overview"},\n'
    '  {"type":"paragraph","content":"2-sentence scope description"},\n'
    '  {"type":"heading","content":"<LLM-generated topic name 1>"},\n'
    '  {"type":"paragraph","content":"3-4 sentence summary of this topic"},\n'
    '  {"type":"heading","content":"<LLM-generated topic name 2>"},\n'
    '  {"type":"paragraph","content":"3-4 sentence summary"},\n'
    '  {"type":"heading","content":"Key Takeaways"},\n'
    '  {"type":"bullet_list","items":["takeaway 1","takeaway 2","takeaway 3","takeaway 4"]}\n'
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
    """Return (system_prompt, user_prompt) for the given template."""
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
        import json as _json
        schema_str = _json.dumps(synthesized_schema, ensure_ascii=False)
        user = f"Schema to fill:\n{schema_str}\n\n{context_block}"
        return _CUSTOM_FILL_SYSTEM, user

    raise ValueError(f"Unknown template_id: {template_id!r}")


# ─── Output normalizer ─────────────────────────────────────────────────────────

def normalize_report_sections(raw: dict) -> dict:
    """
    Normalise LLM output to a ReportsViewer-compatible payload.
    - Caps sections at MAX_SECTIONS
    - Fills missing types to bullet_list if items present, else paragraph
    - Drops completely empty content blocks
    """
    title = str(raw.get("title") or "Report").strip() or "Report"
    subtitle = str(raw.get("subtitle") or "").strip()
    page_count = int(raw.get("page_count") or 2)

    raw_sections = raw.get("sections") or []
    if not isinstance(raw_sections, list):
        raw_sections = []

    normalized = []
    for block in raw_sections:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type") or "").lower().strip()
        if btype not in VALID_BLOCK_TYPES:
            # infer type
            if isinstance(block.get("items"), list):
                btype = "bullet_list"
            else:
                btype = "paragraph"

        content = str(block.get("content") or block.get("text") or "").strip()
        items = block.get("items")
        if isinstance(items, list):
            items = [str(i) for i in items if str(i).strip()]
        else:
            items = None

        # Skip empty blocks
        if not content and not items:
            continue

        entry: dict = {"type": btype}
        if content:
            entry["content"] = content
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
```

- [x] **Step 8: Run contract tests**

```bash
python3 -m pytest tests/test_reports_validation.py -k "template or normalize or contract" -v
```
Expected: all PASSED.

### 2c: PDF Builder

- [x] **Step 9: Write PDF builder smoke test**

Add to `tests/test_reports_validation.py`:

```python
from api.services.reports_pdf_builder import build_reports_pdf_html


def test_pdf_html_contains_title():
    payload = {
        "title": "Robotics Study Guide",
        "subtitle": "Key concepts",
        "sections": [
            {"type": "heading", "content": "Overview"},
            {"type": "paragraph", "content": "This covers SLAM."},
            {"type": "bullet_list", "items": ["point A", "point B"]},
        ]
    }
    html = build_reports_pdf_html(report=payload)
    assert "Robotics Study Guide" in html
    assert "Overview" in html
    assert "point A" in html
```

- [x] **Step 10: Implement PDF builder**

Create `api/services/reports_pdf_builder.py`:

```python
"""Reports PDF/HTML builder — generates printable HTML from sections_json payload."""
from __future__ import annotations


def _e(v: str) -> str:
    return (
        (v or "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def _render_block(block: dict) -> str:
    btype = str(block.get("type") or "paragraph")
    content = _e(str(block.get("content") or ""))
    items = block.get("items") or []

    if btype in ("heading", "section"):
        return f"<h2>{content}</h2>"
    if btype in ("subheading", "subsection"):
        return f"<h3>{content}</h3>"
    if btype == "callout":
        return f'<div class="callout">{content}</div>'
    if btype in ("bullet_list", "list"):
        lis = "".join(f"<li>{_e(str(i))}</li>" for i in items)
        return f"<ul>{lis}</ul>"
    if btype == "page_break":
        return '<div class="page-break"></div>'
    # paragraph default
    return f"<p>{content}</p>"


def build_reports_pdf_html(*, report: dict) -> str:
    title = _e(str(report.get("title") or "Report"))
    subtitle = _e(str(report.get("subtitle") or ""))
    sections = report.get("sections") or []

    blocks_html = "\n".join(_render_block(b) for b in sections if isinstance(b, dict))

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 720px; margin: 40px auto; color: #1a1a1a; font-size: 14px; line-height: 1.7; }}
  h1 {{ font-size: 22px; text-align: center; margin-bottom: 4px; }}
  .subtitle {{ text-align: center; color: #666; font-size: 13px; margin-bottom: 32px; }}
  h2 {{ font-size: 16px; font-weight: bold; margin-top: 28px; padding-bottom: 4px; border-bottom: 1px solid #ddd; }}
  h3 {{ font-size: 14px; font-weight: 600; margin-top: 18px; }}
  p {{ margin: 10px 0; }}
  ul {{ padding-left: 20px; margin: 10px 0; }}
  li {{ margin: 4px 0; }}
  .callout {{ background: #eef2ff; border-left: 4px solid #6366f1; padding: 12px 16px; border-radius: 0 8px 8px 0; font-style: italic; margin: 16px 0; color: #3730a3; }}
  .page-break {{ page-break-after: always; border-top: 1px dashed #ccc; margin: 32px 0; }}
</style>
</head>
<body>
<h1>{title}</h1>
{f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
{blocks_html}
</body>
</html>"""


def build_reports_pdf_bytes(*, report: dict) -> bytes:
    """Return PDF bytes. Falls back to HTML bytes if weasyprint unavailable."""
    html = build_reports_pdf_html(report=report)
    try:
        from weasyprint import HTML as WeasyprintHTML
        return WeasyprintHTML(string=html).write_pdf()
    except ImportError:
        return html.encode("utf-8")
```

- [x] **Step 11: Run all service tests**

```bash
python3 -m pytest tests/test_reports_validation.py -v
```
Expected: all PASSED.

- [x] **Step 12: Commit**

```bash
git add api/services/reports_token_estimator.py api/services/reports_contracts.py api/services/reports_pdf_builder.py tests/test_reports_validation.py
git commit -m "feat(reports): add token estimator, template contracts, and PDF builder"
```

---

## Task 3: API Orchestrator (`api/reports.py`)

**Files:**
- Create: `api/reports.py`

### Background

Pattern is identical to `api/flashcards.py`. The handler is a `BaseHTTPRequestHandler` subclass with `do_GET`, `do_POST`, `do_DELETE`. Actions are dispatched by `action` parameter. No LLM calls — all generation is delegated to the Lambda worker via SQS.

- [x] **Step 1: Implement the full handler**

Create `api/reports.py`:

```python
# Vercel Python Serverless Function -- Reports Generation
# POST /api/reports  action=estimate            -> draft row + token estimates
# POST /api/reports  action=generate            -> transition draft->queued, SQS enqueue, 202
# POST /api/reports  action=save_artifact       -> save generation as materials artifact
# POST /api/reports  action=resolve_regeneration -> post-regen resolution
# GET  /api/reports  action=get_generation      -> full viewer payload (status=ready)
# GET  /api/reports  action=get_generation_status -> lightweight poll
# GET  /api/reports  action=list_generations    -> history for course
# GET  /api/reports  action=export_pdf          -> PDF download
# DELETE /api/reports ?generation_id=           -> delete generation + artifact material

import json
import os
import boto3
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

try:
    from .middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from .models import User
    from .courses import Course
    from .db import get_db
    from .services.reports_token_estimator import estimate_reports_token_ranges
    from .services.reports_contracts import (
        build_report_prompt, normalize_report_sections, VALID_TEMPLATES
    )
    from .services.reports_pdf_builder import build_reports_pdf_bytes
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from models import User
    from courses import Course
    from db import get_db
    from services.reports_token_estimator import estimate_reports_token_ranges
    from services.reports_contracts import (
        build_report_prompt, normalize_report_sections, VALID_TEMPLATES
    )
    from services.reports_pdf_builder import build_reports_pdf_bytes

_REPORTS_QUEUE_URL = os.environ.get('REPORTS_GENERATION_QUEUE_URL')
_AWS_REGION = (
    os.environ.get('AWS_REGION')
    or os.environ.get('AWS_DEFAULT_REGION')
    or 'us-east-1'
)

_MATERIAL_CHUNK_LIMIT = 80
_CONTEXT_CHAR_BUDGET = 24_000


def _fetch_material_context(conn, material_ids: list) -> str:
    if not material_ids:
        return 'No course materials selected.'
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.content
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.material_id = ANY(%s::int[])
        ORDER BY d.material_id, c.chunk_index
        LIMIT %s
        """,
        (material_ids, _MATERIAL_CHUNK_LIMIT),
    )
    rows = cursor.fetchall()
    cursor.close()
    if not rows:
        return 'No indexed content found for the selected materials.'
    parts, total = [], 0
    for row in rows:
        content = row.get('content') or ''
        if total + len(content) > _CONTEXT_CHAR_BUDGET:
            remaining = _CONTEXT_CHAR_BUDGET - total
            if remaining > 200:
                parts.append(content[:remaining])
            break
        parts.append(content)
        total += len(content)
    return '\n\n---\n\n'.join(parts)


def _build_estimate_prompt(template_id: str, material_context: str, custom_prompt: str | None) -> tuple[str, str]:
    """Build prompt for estimate (no synthesized schema yet for custom)."""
    if template_id == 'custom':
        # Use a placeholder schema for estimation only
        placeholder_system = (
            "You are a report generator. "
            f"User request: {custom_prompt or 'Custom report'}. "
            "Produce a structured JSON report."
        )
        return placeholder_system, f"Course materials:\n{material_context}"
    return build_report_prompt(
        template_id=template_id,
        material_context=material_context,
        custom_prompt=custom_prompt,
        synthesized_schema=None,
    )


def _enqueue_reports_generation_job(generation_id: int, user_id: int):
    if not _REPORTS_QUEUE_URL:
        raise ValueError('REPORTS_GENERATION_QUEUE_URL env var is not set')
    sqs = boto3.client('sqs', region_name=_AWS_REGION)
    sqs.send_message(
        QueueUrl=_REPORTS_QUEUE_URL,
        MessageBody=json.dumps({
            'generation_id': generation_id,
            'generated_by': user_id,
        }),
    )


def _persist_draft(conn, *, course_id, user_id, template_id, custom_prompt,
                   provider, model_id, material_ids, prompt_text,
                   generation_settings, est_pl, est_ph, est_tl, est_th,
                   parent_generation_id=None) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO report_generations
            (course_id, generated_by, template_id, custom_prompt,
             provider, model_id, status, parent_generation_id,
             selected_material_ids, prompt_text, generation_settings,
             estimated_prompt_tokens_low, estimated_prompt_tokens_high,
             estimated_total_tokens_low, estimated_total_tokens_high)
        VALUES
            (%s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            course_id, user_id, template_id, custom_prompt or None,
            provider, model_id, parent_generation_id,
            json.dumps(material_ids), prompt_text,
            json.dumps(generation_settings),
            est_pl, est_ph, est_tl, est_th,
        ),
    )
    generation_id = cursor.fetchone()['id']
    cursor.close()
    return generation_id


def _build_viewer_payload(gen: dict, version: dict | None) -> dict:
    sections = []
    if version:
        raw = version.get('sections_json') or []
        sections = raw if isinstance(raw, list) else []
    return {
        'generation_id': gen['id'],
        'parent_generation_id': gen.get('parent_generation_id'),
        'course_id': gen['course_id'],
        'template_id': gen.get('template_id'),
        'custom_prompt': gen.get('custom_prompt'),
        'title': (version or {}).get('title') or 'Report',
        'subtitle': (version or {}).get('subtitle') or '',
        'page_count': (version or {}).get('page_count') or 2,
        'sections': sections,
        'provider': gen.get('provider'),
        'model_id': gen.get('model_id'),
        'selected_material_ids': gen.get('selected_material_ids') or [],
        'generation_settings': gen.get('generation_settings') or {},
        'artifact_material_id': gen.get('artifact_material_id'),
        'status': gen.get('status'),
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ── GET ────────────────────────────────────────────────────────────────────

    def do_GET(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {'error': 'Unauthorized'})
            return
        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {'error': 'User not found'})
            return
        params = parse_qs(urlparse(self.path).query)
        action = (params.get('action') or [None])[0]

        if action == 'get_generation':
            self._get_generation(params, user)
        elif action == 'get_generation_status':
            self._get_generation_status(params, user)
        elif action == 'list_generations':
            self._list_generations(params, user)
        elif action == 'export_pdf':
            self._export_pdf(params, user)
        else:
            send_json(self, 400, {'error': f'Unknown action: {action}'})

    def _get_generation(self, params, user):
        gen_id_raw = (params.get('generation_id') or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user['id']),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return
            version = None
            if gen['status'] == 'ready':
                cursor.execute(
                    "SELECT * FROM report_versions WHERE generation_id=%s ORDER BY version_number DESC LIMIT 1",
                    (gen_id,),
                )
                version = cursor.fetchone()
            cursor.close()
        send_json(self, 200, _build_viewer_payload(gen, version))

    def _get_generation_status(self, params, user):
        gen_id_raw = (params.get('generation_id') or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, status, error FROM report_generations WHERE id=%s AND generated_by=%s",
                (int(gen_id_raw), user['id']),
            )
            row = cursor.fetchone()
            cursor.close()
        if not row:
            send_json(self, 404, {'error': 'Generation not found'})
            return
        send_json(self, 200, {'generation_id': row['id'], 'status': row['status'], 'error': row.get('error')})

    def _list_generations(self, params, user):
        course_id_raw = (params.get('course_id') or [None])[0]
        if not course_id_raw or not str(course_id_raw).isdigit():
            send_json(self, 400, {'error': 'course_id required'})
            return
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, template_id, custom_prompt, status, error,
                       provider, model_id, artifact_material_id,
                       parent_generation_id, created_at,
                       estimated_total_tokens_low, estimated_total_tokens_high,
                       generation_settings
                FROM report_generations
                WHERE course_id=%s AND generated_by=%s
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (int(course_id_raw), user['id']),
            )
            rows = cursor.fetchall()
            cursor.close()

        results = []
        for r in rows:
            results.append({
                'generation_id': r['id'],
                'template_id': r['template_id'],
                'custom_prompt': r.get('custom_prompt'),
                'status': r['status'],
                'error': r.get('error'),
                'provider': r.get('provider'),
                'model_id': r.get('model_id'),
                'artifact_material_id': r.get('artifact_material_id'),
                'parent_generation_id': r.get('parent_generation_id'),
                'created_at': r['created_at'].isoformat() if r.get('created_at') else None,
                'estimated_total_tokens_low': r.get('estimated_total_tokens_low'),
                'estimated_total_tokens_high': r.get('estimated_total_tokens_high'),
                'generation_settings': r.get('generation_settings') or {},
            })
        send_json(self, 200, {'generations': results})

    def _export_pdf(self, params, user):
        gen_id_raw = (params.get('generation_id') or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s AND status='ready'",
                (gen_id, user['id']),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Ready generation not found'})
                return
            cursor.execute(
                "SELECT * FROM report_versions WHERE generation_id=%s ORDER BY version_number DESC LIMIT 1",
                (gen_id,),
            )
            version = cursor.fetchone()
            cursor.close()

        if not version:
            send_json(self, 404, {'error': 'No version data found'})
            return

        payload = _build_viewer_payload(gen, version)
        pdf_bytes = build_reports_pdf_bytes(report=payload)
        title_slug = (payload.get('title') or 'report').replace(' ', '_')[:40]
        content_type = 'application/pdf' if pdf_bytes[:4] == b'%PDF' else 'text/html; charset=utf-8'
        cors = get_cors_headers()
        self.send_response(200)
        for k, v in cors.items():
            self.send_header(k, v)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Disposition', f'attachment; filename="{title_slug}.pdf"')
        self.send_header('Content-Length', str(len(pdf_bytes)))
        self.end_headers()
        self.wfile.write(pdf_bytes)

    # ── DELETE ─────────────────────────────────────────────────────────────────

    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {'error': 'Unauthorized'})
            return
        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {'error': 'User not found'})
            return
        params = parse_qs(urlparse(self.path).query)
        gen_id_raw = (params.get('generation_id') or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT artifact_material_id FROM report_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user['id']),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return
            if row.get('artifact_material_id'):
                cursor.execute('DELETE FROM materials WHERE id=%s', (row['artifact_material_id'],))
            cursor.execute(
                'DELETE FROM report_generations WHERE id=%s AND generated_by=%s RETURNING id',
                (gen_id, user['id']),
            )
            deleted = cursor.fetchone()
            cursor.close()
        if not deleted:
            send_json(self, 404, {'error': 'Generation not found'})
            return
        send_json(self, 200, {'deleted': gen_id})

    # ── POST ───────────────────────────────────────────────────────────────────

    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {'error': 'Unauthorized'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) if length else b'{}')
        except (json.JSONDecodeError, ValueError):
            send_json(self, 400, {'error': 'Invalid JSON body'})
            return
        action = body.get('action') or parse_qs(urlparse(self.path).query).get('action', [None])[0]
        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {'error': 'User not found'})
            return
        if action == 'estimate':
            self._estimate(body, user)
        elif action == 'generate':
            self._generate(body, user)
        elif action == 'save_artifact':
            self._save_artifact(body, user)
        elif action == 'resolve_regeneration':
            self._resolve_regeneration(body, user)
        else:
            send_json(self, 400, {'error': f'Unknown action: {action}'})

    def _estimate(self, body, user):
        course_id = body.get('course_id')
        if not course_id:
            send_json(self, 400, {'error': 'course_id required'})
            return
        template_id = str(body.get('template_id') or 'study-guide').strip()
        if template_id not in VALID_TEMPLATES:
            send_json(self, 400, {'error': f'template_id must be one of: {", ".join(VALID_TEMPLATES)}'})
            return
        custom_prompt = str(body.get('custom_prompt') or '').strip() or None
        if template_id == 'custom' and not custom_prompt:
            send_json(self, 400, {'error': 'custom_prompt required for custom template'})
            return
        provider = body.get('provider', 'openai')
        model_id = body.get('model_id', 'gpt-4o-mini')
        material_ids = [
            int(x) for x in (body.get('material_ids') or [])
            if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
        ]
        user_id = user['id']
        with get_db() as conn:
            if not Course.verify_access(int(course_id), user_id):
                send_json(self, 403, {'error': 'Access denied to this course'})
                return
            material_context = _fetch_material_context(conn, material_ids)
            system_prompt, user_prompt = _build_estimate_prompt(template_id, material_context, custom_prompt)
            estimate = estimate_reports_token_ranges(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                template_id=template_id,
            )
            generation_settings = {
                'template_id': template_id,
                'custom_prompt': custom_prompt,
                'provider': provider,
                'model_id': model_id,
            }
            generation_id = _persist_draft(
                conn,
                course_id=int(course_id),
                user_id=user_id,
                template_id=template_id,
                custom_prompt=custom_prompt,
                provider=provider,
                model_id=model_id,
                material_ids=material_ids,
                prompt_text=system_prompt + '\n\n' + user_prompt,
                generation_settings=generation_settings,
                est_pl=estimate['estimated_prompt_tokens_low'],
                est_ph=estimate['estimated_prompt_tokens_high'],
                est_tl=estimate['estimated_total_tokens_low'],
                est_th=estimate['estimated_total_tokens_high'],
                parent_generation_id=body.get('parent_generation_id'),
            )
        send_json(self, 200, {
            'generation_id': generation_id,
            'template_id': template_id,
            'provider': provider,
            'model_id': model_id,
            **estimate,
        })

    def _generate(self, body, user):
        gen_id_raw = body.get('generation_id')
        if gen_id_raw is None:
            send_json(self, 400, {'error': 'generation_id required'})
            return
        try:
            generation_id = int(gen_id_raw)
        except (TypeError, ValueError):
            send_json(self, 400, {'error': 'Invalid generation_id'})
            return

        # Optional model override
        provider_override = body.get('provider')
        model_id_override = body.get('model_id')

        user_id = user['id']
        should_enqueue = False
        status_response = None

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s FOR UPDATE",
                (generation_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                send_json(self, 404, {'error': 'Draft generation not found'})
                return

            current_status = row['status']
            if current_status in ('queued', 'generating'):
                cursor.close()
                send_json(self, 202, {
                    'generation_id': generation_id,
                    'status': current_status,
                    'message': f'Generation already {current_status}',
                })
                return
            if current_status not in ('draft', 'failed'):
                cursor.close()
                send_json(self, 409, {'error': f'Cannot generate from status: {current_status}'})
                return

            update_fields = ['status=%s']
            update_values = ['queued']
            if provider_override:
                update_fields.append('provider=%s')
                update_values.append(provider_override)
            if model_id_override:
                update_fields.append('model_id=%s')
                update_values.append(model_id_override)
            update_values.extend([generation_id, user_id])

            cursor.execute(
                f"UPDATE report_generations SET {', '.join(update_fields)} WHERE id=%s AND generated_by=%s",
                update_values,
            )
            cursor.close()
            should_enqueue = True
            status_response = {'generation_id': generation_id, 'status': 'queued'}

        if should_enqueue:
            try:
                _enqueue_reports_generation_job(generation_id, user_id)
            except Exception as exc:
                with get_db() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute(
                        "UPDATE report_generations SET status='failed', error=%s WHERE id=%s",
                        (f'Failed to enqueue generation job: {exc}'[:500], generation_id),
                    )
                    cur2.close()
                send_json(self, 500, {'error': 'Failed to queue generation', 'detail': str(exc)})
                return

        self.send_response(202)
        cors = get_cors_headers()
        for k, v in cors.items():
            self.send_header(k, v)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(status_response).encode())

    def _save_artifact(self, body, user):
        gen_id = body.get('generation_id')
        if not gen_id:
            send_json(self, 400, {'error': 'generation_id required'})
            return
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s AND status='ready'",
                (int(gen_id), user['id']),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Ready generation not found'})
                return
            cursor.execute(
                "SELECT title FROM report_versions WHERE generation_id=%s ORDER BY version_number DESC LIMIT 1",
                (int(gen_id),),
            )
            ver = cursor.fetchone()
            title = (ver or {}).get('title') or 'Report'

            file_url = f'report://generation/{int(gen_id)}'
            cursor.execute(
                """
                INSERT INTO materials (course_id, name, file_url, file_type, source_type, doc_type, uploaded_by)
                VALUES (%s, %s, %s, 'json', 'generated', 'report', %s)
                RETURNING id
                """,
                (gen['course_id'], title, file_url, user['id']),
            )
            material_id = cursor.fetchone()['id']
            cursor.execute(
                "UPDATE report_generations SET artifact_material_id=%s WHERE id=%s",
                (material_id, int(gen_id)),
            )
            # Link material to course junction table (mirrors flashcards pattern)
            cursor.execute(
                "INSERT INTO course_materials (course_id, material_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (gen['course_id'], material_id),
            )
            cursor.close()
        send_json(self, 200, {'artifact_material_id': material_id, 'generation_id': int(gen_id)})

    def _resolve_regeneration(self, body, user):
        """Handle save_both / replace / revert for post-regen resolution."""
        generation_id = body.get('generation_id')
        parent_id = body.get('parent_generation_id')
        resolution = body.get('resolution')  # 'save_both' | 'replace' | 'revert'

        if not generation_id or not resolution:
            send_json(self, 400, {'error': 'generation_id and resolution required'})
            return
        if resolution not in ('save_both', 'replace', 'revert'):
            send_json(self, 400, {'error': 'resolution must be save_both, replace, or revert'})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            if resolution == 'revert' and parent_id:
                cursor.execute(
                    "DELETE FROM report_generations WHERE id=%s AND generated_by=%s",
                    (int(generation_id), user['id']),
                )
            elif resolution == 'replace' and parent_id:
                cursor.execute(
                    """
                    UPDATE report_generations SET artifact_material_id=NULL
                    WHERE id=%s AND generated_by=%s
                    """,
                    (int(parent_id), user['id']),
                )
                cursor.execute(
                    "DELETE FROM materials WHERE id=(SELECT artifact_material_id FROM report_generations WHERE id=%s)",
                    (int(parent_id),),
                )
            # save_both: no-op — keep both rows as-is
            cursor.close()
        send_json(self, 200, {'resolution': resolution, 'generation_id': int(generation_id)})
```

- [x] **Step 2: Verify compile**

```bash
python3 -m py_compile api/reports.py
```
Expected: no output.

- [x] **Step 3: Commit**

```bash
git add api/reports.py
git commit -m "feat(reports): implement API orchestrator with all actions"
```

---

## Task 4: Lambda Worker (`lambda/reports_generate/`)

**Files:**
- Create: `lambda/reports_generate/db.py`
- Create: `lambda/reports_generate/handler.py`
- Create: `lambda/reports_generate/Dockerfile`
- Create: `lambda/reports_generate/requirements.txt`
- Create: `lambda/reports_generate/build.sh`
- Create: `lambda/reports_generate/iam/api-send-message-policy.json`
- Create: `lambda/reports_generate/iam/worker-consume-policy.json`

### 4a: DB helper

- [x] **Step 1: Create `lambda/reports_generate/db.py`**

Copy from `lambda/flashcards_generate/db.py` — it's identical (just connects to DATABASE_URL). No changes needed.

```python
"""PostgreSQL connection helper for Lambda worker."""
import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row


@contextmanager
def get_db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")
    with psycopg.connect(url, row_factory=dict_row) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

### 4b: Handler

The worker handles three execution paths in `_process_generation`:

1. **Built-in templates** (`study-guide`, `briefing`, `summary`): single LLM call using the contract from `reports_contracts.py` (copied into the Lambda, not imported from API).
2. **Custom template**: two-call pipeline — Call 1 synthesizes a schema from the custom_prompt + a short topic summary (first 2,000 chars of material context), Call 2 fills the schema using the full material context.

- [x] **Step 2: Create `lambda/reports_generate/handler.py`**

```python
"""
AWS Lambda handler -- reports_generate

Triggered by SQS messages from the API enqueue step.
Message body: {"generation_id": <int>, "generated_by": <int>}

Two-path LLM pipeline:
  Built-in templates (study-guide, briefing, summary):
    Single call with fixed schema contract.
  Custom template:
    Call 1 (schema synthesis): custom_prompt + short topic summary -> JSON schema skeleton
    Call 2 (content fill): synthesized schema + full material context -> filled JSON
"""
import json
import os
import re

import requests
from cryptography.fernet import Fernet, InvalidToken

from db import get_db

TIMEOUT_SECONDS = 90
MATERIAL_CHUNK_LIMIT = 80
CONTEXT_CHAR_BUDGET = 24_000
TOPIC_SUMMARY_BUDGET = 2_000   # for schema synthesis Call 1 only
MAX_SECTIONS = 8

VALID_BLOCK_TYPES = frozenset({
    "heading", "subheading", "paragraph", "bullet_list",
    "callout", "equation", "page_break",
})


# ─── Crypto ───────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    raw = os.environ.get("API_KEY_ENCRYPTION_KEY")
    if not raw:
        raise ValueError("API_KEY_ENCRYPTION_KEY not set")
    return Fernet(raw.encode())


def decrypt_api_key(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt API key")


# ─── Material context ─────────────────────────────────────────────────────────

def _fetch_material_context(conn, material_ids: list, char_budget: int = CONTEXT_CHAR_BUDGET) -> str:
    if not material_ids:
        return "No course materials selected."
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.content
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.material_id = ANY(%s::int[])
        ORDER BY d.material_id, c.chunk_index
        LIMIT %s
        """,
        (material_ids, MATERIAL_CHUNK_LIMIT),
    )
    rows = cursor.fetchall()
    cursor.close()
    if not rows:
        return "No indexed content found for the selected materials."
    parts, total = [], 0
    for row in rows:
        content = row.get("content") or ""
        if total + len(content) > char_budget:
            remaining = char_budget - total
            if remaining > 200:
                parts.append(content[:remaining])
            break
        parts.append(content)
        total += len(content)
    return "\n\n---\n\n".join(parts)


# ─── Prompt builders ──────────────────────────────────────────────────────────

_COMMON_RULES = (
    "Return valid JSON only. No markdown fences, no preamble. "
    "Output must be json.loads() parseable.\n"
    "Rules:\n"
    "- Base all content strictly on provided course materials\n"
    "- Be concise and factual; no padding\n"
    "- Max 8 sections total\n"
    "- Keep page_count at the specified value\n"
)

_STUDY_GUIDE_SYSTEM = (
    "You are an academic study guide generator. " + _COMMON_RULES +
    'Output format:\n'
    '{"title":"...","subtitle":"...","page_count":2,"sections":['
    '{"type":"heading","content":"Overview"},'
    '{"type":"paragraph","content":"2-3 sentence overview"},'
    '{"type":"heading","content":"Key Concepts"},'
    '{"type":"subheading","content":"<Concept Name>"},'
    '{"type":"paragraph","content":"<Definition>"},'
    '{"type":"heading","content":"Core Topics"},'
    '{"type":"subheading","content":"<Topic Name>"},'
    '{"type":"bullet_list","items":["point 1","point 2"]},'
    '{"type":"heading","content":"Examples"},'
    '{"type":"bullet_list","items":["example 1","example 2"]},'
    '{"type":"heading","content":"Summary"},'
    '{"type":"callout","content":"3-5 key takeaways"}]}'
)

_BRIEFING_SYSTEM = (
    "You are an executive briefing writer. " + _COMMON_RULES +
    'Output format:\n'
    '{"title":"...","subtitle":"Executive Summary","page_count":1,"sections":['
    '{"type":"heading","content":"Background"},'
    '{"type":"paragraph","content":"3-4 sentence situation overview"},'
    '{"type":"heading","content":"Key Points"},'
    '{"type":"bullet_list","items":["point — one sentence each"]},'
    '{"type":"heading","content":"Critical Terms"},'
    '{"type":"bullet_list","items":["Term — definition"]},'
    '{"type":"heading","content":"Implications"},'
    '{"type":"paragraph","content":"What this means"},'
    '{"type":"callout","content":"Bottom line in one sentence"}]}'
)

_SUMMARY_SYSTEM = (
    "You are a document summarizer. " + _COMMON_RULES +
    'Output format:\n'
    '{"title":"Summary — <topic>","subtitle":"","page_count":2,"sections":['
    '{"type":"heading","content":"Overview"},'
    '{"type":"paragraph","content":"2-sentence scope"},'
    '{"type":"heading","content":"<Topic 1>"},'
    '{"type":"paragraph","content":"3-4 sentence summary"},'
    '{"type":"heading","content":"<Topic 2>"},'
    '{"type":"paragraph","content":"3-4 sentence summary"},'
    '{"type":"heading","content":"Key Takeaways"},'
    '{"type":"bullet_list","items":["takeaway 1","takeaway 2","takeaway 3"]}]}'
)

# Custom template — Call 1: schema synthesis
_SCHEMA_SYNTHESIS_SYSTEM = (
    "You are a document schema designer. "
    "Given the user's report request and a short sample of available material topics, "
    "output a JSON schema skeleton only. Do not fill in actual content. "
    "Return valid JSON only. No markdown fences. "
    'Format: {"title":"...","subtitle":"...","page_count":1,"sections":['
    '{"type":"heading|subheading|paragraph|bullet_list|callout","name":"Section Name","instructions":"what to generate here"}]}\n'
    "Rules:\n"
    "- Max 6 sections. Max page_count 2.\n"
    "- Each section has 'type', 'name', and 'instructions' only — no actual content."
)

# Custom template — Call 2: content fill
_CONTENT_FILL_SYSTEM = (
    "You are a document content generator. "
    "Return valid JSON only. No markdown fences. "
    "You are given a schema with 'instructions' fields. "
    "Replace every 'instructions' value with actual content generated from the course materials. "
    "Preserve all other fields (type, name, page_count, title, subtitle) exactly. "
    "For type=bullet_list, output 'items': [...] instead of 'content'. "
    "Output the completed schema JSON."
)


def _build_prompt(template_id: str, material_context: str, custom_prompt: str | None,
                  synthesized_schema: dict | None) -> tuple[str, str]:
    context_block = f"Course materials:\n{material_context}"
    if template_id == "study-guide":
        return _STUDY_GUIDE_SYSTEM, context_block
    if template_id == "briefing":
        return _BRIEFING_SYSTEM, context_block
    if template_id == "summary":
        return _SUMMARY_SYSTEM, context_block
    if template_id == "custom":
        if not synthesized_schema:
            raise ValueError("custom template requires synthesized_schema")
        schema_str = json.dumps(synthesized_schema, ensure_ascii=False)
        return _CONTENT_FILL_SYSTEM, f"Schema to fill:\n{schema_str}\n\n{context_block}"
    raise ValueError(f"Unknown template_id: {template_id!r}")


def _build_synthesis_prompt(custom_prompt: str, topic_summary: str) -> tuple[str, str]:
    user = f"Report request: {custom_prompt}\n\nAvailable material topics (sample):\n{topic_summary}"
    return _SCHEMA_SYNTHESIS_SYSTEM, user


# ─── JSON parsing ─────────────────────────────────────────────────────────────

def _parse_model_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Model returned empty content")
    try:
        return json.loads(raw)
    except Exception:
        pass
    if raw.startswith("```"):
        stripped = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(stripped)
        except Exception:
            raw = stripped
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0).strip())
        except Exception:
            pass
    raise ValueError("Could not parse model JSON output")


# ─── LLM calls ────────────────────────────────────────────────────────────────

def _call_openai_json(api_key, model_id, system, user) -> dict:
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model_id, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]},
        timeout=TIMEOUT_SECONDS,
    )
    if not resp.ok:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message") or resp.text[:500]
        except Exception:
            detail = resp.text[:500]
        raise requests.HTTPError(f"OpenAI failed ({resp.status_code}): {detail}", response=resp)
    raw = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
    return _parse_model_json(raw)


def _call_claude_json(api_key, model_id, system, user) -> dict:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model_id, "max_tokens": 4096, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    blocks = resp.json().get("content") or []
    raw = "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()
    return _parse_model_json(raw)


def _call_gemini_json(api_key, model_id, system, user) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    resp = requests.post(
        url,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={"system_instruction": {"parts": [{"text": system}]},
              "contents": [{"parts": [{"text": user}]}]},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates") or []
    parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
    raw = "\n".join(str(p.get("text", "")) for p in parts if isinstance(p, dict) and p.get("text")).strip()
    return _parse_model_json(raw)


def _call_llm_json(provider, api_key, model_id, system, user) -> dict:
    if provider == "openai":
        return _call_openai_json(api_key, model_id, system, user)
    if provider == "claude":
        return _call_claude_json(api_key, model_id, system, user)
    if provider == "gemini":
        return _call_gemini_json(api_key, model_id, system, user)
    raise ValueError(f"Unsupported provider: {provider}")


# ─── Output normalizer ────────────────────────────────────────────────────────

def _normalize_output(raw: dict) -> dict:
    title = str(raw.get("title") or "Report").strip() or "Report"
    subtitle = str(raw.get("subtitle") or "").strip()
    page_count = int(raw.get("page_count") or 2)

    raw_sections = raw.get("sections") or []
    if not isinstance(raw_sections, list):
        raw_sections = []

    normalized = []
    for block in raw_sections:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type") or "").lower().strip()
        if btype not in VALID_BLOCK_TYPES:
            btype = "bullet_list" if isinstance(block.get("items"), list) else "paragraph"

        content = str(block.get("content") or block.get("instructions") or "").strip()
        items = block.get("items")
        items = [str(i) for i in items if str(i).strip()] if isinstance(items, list) else None

        if not content and not items:
            continue

        entry: dict = {"type": btype}
        if content:
            entry["content"] = content
        if items:
            entry["items"] = items

        normalized.append(entry)
        if len(normalized) >= MAX_SECTIONS:
            break

    return {"title": title, "subtitle": subtitle, "page_count": page_count, "sections": normalized}


# ─── Persistence ──────────────────────────────────────────────────────────────

def _persist_version(conn, generation_id: int, normalized: dict):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM report_versions WHERE generation_id=%s",
        (generation_id,),
    )
    version_number = cursor.fetchone()["next_version"]
    cursor.execute(
        """
        INSERT INTO report_versions
            (generation_id, version_number, title, subtitle, page_count, sections_json)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            generation_id,
            version_number,
            normalized["title"],
            normalized["subtitle"],
            normalized["page_count"],
            json.dumps(normalized["sections"]),
        ),
    )
    cursor.close()


def _mark_failed(generation_id: int, error: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE report_generations SET status='failed', error=%s WHERE id=%s",
            ((error or "")[:500], generation_id),
        )
        cursor.close()


# ─── Core processing ──────────────────────────────────────────────────────────

def _process_generation(generation_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM report_generations WHERE id=%s FOR UPDATE",
            (generation_id,),
        )
        gen = cursor.fetchone()
        if not gen or gen["status"] != "queued":
            cursor.close()
            return  # idempotent skip

        cursor.execute(
            "UPDATE report_generations SET status='generating', error=NULL WHERE id=%s",
            (generation_id,),
        )

        provider  = gen.get("provider") or "openai"
        model_id  = gen.get("model_id") or "gpt-4o-mini"
        user_id   = gen["generated_by"]
        template_id   = str(gen.get("template_id") or "study-guide")
        custom_prompt = str(gen.get("custom_prompt") or "").strip() or None
        material_ids  = gen.get("selected_material_ids") or []
        if isinstance(material_ids, str):
            try:
                material_ids = json.loads(material_ids)
            except Exception:
                material_ids = []

        cursor.execute(
            "SELECT encrypted_key FROM user_api_keys WHERE user_id=%s AND provider=%s",
            (user_id, provider),
        )
        key_row = cursor.fetchone()
        if not key_row:
            cursor.close()
            raise ValueError(f"No {provider} API key configured for user {user_id}")
        api_key = decrypt_api_key(key_row["encrypted_key"])

        full_context = _fetch_material_context(conn, material_ids)
        cursor.close()

    # ── Two-call pipeline for custom; single call for built-ins ──────────────

    synthesized_schema = None
    if template_id == "custom" and custom_prompt:
        topic_summary = full_context[:TOPIC_SUMMARY_BUDGET]
        synth_system, synth_user = _build_synthesis_prompt(custom_prompt, topic_summary)
        synthesized_schema = _call_llm_json(provider, api_key, model_id, synth_system, synth_user)

    system, user_prompt = _build_prompt(template_id, full_context, custom_prompt, synthesized_schema)
    raw = _call_llm_json(provider, api_key, model_id, system, user_prompt)
    normalized = _normalize_output(raw)

    with get_db() as conn:
        _persist_version(conn, generation_id, normalized)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE report_generations SET status='ready', error=NULL WHERE id=%s",
            (generation_id,),
        )
        cursor.close()


# ─── Lambda entry point ───────────────────────────────────────────────────────

def lambda_handler(event, context):
    records = event.get("Records") or []
    for record in records:
        try:
            body = json.loads(record.get("body") or "{}")
            generation_id = int(body["generation_id"])
        except Exception:
            continue
        try:
            _process_generation(generation_id)
        except Exception as exc:
            _mark_failed(generation_id, str(exc))
            raise
    return {"statusCode": 200, "body": json.dumps({"ok": True})}
```

- [x] **Step 3: Compile check**

```bash
python3 -m py_compile lambda/reports_generate/handler.py lambda/reports_generate/db.py
```
Expected: no output.

### 4c: Docker + build files

- [x] **Step 4: Create `lambda/reports_generate/Dockerfile`**

```dockerfile
FROM python:3.12-slim

COPY requirements.txt .
RUN pip install --no-cache-dir awslambdaric -r requirements.txt

WORKDIR /var/task
COPY handler.py db.py ./

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
```

- [x] **Step 5: Create `lambda/reports_generate/requirements.txt`**

```
requests>=2.32.0
psycopg[binary]==3.3.3
cryptography>=41.0.0
awslambdaric>=2.0.0
```

- [x] **Step 6: Create `lambda/reports_generate/build.sh`**

```bash
#!/bin/bash
set -e
export AWS_PAGER=""

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
REPO_NAME="coursemate-reports-generate"
FUNCTION_NAME="reports_generate"
IMAGE_TAG="latest"
FULL_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

cd "$(dirname "$0")"

echo "=== Building Lambda container image ==="

if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  echo "1. Ensuring ECR repository exists..."
  aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" 2>/dev/null \
    || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" \
         --image-scanning-configuration scanOnPush=true
  echo "   Done."

  echo "2. Logging in to ECR..."
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

  echo "3. Building Docker image for linux/amd64..."
  docker buildx build --platform linux/amd64 \
    -t "${REPO_NAME}:${IMAGE_TAG}" \
    -t "${FULL_URI}" \
    --load .

  echo "   Pushing image to ECR..."
  docker push "${FULL_URI}"
else
  echo "1-3. Skipping ECR setup and build (SKIP_BUILD=1)"
fi

echo "4. Deploying Lambda function '${FUNCTION_NAME}'..."
if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
  echo "   Updating existing function code..."
  aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --image-uri "${FULL_URI}" \
    --region "${AWS_REGION}"
else
  echo "   Creating new Lambda function..."
  aws lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --package-type Image \
    --code ImageUri="${FULL_URI}" \
    --role "arn:aws:iam::${AWS_ACCOUNT_ID}:role/CoursemateLambda" \
    --architectures x86_64 \
    --timeout 600 \
    --memory-size 1024 \
    --environment "Variables={DATABASE_URL=<YOUR_DATABASE_URL>,API_KEY_ENCRYPTION_KEY=<YOUR_KEY>}" \
    --region "${AWS_REGION}"
fi
echo "   Done."

echo ""
echo "=== Deployment complete ==="
echo "Image URI: ${FULL_URI}"
echo ""
echo "Next steps:"
echo "1. Set API env var:"
echo "   REPORTS_GENERATION_QUEUE_URL=https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/reports-generate"
echo ""
echo "2. Create event source mapping (if not exists):"
echo "   aws lambda create-event-source-mapping \\"
echo "     --function-name ${FUNCTION_NAME} \\"
echo "     --event-source-arn arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:reports-generate \\"
echo "     --batch-size 1 \\"
echo "     --enabled \\"
echo "     --region ${AWS_REGION}"
```

### 4d: IAM templates

- [x] **Step 7: Create `lambda/reports_generate/iam/api-send-message-policy.json`**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "arn:aws:sqs:<region>:<account>:reports-generate"
    }
  ]
}
```

- [x] **Step 8: Create `lambda/reports_generate/iam/worker-consume-policy.json`**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:<region>:<account>:reports-generate"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

- [x] **Step 9: Validate files**

```bash
python3 -m py_compile lambda/reports_generate/handler.py lambda/reports_generate/db.py
bash -n lambda/reports_generate/build.sh
python3 -m json.tool lambda/reports_generate/iam/api-send-message-policy.json > /dev/null
python3 -m json.tool lambda/reports_generate/iam/worker-consume-policy.json > /dev/null
```
Expected: no errors.

- [x] **Step 10: Commit**

```bash
git add lambda/reports_generate/
git commit -m "feat(lambda): add reports_generate worker with dual-path LLM pipeline"
```

---

## Task 5: Infrastructure Script

**Files:**
- Create: `scripts/infra/setup_reports_generation_infra.sh`

- [x] **Step 1: Create infra setup script**

```bash
#!/bin/bash
# setup_reports_generation_infra.sh
# Sets up event source mapping from SQS reports-generate -> Lambda reports_generate.
# The primary queue reports-generate already exists; this script only adds the mapping.
# Run AFTER deploying lambda/reports_generate via build.sh.
set -e
export AWS_PAGER=""

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-717279724624}"
QUEUE_NAME="reports-generate"
FUNCTION_NAME="reports_generate"
QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:${QUEUE_NAME}"

echo "=== Reports Generation Infra Setup ==="
echo "Queue ARN: ${QUEUE_ARN}"
echo "Function:  ${FUNCTION_NAME}"
echo ""

# Check if mapping already exists
EXISTING=$(aws lambda list-event-source-mappings \
  --function-name "${FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --query "EventSourceMappings[?EventSourceArn=='${QUEUE_ARN}'].UUID" \
  --output text 2>/dev/null || echo "")

if [[ -n "${EXISTING}" ]]; then
  echo "Event source mapping already exists (UUID: ${EXISTING}). Skipping."
else
  echo "Creating event source mapping..."
  aws lambda create-event-source-mapping \
    --function-name "${FUNCTION_NAME}" \
    --event-source-arn "${QUEUE_ARN}" \
    --batch-size 1 \
    --enabled \
    --region "${AWS_REGION}"
  echo "Done."
fi

echo ""
echo "Remember to set on your API runtime:"
echo "  REPORTS_GENERATION_QUEUE_URL=https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/${QUEUE_NAME}"
echo "  AWS_REGION=${AWS_REGION}"
```

- [x] **Step 2: Validate**

```bash
bash -n scripts/infra/setup_reports_generation_infra.sh
```
Expected: no output (syntax valid).

- [x] **Step 3: Commit**

```bash
git add scripts/infra/setup_reports_generation_infra.sh lambda/reports_generate/
git commit -m "feat(infra): add reports generation infra script and Lambda build artifacts"
```

---

## Task 6: Frontend — `Reports.jsx`

**Files:**
- Modify: `src/Reports.jsx`

### Background

Currently `Reports.jsx` calls `/api/generate` (a dead endpoint) synchronously and shows a spinner. Replace with:
1. `handleEstimate()` → POST `/api/reports` action=estimate → opens `GenerationConfirmModal`
2. `handleGenerate(modalParams)` → POST `/api/reports` action=generate → gets 202, starts polling
3. Poll `GET /api/reports?action=get_generation_status&generation_id=` while status in `['queued','generating']`
4. On `ready`, fetch `GET /api/reports?action=get_generation&generation_id=` and set `reportData`
5. On `list_generations` load, auto-resume polling for in-flight rows

Also fix: `/api/materials` → `/api/material` (the correct endpoint).

- [x] **Step 1: Add state variables and constants**

First, update the React import at the top of `Reports.jsx` to include `useRef`:

```jsx
// BEFORE (find the existing React import and add useRef):
import { useState, useEffect } from 'react';
// AFTER:
import { useState, useEffect, useRef } from 'react';
```

Then add the provider/model constants as module-level definitions (outside the component, mirroring `Quiz.jsx`):

```jsx
const PROVIDER_MODELS = {
  claude: [
    { label: 'Claude Opus 4.6',   id: 'claude-opus-4-6' },
    { label: 'Claude Sonnet 4.6', id: 'claude-sonnet-4-6' },
    { label: 'Claude Haiku 4.5',  id: 'claude-haiku-4-5-20251001' },
    { label: 'Claude Sonnet 4.5', id: 'claude-sonnet-4-5-20250929' },
    { label: 'Claude Sonnet 4',   id: 'claude-sonnet-4-20250514' },
    { label: 'Claude Opus 4',     id: 'claude-opus-4-20250514' },
  ],
  gemini: [
    { label: 'Gemini 3.1 Pro',        id: 'gemini-3.1-pro-preview' },
    { label: 'Gemini 3 Flash',        id: 'gemini-3-flash-preview' },
    { label: 'Gemini 2.5 Pro',        id: 'gemini-2.5-pro' },
    { label: 'Gemini 2.5 Flash',      id: 'gemini-2.5-flash' },
    { label: 'Gemini 2.5 Flash-Lite', id: 'gemini-2.5-flash-lite' },
    { label: 'Deep Research',         id: 'deep-research-pro-preview-12-2025' },
    { label: 'Gemini 2.0 Flash',      id: 'gemini-2.0-flash' },
    { label: 'Gemini 2.0 Flash-Lite', id: 'gemini-2.0-flash-lite' },
  ],
  openai: [
    { label: 'GPT-5.2',               id: 'gpt-5.2' },
    { label: 'GPT-5.1',               id: 'gpt-5.1' },
    { label: 'GPT-5 Mini',            id: 'gpt-5-mini' },
    { label: 'GPT-5 Nano',            id: 'gpt-5-nano' },
    { label: 'GPT-4.1',               id: 'gpt-4.1' },
    { label: 'GPT-4.1 mini',          id: 'gpt-4.1-mini' },
    { label: 'GPT-4.1 nano',          id: 'gpt-4.1-nano' },
    { label: 'GPT-4o',                id: 'gpt-4o' },
    { label: 'GPT-4o mini',           id: 'gpt-4o-mini' },
    { label: 'o3',                    id: 'o3' },
    { label: 'o3-mini',               id: 'o3-mini' },
    { label: 'o3-pro',                id: 'o3-pro' },
    { label: 'o4-mini',               id: 'o4-mini' },
    { label: 'o1',                    id: 'o1' },
    { label: 'o1-pro',                id: 'o1-pro' },
    { label: 'o3 Deep Research',      id: 'o3-deep-research' },
    { label: 'o4-mini Deep Research', id: 'o4-mini-deep-research' },
    { label: 'GPT-OSS 120B',          id: 'gpt-oss-120b' },
  ],
};

const MODEL_LABELS = { gemini: 'Gemini', openai: 'GPT', claude: 'Claude' };
```

Replace the existing state declarations and add at the top of the `Reports` component:

```jsx
// Generation lifecycle state
const [generationId, setGenerationId] = useState(null);
const [generationStatus, setGenerationStatus] = useState(null); // draft|queued|generating|ready|failed
const [generationError, setGenerationError] = useState('');
const [showConfirmModal, setShowConfirmModal] = useState(false);
const [estimateData, setEstimateData] = useState(null);
const [isEstimating, setIsEstimating] = useState(false);
const [isQueueing, setIsQueueing] = useState(false);
const pollingRef = useRef(null); // useRef avoids re-renders on interval assignment
const [history, setHistory] = useState([]);
const [historyLoading, setHistoryLoading] = useState(false);
const [availableProviders, setAvailableProviders] = useState([]);
```

- [x] **Step 2: Implement `loadHistory`, `startPolling`, `stopPolling`, `handleEstimate`, `handleConfirmGenerate`**

Replace `handleGenerate` with these functions:

```jsx
const authHeaders = { Authorization: `Bearer ${sessionToken}` };

async function loadHistory() {
  if (!course?.id) return;
  setHistoryLoading(true);
  try {
    const res = await fetch(`/api/reports?action=list_generations&course_id=${course.id}`, {
      headers: authHeaders,
    });
    const data = await res.json();
    const gens = data.generations || [];
    setHistory(gens);
    // Resume polling for any in-flight row
    const inflight = gens.find(g => g.status === 'queued' || g.status === 'generating');
    if (inflight) {
      setGenerationId(inflight.generation_id);
      setGenerationStatus(inflight.status);
      startPolling(inflight.generation_id);
    }
  } catch {
    // non-fatal
  } finally {
    setHistoryLoading(false);
  }
}

// Load available providers for the modal (same pattern as Quiz.jsx)
async function loadAvailableProviders() {
  try {
    const res = await fetch('/api/user?resource=api_keys', { headers: authHeaders });
    const data = await res.json();
    const providers = Object.entries(data || {}).filter(([, has]) => has).map(([p]) => p);
    setAvailableProviders(providers);
  } catch {
    // non-fatal
  }
}

function stopPolling() {
  if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
}

function startPolling(genId) {
  stopPolling();
  const interval = setInterval(async () => {
    try {
      const res = await fetch(
        `/api/reports?action=get_generation_status&generation_id=${genId}`,
        { headers: authHeaders },
      );
      const data = await res.json();
      setGenerationStatus(data.status);
      if (data.status === 'ready') {
        clearInterval(interval);
        pollingRef.current = null;
        const viewRes = await fetch(
          `/api/reports?action=get_generation&generation_id=${genId}`,
          { headers: authHeaders },
        );
        const viewData = await viewRes.json();
        setReportData(viewData);
        setGenerationStatus(null);
        setGenerationId(null);
      } else if (data.status === 'failed') {
        clearInterval(interval);
        pollingRef.current = null;
        setGenerationError(data.error || 'Generation failed.');
        setGenerationStatus(null);
      }
    } catch {
      // keep polling on transient errors
    }
  }, 3000);
  pollingRef.current = interval;
}

async function handleEstimate() {
  if (isEstimating) return;
  setGenerationError('');
  setIsEstimating(true);
  try {
    const materialIds = selectAll ? materials.map(m => m.id) : Array.from(selectedSources);
    const res = await fetch('/api/reports', {
      method: 'POST',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'estimate',
        course_id: course?.id,
        template_id: template,
        custom_prompt: isCustom ? customPrompt : undefined,
        material_ids: materialIds,
        provider: selectedProvider,
        model_id: selectedModelId,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    setEstimateData(data);
    setShowConfirmModal(true);
  } catch (e) {
    setGenerationError(e.message);
  } finally {
    setIsEstimating(false);
  }
}

async function handleConfirmGenerate({ provider, model_id } = {}) {
  if (!estimateData?.generation_id || isQueueing) return;
  setIsQueueing(true);
  try {
    const res = await fetch('/api/reports', {
      method: 'POST',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({
        action: 'generate',
        generation_id: estimateData.generation_id,
        provider: provider || selectedProvider,
        model_id: model_id || selectedModelId,
      }),
    });
    const data = await res.json();
    if (res.status !== 202 && !res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    setGenerationId(estimateData.generation_id);
    setGenerationStatus('queued');
    setShowConfirmModal(false);
    startPolling(estimateData.generation_id);
  } catch (e) {
    setGenerationError(e.message);
  } finally {
    setIsQueueing(false);
  }
}
```

- [x] **Step 3: Fix materials fetch URL**

Find the `fetch` call for materials and change `/api/materials` to `/api/material`:

```jsx
// BEFORE
fetch(`/api/materials?course_id=${course.id}`, {
// AFTER
fetch(`/api/material?course_id=${course.id}`, {
```

- [x] **Step 4: Replace Generate button's `onClick`**

```jsx
// BEFORE
onClick={handleGenerate}
// AFTER
onClick={() => handleEstimate()}
```

- [x] **Step 5: Add in-progress status UI in the form**

After the `generateError` display, add:

```jsx
{(generationStatus === 'queued' || generationStatus === 'generating') && (
  <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100">
    <svg className="animate-spin h-4 w-4 text-indigo-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
    <span className="text-xs text-indigo-700">
      {generationStatus === 'queued' ? 'Queued — waiting for worker…' : 'Generating report…'}
    </span>
  </div>
)}
```

- [x] **Step 6: Extend `GenerationConfirmModal` for reports mode**

`GenerationConfirmModal` only handles `mode === 'flashcards'` and falls through to a quiz summary otherwise. Add a reports branch so it shows the template name instead of quiz question counts.

In `src/components/GenerationConfirmModal.jsx`, make two changes:

**Change 1 — modal title** (find the `h3` or title element around line 81):
```jsx
// BEFORE:
{isFlashcards ? 'Confirm Flashcards Generation' : 'Confirm Quiz Generation'}
// AFTER:
{isFlashcards ? 'Confirm Flashcards Generation' : isReports ? 'Confirm Report Generation' : 'Confirm Quiz Generation'}
```
Note: `isReports` is declared just below (Change 2); hoist it above the title if needed or define it before the JSX return.

**Change 2 — summary text** (find the `summaryText` definition):
```jsx
// BEFORE:
const isFlashcards = mode === 'flashcards';

const summaryText = isFlashcards
  ? ( ... flashcards JSX ... )
  : ( ... quiz JSX ... );

// AFTER:
const isFlashcards = mode === 'flashcards';
const isReports = mode === 'reports';

const summaryText = isFlashcards
  ? (
    <>
      You are generating: <span className="font-medium text-gray-900">{data.card_count || 0}</span> flashcards
      {' '}at <span className="font-medium text-gray-900">{data.depth || 'moderate'}</span> depth
    </>
  )
  : isReports
  ? (
    <>
      You are generating a <span className="font-medium text-gray-900">{data.template_id || 'study-guide'}</span> report
    </>
  )
  : (
    <>
      You are generating: <span className="font-medium text-gray-900">{data.tf_count || 0}</span> T/F,{' '}
      <span className="font-medium text-gray-900">{data.sa_count || 0}</span> short answers,{' '}
      <span className="font-medium text-gray-900">{data.la_count || 0}</span> long answers,{' '}
      <span className="font-medium text-gray-900">{data.mcq_count || 0}</span> MCQ
    </>
  );
```

- [x] **Step 7: Add `GenerationConfirmModal`**

Import and render the modal (same pattern as Quiz.jsx):

```jsx
import GenerationConfirmModal from './components/GenerationConfirmModal';

// In the return, just before the closing </div>:
{showConfirmModal && estimateData && (
  <GenerationConfirmModal
    mode="reports"
    data={estimateData}
    onConfirm={handleConfirmGenerate}
    onCancel={() => { setShowConfirmModal(false); setEstimateData(null); }}
    isLoading={isQueueing}
    availableProviders={availableProviders}
    providerModels={PROVIDER_MODELS}
    modelLabels={MODEL_LABELS}
  />
)}
```

- [x] **Step 8: Pass `sourceMaterials` to ReportsViewer**

When `reportData` is ready and `ReportsViewer` renders, pass the resolved material objects so the sources panel has content:

```jsx
// Existing ReportsViewer render (find it in Reports.jsx):
<ReportsViewer
  report={reportData}
  sessionToken={sessionToken}
  sourceMaterials={materials}   // <-- add this prop (materials = the fetched list)
  onRegenerate={handleRegenerate}
  onClose={() => setReportData(null)}
/>
```

`materials` is already in scope from the materials fetch; pass it directly.

- [x] **Step 9: Load history and providers on mount and cleanup polling**

```jsx
useEffect(() => { loadHistory(); loadAvailableProviders(); }, [course?.id, sessionToken]); // eslint-disable-line

useEffect(() => {
  return () => stopPolling();
}, []); // eslint-disable-line
```

- [x] **Step 10: Commit**

```bash
git add src/Reports.jsx src/components/GenerationConfirmModal.jsx
git commit -m "feat(frontend): migrate Reports.jsx to async estimate -> confirm -> poll flow"
```

---

## Task 7: Frontend — `ReportsViewer.jsx` Action Wiring

**Files:**
- Modify: `src/ReportsViewer.jsx`

Currently Save Report and Export as PDF buttons are unstyled stubs. Wire them up. The component receives `generation_id` via `report.generation_id`.

- [x] **Step 1: Add save/export state**

```jsx
const [saveStatus, setSaveStatus] = useState(null); // null | 'saving' | 'saved' | 'error'
const [saveError, setSaveError] = useState('');
const [exporting, setExporting] = useState(false);
```

- [x] **Step 2: Implement `handleSave`**

```jsx
async function handleSave() {
  if (!report?.generation_id || saveStatus === 'saving' || saveStatus === 'saved') return;
  setSaveStatus('saving');
  setSaveError('');
  try {
    const res = await fetch('/api/reports', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action: 'save_artifact', generation_id: report.generation_id }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.error || `HTTP ${res.status}`);
    }
    setSaveStatus('saved');
  } catch (e) {
    setSaveError(e.message);
    setSaveStatus('error');
  }
}
```

- [x] **Step 3: Implement `handleExport`**

```jsx
async function handleExport() {
  if (!report?.generation_id || exporting) return;
  setExporting(true);
  try {
    const url = `/api/reports?action=export_pdf&generation_id=${report.generation_id}`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${sessionToken}` } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${title.replace(/\s+/g, '_')}.pdf`;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch {
    // non-critical
  } finally {
    setExporting(false);
  }
}
```

- [x] **Step 4: Update button JSX with active styling**

```jsx
// Save Report button — match Quiz saved-state visual (green = saved, red = error, gray = idle)
<button
  type="button"
  onClick={handleSave}
  disabled={saveStatus === 'saving' || saveStatus === 'saved'}
  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
    saveStatus === 'saved'
      ? 'border-green-300 bg-green-50 text-green-700 cursor-default'
      : saveStatus === 'error'
      ? 'border-red-300 text-red-600 hover:bg-red-50'
      : 'border-gray-200 text-gray-600 hover:bg-gray-50'
  }`}
>
  <BookmarkIcon />
  {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved' : saveStatus === 'error' ? 'Retry Save' : 'Save Report'}
</button>

// Export as PDF button
<button
  type="button"
  onClick={handleExport}
  disabled={exporting}
  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
>
  <DownloadIcon />
  {exporting ? 'Exporting…' : 'Export as PDF'}
</button>
```

- [x] **Step 5: Wire Regenerate**

```jsx
// The onRegenerate prop is called by the parent (Reports.jsx).
// Reports.jsx already resets reportData on regenerate. No change needed here —
// just confirm the Regenerate button calls onRegenerate and passes the current generation_id:
<button
  type="button"
  onClick={() => onRegenerate && onRegenerate({ parent_generation_id: report?.generation_id })}
  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
>
  <RefreshIcon />
  Regenerate
</button>
```

- [x] **Step 6: Commit**

```bash
git add src/ReportsViewer.jsx
git commit -m "feat(frontend): wire ReportsViewer save, export, and regenerate actions"
```

---

## Task 8: Tests and Final Verification

**Files:**
- Modify: `tests/test_reports_validation.py`

- [x] **Step 1: Add worker normalization tests**

```python
# In tests/test_reports_validation.py — add at end

def test_normalize_preserves_callout():
    raw = {"title": "T", "sections": [
        {"type": "callout", "content": "Important note"},
    ]}
    result = normalize_report_sections(raw)
    assert result["sections"][0]["type"] == "callout"
    assert result["sections"][0]["content"] == "Important note"


def test_normalize_bullet_list_with_items():
    raw = {"title": "T", "sections": [
        {"type": "bullet_list", "items": ["a", "b", "c"]},
    ]}
    result = normalize_report_sections(raw)
    s = result["sections"][0]
    assert s["type"] == "bullet_list"
    assert s["items"] == ["a", "b", "c"]


def test_normalize_drops_empty_blocks():
    raw = {"title": "T", "sections": [
        {"type": "paragraph", "content": ""},   # should be dropped
        {"type": "heading", "content": "Title"},
    ]}
    result = normalize_report_sections(raw)
    assert len(result["sections"]) == 1
    assert result["sections"][0]["content"] == "Title"


def test_contracts_custom_requires_schema():
    import pytest
    from api.services.reports_contracts import build_report_prompt
    with pytest.raises(ValueError, match="synthesized_schema"):
        build_report_prompt(
            template_id="custom",
            material_context="some text",
            custom_prompt="Make a timeline",
            synthesized_schema=None,
        )


def test_contracts_custom_with_schema():
    from api.services.reports_contracts import build_report_prompt
    schema = {"title": "Timeline", "sections": [{"type": "heading", "name": "Events", "instructions": "list events"}]}
    system, user = build_report_prompt(
        template_id="custom",
        material_context="material here",
        custom_prompt="Make a timeline",
        synthesized_schema=schema,
    )
    assert "Timeline" in user
    assert "material here" in user
```

- [x] **Step 2: Run full test suite**

```bash
python3 -m pytest tests/test_reports_validation.py -v
```
Expected: all PASSED (no failures, no errors).

- [x] **Step 3: Run API compile checks**

```bash
python3 -m py_compile api/reports.py api/db.py \
  api/services/reports_token_estimator.py \
  api/services/reports_contracts.py \
  api/services/reports_pdf_builder.py
```
Expected: no output.

- [x] **Step 4: Run worker compile checks**

```bash
python3 -m py_compile lambda/reports_generate/handler.py lambda/reports_generate/db.py
bash -n lambda/reports_generate/build.sh
python3 -m json.tool lambda/reports_generate/iam/api-send-message-policy.json > /dev/null
python3 -m json.tool lambda/reports_generate/iam/worker-consume-policy.json > /dev/null
```
Expected: no errors.

- [x] **Step 5: Run existing test suites to confirm no regressions**

```bash
python3 -m pytest tests/test_quiz_validation.py tests/test_quiz_phase2_validation.py \
  tests/test_flashcards_phase2_validation.py -q
```
Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add tests/test_reports_validation.py
git commit -m "test(reports): add full validation suite for token estimator, contracts, and PDF builder"
```

---

## Deployment Checklist (Manual Steps After Code)

Run these after all code is committed and reviewed:

```bash
# 1. Get the SQS queue URL (queue already exists)
aws sqs get-queue-url --queue-name reports-generate

# 2. Set env vars on Vercel API runtime:
#    REPORTS_GENERATION_QUEUE_URL=<url from step 1>
#    AWS_REGION=us-east-1  (if not already set)

# 3a. Attach worker-consume-policy to CoursemateLambda IAM role (one-time):
aws iam put-role-policy \
  --role-name CoursemateLambda \
  --policy-name reports-worker-consume \
  --policy-document file://lambda/reports_generate/iam/worker-consume-policy.json

# 3b. Attach api-send-message-policy to the API execution role (one-time):
#     The API role is the IAM role assumed by Vercel/Lambda when running api/reports.py.
#     Replace <API_EXECUTION_ROLE> with your actual role name (e.g. CoursemateAPIRole).
aws iam put-role-policy \
  --role-name <API_EXECUTION_ROLE> \
  --policy-name reports-api-send-message \
  --policy-document file://lambda/reports_generate/iam/api-send-message-policy.json

# 4. Build and deploy Lambda
cd lambda/reports_generate
chmod +x build.sh
./build.sh

# 5. Create event source mapping
bash scripts/infra/setup_reports_generation_infra.sh

# 6. Set Lambda env vars (DATABASE_URL + API_KEY_ENCRYPTION_KEY)
aws lambda update-function-configuration \
  --function-name reports_generate \
  --environment "Variables={DATABASE_URL=<your_db_url>,API_KEY_ENCRYPTION_KEY=<your_key>}"
```

---

## Manual Smoke Test Checklist

1. Select sources, choose Study Guide, click Generate → estimate modal opens with token range
2. Confirm → history shows "queued" status badge
3. Refresh page → polling resumes, badge transitions queued → generating → ready
4. Viewer opens with structured sections from ReportsViewer
5. Save Report → button turns green "Saved"
6. Export as PDF → browser downloads file
7. Regenerate → returns to form with same template selected; re-runs estimate
8. Delete generation → history entry removed
9. Custom template → enter prompt, confirm → 2-call pipeline runs → viewer shows result
10. Briefing → 1 page, ≤6 sections; Study Guide → 2 pages, ≤8 sections
