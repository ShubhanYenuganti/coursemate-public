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
TOPIC_SUMMARY_BUDGET = 2_000
MAX_SECTIONS = 8
MAX_PAGE_COUNT = 2
REPORTS_LOCK_NAMESPACE = 4101

VALID_BLOCK_TYPES = frozenset(
    {
        "heading",
        "subheading",
        "paragraph",
        "bullet_list",
        "callout",
        "equation",
        "page_break",
    }
)

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
    "You are an academic study guide generator. "
    + _COMMON_RULES
    + 'Output format:\n'
    + '{"title":"...","subtitle":"...","page_count":2,"sections":['
    + '{"type":"heading","content":"Overview"},'
    + '{"type":"paragraph","content":"2-3 sentence overview"},'
    + '{"type":"heading","content":"Key Concepts"},'
    + '{"type":"subheading","content":"<Concept Name>"},'
    + '{"type":"paragraph","content":"<Definition>"},'
    + '{"type":"heading","content":"Core Topics"},'
    + '{"type":"subheading","content":"<Topic Name>"},'
    + '{"type":"bullet_list","items":["point 1","point 2"]},'
    + '{"type":"heading","content":"Examples"},'
    + '{"type":"bullet_list","items":["example 1","example 2"]},'
    + '{"type":"heading","content":"Summary"},'
    + '{"type":"callout","content":"3-5 key takeaways"}]}'
)

_BRIEFING_SYSTEM = (
    "You are an executive briefing writer. "
    + _COMMON_RULES
    + 'Output format:\n'
    + '{"title":"...","subtitle":"Executive Summary","page_count":1,"sections":['
    + '{"type":"heading","content":"Background"},'
    + '{"type":"paragraph","content":"3-4 sentence situation overview"},'
    + '{"type":"heading","content":"Key Points"},'
    + '{"type":"bullet_list","items":["point — one sentence each"]},'
    + '{"type":"heading","content":"Critical Terms"},'
    + '{"type":"bullet_list","items":["Term — definition"]},'
    + '{"type":"heading","content":"Implications"},'
    + '{"type":"paragraph","content":"What this means"},'
    + '{"type":"callout","content":"Bottom line in one sentence"}]}'
)

_SUMMARY_SYSTEM = (
    "You are a document summarizer. "
    + _COMMON_RULES
    + 'Output format:\n'
    + '{"title":"Summary — <topic>","subtitle":"","page_count":2,"sections":['
    + '{"type":"heading","content":"Overview"},'
    + '{"type":"paragraph","content":"2-sentence scope"},'
    + '{"type":"heading","content":"<Topic 1>"},'
    + '{"type":"paragraph","content":"3-4 sentence summary"},'
    + '{"type":"heading","content":"<Topic 2>"},'
    + '{"type":"paragraph","content":"3-4 sentence summary"},'
    + '{"type":"heading","content":"Key Takeaways"},'
    + '{"type":"bullet_list","items":["takeaway 1","takeaway 2","takeaway 3"]}]}'
)

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

_CONTENT_FILL_SYSTEM = (
    "You are a document content generator. "
    "Return valid JSON only. No markdown fences. "
    "You are given a schema with 'instructions' fields. "
    "Replace every 'instructions' value with actual content generated from the course materials. "
    "Preserve all other fields (type, name, page_count, title, subtitle) exactly. "
    "For type=bullet_list, output 'items': [...] instead of 'content'. "
    "Output the completed schema JSON."
)


def _get_fernet() -> Fernet:
    raw = os.environ.get("API_KEY_ENCRYPTION_KEY")
    if not raw:
        raise ValueError("API_KEY_ENCRYPTION_KEY not set")
    return Fernet(raw.encode())


def decrypt_api_key(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt API key") from exc


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

    parts = []
    total = 0
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


def _build_prompt(
    template_id: str,
    material_context: str,
    custom_prompt: str | None,
    synthesized_schema: dict | None,
) -> tuple[str, str]:
    del custom_prompt
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
    user = (
        f"Report request: {custom_prompt}\n\n"
        f"Available material topics (sample):\n{topic_summary}"
    )
    return _SCHEMA_SYNTHESIS_SYSTEM, user


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


def _call_openai_json(api_key, model_id, system, user) -> dict:
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
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
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model_id,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    blocks = resp.json().get("content") or []
    raw = "\n".join(
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
    return _parse_model_json(raw)


def _call_gemini_json(api_key, model_id, system, user) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    resp = requests.post(
        url,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates") or []
    parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
    raw = "\n".join(
        str(part.get("text", ""))
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()
    return _parse_model_json(raw)


def _call_llm_json(provider, api_key, model_id, system, user) -> dict:
    if provider == "openai":
        return _call_openai_json(api_key, model_id, system, user)
    if provider == "claude":
        return _call_claude_json(api_key, model_id, system, user)
    if provider == "gemini":
        return _call_gemini_json(api_key, model_id, system, user)
    raise ValueError(f"Unsupported provider: {provider}")


def _safe_page_count(value: object) -> int:
    try:
        if isinstance(value, bool):
            return MAX_PAGE_COUNT
        parsed = int(value)
        if parsed <= 0:
            return MAX_PAGE_COUNT
        return min(parsed, MAX_PAGE_COUNT)
    except (TypeError, ValueError):
        return MAX_PAGE_COUNT


def _sanitize_error_message(error: object) -> str:
    if isinstance(error, requests.Timeout):
        return "Report generation timed out while contacting the AI provider."

    if isinstance(error, requests.HTTPError):
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if status_code in (401, 403):
            return "The configured AI provider credentials were rejected."
        if status_code == 429:
            return "The AI provider rate limit was reached. Please retry."
        if isinstance(status_code, int) and status_code >= 500:
            return "The AI provider is temporarily unavailable. Please retry."
        return "The AI provider request failed while generating the report."

    if isinstance(error, requests.RequestException):
        return "The AI provider request failed while generating the report."

    message = str(error or "").strip().lower()
    if not message:
        return "Report generation failed."
    if "no " in message and " api key configured" in message:
        return "No API key is configured for the selected provider."
    if "failed to decrypt api key" in message:
        return "The stored API key could not be decrypted."
    if "custom template requires custom_prompt" in message:
        return "Custom reports require a prompt before generation can start."
    if "custom template requires synthesized_schema" in message:
        return "The custom report schema could not be prepared."
    if "unsupported provider" in message:
        return "The selected AI provider is not supported for report generation."
    if "unknown template_id" in message:
        return "The selected report template is not supported."
    if "model returned empty content" in message or "could not parse model json output" in message:
        return "The AI provider returned an invalid report payload."
    return "Report generation failed due to an internal error."


def _try_claim_generation_lock(cursor, generation_id: int) -> bool:
    cursor.execute(
        "SELECT pg_try_advisory_lock(%s, %s) AS locked",
        (REPORTS_LOCK_NAMESPACE, generation_id),
    )
    row = cursor.fetchone() or {}
    return bool(row.get("locked"))


def _release_generation_lock(cursor, generation_id: int):
    cursor.execute(
        "SELECT pg_advisory_unlock(%s, %s)",
        (REPORTS_LOCK_NAMESPACE, generation_id),
    )
    cursor.fetchone()


def _normalize_output(raw: dict) -> dict:
    title = str(raw.get("title") or "Report").strip() or "Report"
    subtitle = str(raw.get("subtitle") or "").strip()
    page_count = _safe_page_count(raw.get("page_count") or 2)

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

        content = str(block.get("content") or block.get("instructions") or block.get("text") or "").strip()
        items = block.get("items")
        items = [str(item) for item in items if str(item).strip()] if isinstance(items, list) else None
        lines = block.get("lines")
        lines = [str(line).strip() for line in lines if str(line).strip()] if isinstance(lines, list) else None

        if not content and not items and not lines and btype != "page_break":
            continue

        entry = {"type": btype}
        if content:
            entry["content"] = content
        if items is not None:
            entry["items"] = items
        if lines is not None:
            entry["lines"] = lines

        normalized.append(entry)
        if len(normalized) >= MAX_SECTIONS:
            break

    return {
        "title": title,
        "subtitle": subtitle,
        "page_count": page_count,
        "sections": normalized,
    }


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


def _mark_failed(generation_id: int, error: object):
    if generation_id is None:
        return
    safe_error = _sanitize_error_message(error)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE report_generations SET status='failed', error=%s WHERE id=%s",
            (safe_error[:500], generation_id),
        )
        cursor.close()


def _process_generation(generation_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        lock_claimed = False
        try:
            lock_claimed = _try_claim_generation_lock(cursor, generation_id)
            if not lock_claimed:
                cursor.close()
                return

            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s FOR UPDATE",
                (generation_id,),
            )
            generation = cursor.fetchone()
            if not generation:
                cursor.close()
                return

            status = generation.get("status")
            if status not in ("queued", "generating"):
                cursor.close()
                return

            if status == "queued":
                cursor.execute(
                    "UPDATE report_generations SET status='generating', error=NULL WHERE id=%s",
                    (generation_id,),
                )
            else:
                cursor.execute(
                    "UPDATE report_generations SET error=NULL WHERE id=%s",
                    (generation_id,),
                )

            provider = generation.get("provider") or "openai"
            model_id = generation.get("model_id") or "gpt-4o-mini"
            user_id = generation["generated_by"]
            template_id = str(generation.get("template_id") or "study-guide")
            custom_prompt = str(generation.get("custom_prompt") or "").strip() or None
            material_ids = generation.get("selected_material_ids") or []
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
                raise ValueError(f"No {provider} API key configured for report generation")

            api_key = decrypt_api_key(key_row["encrypted_key"])
            full_context = _fetch_material_context(conn, material_ids)

            # Persist the generating state before the external provider call, but keep the
            # session lock so a retried message can safely reclaim abandoned work.
            conn.commit()
            cursor.close()

            synthesized_schema = None
            if template_id == "custom":
                if not custom_prompt:
                    raise ValueError("custom template requires custom_prompt")
                topic_summary = full_context[:TOPIC_SUMMARY_BUDGET]
                synth_system, synth_user = _build_synthesis_prompt(custom_prompt, topic_summary)
                synthesized_schema = _call_llm_json(provider, api_key, model_id, synth_system, synth_user)

            system, user_prompt = _build_prompt(template_id, full_context, custom_prompt, synthesized_schema)
            raw = _call_llm_json(provider, api_key, model_id, system, user_prompt)
            normalized = _normalize_output(raw)

            _persist_version(conn, generation_id, normalized)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE report_generations SET status='ready', error=NULL WHERE id=%s",
                (generation_id,),
            )
            cursor.close()
        finally:
            if lock_claimed:
                try:
                    release_cursor = conn.cursor()
                    try:
                        _release_generation_lock(release_cursor, generation_id)
                    finally:
                        release_cursor.close()
                except Exception:
                    # Connection close also releases advisory locks.
                    pass


def lambda_handler(event, context):
    del context
    records = event.get("Records") or []
    for record in records:
        generation_id = None
        try:
            body = json.loads(record.get("body") or "{}")
            generation_id = int(body["generation_id"])
        except Exception:
            continue

        try:
            _process_generation(generation_id)
        except Exception as exc:
            _mark_failed(generation_id, exc)
            raise

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
