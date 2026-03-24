"""
Multi-provider LLM synthesis for OneShotCourseMate.

Calls provider REST APIs directly via `requests` to avoid adding heavy SDK
packages (anthropic, openai, google-generativeai) that would exceed Vercel's
250 MB bundle limit.

Phase 1: Single-turn synthesis — retrieved chunks injected as system context.
Phase 2 (agentic loop): Each provider's tool-calling format will extend this module:
  - Claude:  Anthropic tool_use / tool_result blocks
  - OpenAI:  tools + tool_calls function-calling format
  - Gemini:  tools with function_declarations + FunctionCall/FunctionResponse
"""
import json
import logging
import os
import re
import time

import requests
from uuid import UUID

try:
    from .crypto_utils import decrypt_api_key
except ImportError:
    from crypto_utils import decrypt_api_key
try:
    from .tools import execute_rerank, execute_search_materials, execute_web_search, pull_grounding_context, resolve_references_llm
except ImportError:
    from tools import execute_rerank, execute_search_materials, execute_web_search, pull_grounding_context, resolve_references_llm

_SYSTEM_PROMPT_BASE = (
    "You are a helpful course assistant. Answer the user's question using the "
    "provided course material excerpts.\n\n"
    "**Citations**: Cite sources using isolated bracket notation — [1] for one "
    "source, [1], [2] for two, [1], [2], [3] for three, and so on. Always place "
    "a comma and space between multiple citations. Only use numbers that correspond "
    "to the excerpts provided. Never write adjacent brackets without separation "
    "(e.g. never write [1][2]).\n\n"
    "**Formatting**: Use rich Markdown to make your response clear and readable:\n"
    "- **Bold** or *italic* for key terms and emphasis.\n"
    "- Fenced code blocks (```language\\n...\\n```) ONLY for genuinely multi-line code samples. "
    "NEVER place a single identifier, function call, class name, module path, or short token "
    "in a fenced block — even if it stands alone on a line in the source material. "
    "CRITICAL: when a code token appears inside a sentence or immediately before/after prose "
    "(e.g. 'returned by env.reset() and env.step()'), it MUST stay on the same line as the "
    "surrounding words using single backticks, not split onto its own fenced block.\n"
    "- `inline code` (single backticks) for ALL identifiers, function calls, class names, "
    "module paths, dictionary keys, and any token shorter than one line. "
    "✗ WRONG (never do this): 'returned by\\n```\\nenv.reset()\\n```\\nand\\n```\\nenv.step()\\n```\\n:' "
    "✓ CORRECT: 'returned by `env.reset()` and `env.step()`:'\n"
    "- Tables: use standard GFM pipe tables (| Col | Col |\\n|---|---|\\n| val | val |). "
    "All cell content must be plain text or inline code — NEVER put a fenced code block "
    "inside a table cell; use inline backticks instead.\n"
    "- Block quotes (> ...) for verbatim quotations from readings or source material.\n"
    "- Numbered or bulleted lists for steps, enumerations, and comparisons.\n"
    "- Headers (## or ###) to organise longer multi-section responses.\n\n"
    "**Math**: Wrap mathematical expressions in LaTeX delimiters: "
    "$...$ for inline math and $$...$$ for display/block equations. "
    "Never use LaTeX delimiters for code-like tokens (e.g. env.step(action), file paths, "
    "class names, API identifiers) — these must use inline backticks.\n\n"
    "If the materials don't contain enough information to answer fully, say so clearly."
)

_SYSTEM_PROMPT_TOOL_USE = (
    "\n\n**Tool use**: Always call `search_materials` first. After reviewing the results, ask: "
    "can I give a complete, specific, and accurate answer from these materials alone? "
    "If there is any doubt — the material is vague, missing key details, doesn't directly "
    "address the question, or the question involves implementation specifics, external libraries, "
    "or concepts not well-covered — call `web_search` immediately. Prefer calling `web_search` "
    "over giving a partial or hedged answer. Never use `web_search` as a first resort before "
    "`search_materials`, but default to calling it whenever the course material leaves anything "
    "unexplained or underspecified. "
    "If `rerank_results` is available, call it after `search_materials` when the results seem "
    "noisy or loosely related to the query — pass the chunk_ids from the search result and the "
    "same query. Skip reranking when results are already clearly relevant."
)

# Full prompt with tool use instructions — only used for agentic loop (OpenAI).
# Non-agentic providers (Claude, Gemini) use _SYSTEM_PROMPT_BASE to avoid the
# model hallucinating tool call syntax as plain text in its response.
SYSTEM_PROMPT = _SYSTEM_PROMPT_BASE + _SYSTEM_PROMPT_TOOL_USE

_TIMEOUT = 60  # seconds
DEFAULT_AGENTIC_PROVIDER = "openai"
DEFAULT_AGENTIC_MODEL = "gpt-4o-mini"
MAX_TOOL_ITERATIONS = 4

logger = logging.getLogger(__name__)


def _json_safe_chunk_id(value):
    if isinstance(value, UUID):
        return str(value)
    return value


def _is_enabled(env_name: str, default: bool = False) -> bool:
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _safe_int_env(env_name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(high, value))


def _dedupe_preserve_order(values: list) -> list:
    seen = set()
    out = []
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _truncate_text(value: str, limit: int = 180) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


_INLINE_TOKEN_PATTERN = re.compile(
    r"^(?:"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\([^`\n]*\)"  # fn()/obj.method()
    r"|[A-Za-z_][A-Za-z0-9_./:-]*"  # identifier/path/token
    r"|[A-Za-z_][A-Za-z0-9_]*\[[^`\n]+\]"  # key[index]
    r")$"
)

_LIKELY_MATH_PATTERN = re.compile(
    r"(\\[A-Za-z]+|\d|[=+\-*/^_])"
)


def _looks_inline_token(value: str) -> bool:
    text = (value or "").strip()
    if not text or "\n" in text or len(text) > 120:
        return False
    if text.startswith(("-", "*", ">")):
        return False
    return _INLINE_TOKEN_PATTERN.match(text) is not None


def _looks_like_math(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    return _LIKELY_MATH_PATTERN.search(text) is not None


def _normalize_llm_markdown(text: str) -> str:
    """
    Apply deterministic formatting fixes for common model mistakes:
    - one-line fenced blocks -> inline code
    - non-math $$...$$ blocks -> inline code
    - punctuation stranded on a new line after inline code
    """
    normalized = (text or "").strip()
    if not normalized:
        return ""

    # Convert one-line fenced code blocks to inline code tokens.
    fence_pattern = re.compile(r"```[ \t]*([A-Za-z0-9_+-]+)?[ \t]*\n([^\n`]+)\n```")

    def _replace_one_line_fence(match: re.Match) -> str:
        token = match.group(2).strip()
        if _looks_inline_token(token):
            return f"`{token}`"
        return match.group(0)

    normalized = fence_pattern.sub(_replace_one_line_fence, normalized)

    # Convert non-math display LaTeX tokens to inline code.
    display_math_pattern = re.compile(r"\$\$\s*([^$\n][^$]{0,140}?)\s*\$\$")

    def _replace_non_math_display(match: re.Match) -> str:
        token = match.group(1).strip()
        if _looks_like_math(token):
            return match.group(0)
        if _looks_inline_token(token):
            return f"`{token}`"
        return match.group(0)

    normalized = display_math_pattern.sub(_replace_non_math_display, normalized)

    # Keep punctuation on same line when it follows an inline code token.
    normalized = re.sub(r"`([^`\n]+)`\n([:;,.!?])", r"`\1`\2", normalized)

    # Collapse sentence fragments split around converted inline code.
    normalized = re.sub(r"([A-Za-z0-9)\]])\n`([^`\n]+)`\n([A-Za-z(])", r"\1 `\2` \3", normalized)

    return normalized


def _char_cap_from_tokens(tokens: int) -> int:
    return max(200, int(tokens * 4))


def _chunk_previews(chunks: list, max_items: int = 3, excerpt_chars: int = 120) -> list:
    previews = []
    for chunk in (chunks or [])[:max_items]:
        previews.append(
            {
                "id": _json_safe_chunk_id(chunk.get("id")),
                "chunk_type": chunk.get("chunk_type"),
                "similarity": chunk.get("similarity"),
                "excerpt": _truncate_text(chunk.get("chunk_text", ""), excerpt_chars),
            }
        )
    return previews


def _id_preview(values: list, max_items: int = 12) -> list:
    return [str(v) for v in (values or [])[:max_items]]


def _get_api_key(conn, user_id: int, provider: str) -> str:
    """Fetch and decrypt the user's stored API key for the given provider."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT encrypted_key FROM user_api_keys WHERE user_id = %s AND provider = %s",
        (user_id, provider),
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise ValueError(f"No {provider} API key found. Add your key in Settings.")
    return decrypt_api_key(row['encrypted_key'])


def _format_context(chunks: list) -> str:
    """Format retrieved chunks into a numbered context block for the system prompt."""
    if not chunks:
        return "No relevant course material was found for this query."
    parts = []
    for i, c in enumerate(chunks, 1):
        header = f"[{i}] (type={c['chunk_type']}"
        if c.get('page_number'):
            header += f", page {c['page_number']}"
        header += f", similarity={c['similarity']:.3f})"
        parts.append(f"{header}\n{c['chunk_text']}")
    return "\n\n---\n\n".join(parts)


def _build_system_context(chunks: list, grounding_text: str = "") -> str:
    context = _format_context(chunks)
    if grounding_text:
        return f"{SYSTEM_PROMPT}\n\n{grounding_text}\n\nCourse material excerpts:\n{context}"
    return f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}"


def _build_layered_system_context(
    *,
    task_and_policy: str,
    resolver_result: dict,
    carryover_evidence_text: str,
    fresh_evidence_text: str,
    conflict_notes: str,
    user_turn: str,
    required_entities: list | None = None,
    selected_model_draft: str = "",
    model_web_handoff: dict | None = None,
    low_conf_not_needed_override: bool = False,
) -> str:
    resolved_tokens = _safe_int_env("GROUNDING_CONTEXT_TOKENS_RESOLVED", 300, 100, 1200)
    carry_tokens = _safe_int_env("GROUNDING_CONTEXT_TOKENS_CARRYOVER", 2200, 500, 4000)
    fresh_tokens = _safe_int_env("GROUNDING_CONTEXT_TOKENS_FRESH", 2500, 500, 4000)
    conflict_tokens = _safe_int_env("GROUNDING_CONTEXT_TOKENS_CONFLICT", 300, 100, 1200)

    required_coverage_section = ""
    if required_entities:
        items_str = "\n".join(f"- {e}" for e in required_entities)
        required_coverage_section = (
            "## RequiredCoverage\n"
            "The user is asking about items they explicitly referenced from your prior response.\n"
            "Your answer MUST address ALL of the following items. Do not omit any. "
            "Do not introduce items not in this list:\n"
            f"{items_str}\n"
            "If your retrieved context does not contain information for a specific item, "
            "state explicitly that no information was found for it rather than substituting "
            "a different item.\n\n"
        )

    handoff_section = ""
    handoff_policy = ""
    if isinstance(model_web_handoff, dict) and model_web_handoff:
        handoff_section = (
            "## WebSearchHandoff\n"
            f"{_truncate_text(json.dumps(model_web_handoff), 2000)}\n\n"
        )
        recommendation = str(model_web_handoff.get("web_search_recommendation", "optional")).lower()
        if recommendation == "required":
            handoff_policy = (
                "## WebSearchHandoffPolicy\n"
                "The first model recommends REQUIRED web search. Call `web_search` before finalizing if "
                "the answer depends on external or underspecified facts.\n\n"
            )
        elif recommendation == "not_needed" and not low_conf_not_needed_override:
            handoff_policy = (
                "## WebSearchHandoffPolicy\n"
                "The first model recommends NOT_NEEDED with sufficient confidence. Prefer course evidence "
                "unless contradictions or critical gaps appear.\n\n"
            )
        elif recommendation == "not_needed" and low_conf_not_needed_override:
            handoff_policy = (
                "## WebSearchHandoffPolicy\n"
                "Guardrail override active: first model said NOT_NEEDED at low confidence. Treat this as "
                "OPTIONAL and call `web_search` whenever evidence is incomplete or uncertain.\n\n"
            )
        else:
            handoff_policy = (
                "## WebSearchHandoffPolicy\n"
                "The first model marked web search as OPTIONAL. Call `web_search` when course evidence is "
                "incomplete, vague, or missing implementation detail.\n\n"
            )

    return (
        f"{task_and_policy}\n\n"
        "## ResolvedFollowupContext\n"
        f"{_truncate_text(json.dumps(resolver_result), _char_cap_from_tokens(resolved_tokens))}\n\n"
        "## CarryoverEvidence\n"
        f"{_truncate_text(carryover_evidence_text, _char_cap_from_tokens(carry_tokens))}\n\n"
        "## FreshEvidence\n"
        f"{_truncate_text(fresh_evidence_text, _char_cap_from_tokens(fresh_tokens))}\n\n"
        "## ConflictNotes\n"
        f"{_truncate_text(conflict_notes, _char_cap_from_tokens(conflict_tokens))}\n\n"
        f"{required_coverage_section}"
        f"{handoff_section}"
        f"{handoff_policy}"
        "## SelectedModelDraft\n"
        f"{_truncate_text(selected_model_draft, 3000)}\n\n"
        "## UserTurn\n"
        f"{_truncate_text(user_turn, 1200)}"
    )


def _verify_grounding(final_text: str, resolver_result: dict, grounding_refs: list) -> dict:
    text = (final_text or "").strip()
    intent = str((resolver_result or {}).get("intent_type", "fresh")).lower()
    entities = (resolver_result or {}).get("resolved_entities") or []
    required_entities = (resolver_result or {}).get("required_entities") or []
    missing_entities = []
    missing_required = []
    lowered = text.lower()

    if intent == "followup" and entities:
        for entity in entities:
            token = str(entity or "").strip().lower()
            if token and token not in lowered:
                missing_entities.append(entity)

    if required_entities:
        for entity in required_entities:
            token = str(entity or "").strip().lower()
            if token and token not in lowered:
                missing_required.append(entity)

    citation_refs = re.findall(r"\[(\d+)\]", text)
    has_citation = len(citation_refs) > 0
    generic_markers = ("entire course", "overall course", "generally in this course")
    looks_generic = any(marker in lowered for marker in generic_markers)
    passed = (
        len(missing_entities) == 0
        and len(missing_required) == 0
        and (has_citation or len(grounding_refs or []) == 0)
        and not looks_generic
    )
    return {
        "passed": bool(passed),
        "missing_entities": missing_entities,
        "missing_required": missing_required,
        "has_citation": has_citation,
        "looks_generic": looks_generic,
    }


def _repair_response_openai(
    *,
    api_key: str,
    model: str,
    messages: list,
    verifier_result: dict,
    grounding_refs: list,
    required_entities: list | None = None,
) -> str:
    missing_entities = verifier_result.get("missing_entities") or []
    missing_required = verifier_result.get("missing_required") or []

    if missing_required:
        all_required = required_entities or missing_required
        prompt = (
            "Your response did not address the following required items: "
            f"{missing_required}.\n"
            f"Revise your answer to include ALL of: {all_required}.\n"
            "Do not introduce any additional items beyond this list.\n"
            "If your retrieved context does not contain information for a specific item, "
            "state explicitly that no information was found for it."
        )
    else:
        prompt = (
            "Revise the assistant answer to be strictly grounded.\n"
            f"Missing entities: {missing_entities}\n"
            f"Grounding refs available: {grounding_refs[:20]}\n"
            "Do not provide generic course-wide summaries."
        )
    repair_messages = list(messages) + [{"role": "user", "content": prompt}]
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": repair_messages, "temperature": 0.1},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return _message_text(response.json()["choices"][0]["message"]).strip()


def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts).strip()
    return ""


def _resolve_provider_model(ai_provider: str | None, ai_model: str | None) -> tuple[str, str]:
    provider = ai_provider or DEFAULT_AGENTIC_PROVIDER
    model = ai_model
    if provider == "openai" and not model:
        model = DEFAULT_AGENTIC_MODEL
    if not model:
        raise ValueError(f"ai_model is required for provider '{provider}'")
    return provider, model


def _extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw, re.IGNORECASE)
        if fenced:
            raw = fenced[0].strip()
    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _normalize_web_search_handoff(handoff: dict | None) -> dict:
    data = handoff if isinstance(handoff, dict) else {}
    recommendation = str(data.get("web_search_recommendation", "optional")).strip().lower()
    if recommendation not in ("required", "optional", "not_needed"):
        recommendation = "optional"

    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    missing_facts = data.get("missing_facts")
    if not isinstance(missing_facts, list):
        missing_facts = []
    missing_facts = [str(v).strip() for v in missing_facts if str(v).strip()][:6]

    suggested_queries = data.get("suggested_queries")
    if not isinstance(suggested_queries, list):
        suggested_queries = []
    suggested_queries = [str(v).strip() for v in suggested_queries if str(v).strip()][:4]

    reasoning = str(data.get("reasoning", "") or "").strip()
    return {
        "web_search_recommendation": recommendation,
        "confidence": confidence,
        "missing_facts": missing_facts,
        "suggested_queries": suggested_queries,
        "reasoning": reasoning,
    }


def _assess_web_search_handoff(
    *,
    synthesis_fn,
    model: str,
    api_key: str,
    user_message: str,
    selected_model_draft: str,
) -> dict:
    """Ask the selected model for web-search routing hints and normalize response."""
    if not (selected_model_draft or "").strip():
        return _normalize_web_search_handoff({"web_search_recommendation": "optional", "confidence": 0.5})

    assessment_context = "Assessment-only context for tool routing. No citations required."
    assessment_prompt = (
        "You are creating a structured handoff for another model that orchestrates tools.\n"
        "Given USER_QUESTION and DRAFT_ANSWER, decide whether external web search is needed.\n"
        "Use ONLY THE FOLLOWING LABELS: required, optional, not_needed.\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "web_search_recommendation": "required|optional|not_needed",\n'
        '  "confidence": 0.0,\n'
        '  "missing_facts": ["..."],\n'
        '  "suggested_queries": ["..."],\n'
        '  "reasoning": "..."\n'
        "}\n"
        "Rules:\n"
        "- confidence must be between 0 and 1.\n"
        "- If there are notable unknowns in the draft answer, avoid not_needed.\n"
        "- suggested_queries should be empty when recommendation is not_needed.\n\n"
        f"USER_QUESTION:\n{_truncate_text(user_message, 2500)}\n\n"
        f"DRAFT_ANSWER:\n{_truncate_text(selected_model_draft, 3500)}"
    )

    try:
        raw = synthesis_fn(assessment_context, assessment_prompt, model, api_key)
        parsed = _extract_json_object(raw)
        normalized = _normalize_web_search_handoff(parsed)
        normalized["raw_handoff_excerpt"] = _truncate_text(raw, 400)
        return normalized
    except Exception as exc:
        fallback = _normalize_web_search_handoff({"web_search_recommendation": "optional", "confidence": 0.5})
        fallback["error"] = f"handoff_assessment_failed: {exc}"
        return fallback


def _synthesize_claude(context: str, user_message: str, model: str, api_key: str) -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "system": f"{_SYSTEM_PROMPT_BASE}\n\nCourse material excerpts:\n{context}",
            "messages": [{"role": "user", "content": user_message}],
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def _synthesize_openai(context: str, user_message: str, model: str, api_key: str) -> str:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": f"{_SYSTEM_PROMPT_BASE}\n\nCourse material excerpts:\n{context}",
                },
                {"role": "user", "content": user_message},
            ],
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _synthesize_gemini(context: str, user_message: str, model: str, api_key: str) -> str:
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "system_instruction": {
                "parts": [{"text": f"{_SYSTEM_PROMPT_BASE}\n\nCourse material excerpts:\n{context}"}]
            },
            "contents": [{"parts": [{"text": user_message}]}],
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def _emit_web_results(on_event, text: str, max_results: int = 3):
    """Parse web search result text and emit one web_result event per result (up to max_results)."""
    blocks = re.split(r'\[W\d+\]', text)
    emitted = 0
    for block in blocks[1:]:  # skip header block
        if emitted >= max_results:
            break
        url_match = re.search(r'url=(\S+)', block)
        if not url_match:
            continue
        url = url_match.group(1)
        content = block[url_match.end():].strip()[:200]
        on_event({"type": "web_result", "url": url, "excerpt": content})
        emitted += 1


def run_agent_openai(
    conn,
    user_message: str,
    model: str,
    api_key: str,
    chunks: list,
    chat_id: int | None,
    context_material_ids: list,
    selected_model_draft: str = "",
    model_web_handoff: dict | None = None,
    on_event=None,
) -> tuple[str, list, list, dict]:
    debug = _is_enabled("AGENTIC_LOOP_DEBUG", default=False)
    resolver_enabled = _is_enabled("GROUNDING_RESOLVER_ENABLED", default=True)
    fusion_enabled = _is_enabled("GROUNDING_FUSION_ENABLED", default=True)
    verifier_enabled = _is_enabled("GROUNDING_VERIFIER_ENABLED", default=True)
    mode = "fresh"
    resolver_result = {
        "intent_type": "fresh",
        "resolved_query": user_message,
        "resolved_entities": [],
        "carryover_chunk_ids": [],
        "confidence": 0.0,
        "reasoning_brief": "resolver disabled",
    }
    if resolver_enabled:
        resolver_result = resolve_references_llm(
            conn=conn,
            chat_id=chat_id,
            current_query=user_message,
            selected_material_ids=context_material_ids,
            api_key=api_key,
            model=model,
        )
    mode = resolver_result.get("intent_type", "fresh")
    resolved_query = resolver_result.get("resolved_query") or user_message
    resolved_entities = resolver_result.get("resolved_entities") or []
    required_entities = resolver_result.get("required_entities") or []
    resolver_confidence = float(resolver_result.get("confidence", 0.0) or 0.0)

    initial_search = execute_search_materials(
        conn=conn,
        query=resolved_query,
        material_ids=context_material_ids,
        top_k=10 if mode in ("followup", "mixed") else 8,
        mode=mode if fusion_enabled else "fresh",
        anchor_chunk_ids=resolver_result.get("carryover_chunk_ids") or [],
        resolved_entities=resolved_entities,
    )
    initial_chunks = chunks or []
    if initial_search.get("chunk_ids"):
        initial_chunks = []
        for cid in initial_search["chunk_ids"]:
            initial_chunks.append(
                {
                    "id": cid,
                    "chunk_type": "fused",
                    "similarity": 0.7,
                    "chunk_text": f"[ref:{cid}]",
                }
            )

    grounding_refs = _dedupe_preserve_order(
        [_json_safe_chunk_id(c.get("id")) for c in initial_chunks if c.get("id") is not None]
    )
    grounding_text = ""
    pulled_chunk_ids = []
    carryover_text = ""
    fresh_text = initial_search.get("text", "")
    carryover_count = initial_search.get("meta", {}).get("carryover_count", 0)
    fresh_count = initial_search.get("meta", {}).get("fresh_count", len(chunks or []))
    if chat_id is not None:
        pulled = pull_grounding_context(conn, chat_id, user_message)
        grounding_text = pulled.get("text", "")
        pulled_chunk_ids = pulled.get("chunk_ids", []) or []
        grounding_refs.extend(pulled_chunk_ids)
        grounding_refs = _dedupe_preserve_order(grounding_refs)
        carryover_text = grounding_text

    if debug:
        logger.info(
            "agentic_loop_debug",
            extra={
                "event": "loop_start",
                "chat_id": chat_id,
                "model": model,
                "seed_chunk_count": len(initial_chunks or []),
                "seed_chunk_ids": _id_preview(
                    [_json_safe_chunk_id(c.get("id")) for c in initial_chunks if c.get("id") is not None]
                ),
                "seed_chunk_previews": _chunk_previews(initial_chunks),
                "grounding_pull_chunk_ids": _id_preview(pulled_chunk_ids),
                "grounding_text_excerpt": _truncate_text(grounding_text, 280),
                "resolver_intent_type": mode,
                "resolver_confidence": resolver_confidence,
                "resolver_entities": resolved_entities,
                "required_entities": required_entities,
            },
        )

    handoff = _normalize_web_search_handoff(model_web_handoff)
    handoff_conf_threshold = float(
        os.environ.get("AGENTIC_HANDOFF_NOT_NEEDED_MIN_CONFIDENCE", "0.70") or 0.70
    )
    handoff_conf_threshold = max(0.0, min(1.0, handoff_conf_threshold))
    low_conf_not_needed_override = (
        handoff.get("web_search_recommendation") == "not_needed"
        and float(handoff.get("confidence", 0.0) or 0.0) < handoff_conf_threshold
    )
    web_search_allowed_by_handoff = (
        handoff.get("web_search_recommendation") != "not_needed"
        or low_conf_not_needed_override
    )

    if on_event:
        on_event(
            {
                "type": "handoff_decision",
                "recommendation": handoff.get("web_search_recommendation"),
                "confidence": handoff.get("confidence"),
                "threshold": handoff_conf_threshold,
                "override": low_conf_not_needed_override,
                "web_search_allowed": web_search_allowed_by_handoff,
                "missing_facts": handoff.get("missing_facts", []),
                "suggested_queries": handoff.get("suggested_queries", []),
                "reasoning": handoff.get("reasoning", ""),
            }
        )

    conflict_notes = ""
    if mode == "followup" and fresh_count and carryover_count == 0:
        conflict_notes = "Followup intent detected but no carryover evidence available."
    elif mode == "fresh" and carryover_count > 0:
        conflict_notes = "Fresh intent selected; carryover evidence deprioritized."

    messages = [
        {
            "role": "system",
            "content": _build_layered_system_context(
                task_and_policy=SYSTEM_PROMPT,
                resolver_result=resolver_result,
                carryover_evidence_text=carryover_text,
                fresh_evidence_text=fresh_text,
                conflict_notes=conflict_notes,
                user_turn=user_message,
                required_entities=required_entities,
                selected_model_draft=selected_model_draft,
                model_web_handoff=handoff,
                low_conf_not_needed_override=low_conf_not_needed_override,
            ),
        },
        {"role": "user", "content": resolved_query},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_materials",
                "description": (
                    "Search selected course materials for relevant chunks and return evidence."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "default": 8},
                    },
                    "required": ["query"],
                },
            },
        }
    ]
    if _is_enabled("AGENTIC_WEB_SEARCH_ENABLED") and web_search_allowed_by_handoff:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information not fully covered by course materials. Use this whenever search_materials results are vague, incomplete, or don't directly answer the question — especially for implementation details, API usage, external libraries, or concepts that need more depth.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                },
            }
        )
    if _is_enabled("AGENTIC_RERANK_ENABLED"):
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "rerank_results",
                    "description": (
                        "Re-rank a set of retrieved chunk IDs by relevance to a query using a neural reranker. "
                        "Call this after search_materials when the results feel noisy, loosely related, or the query "
                        "is complex and multi-faceted. Pass the chunk_ids from the prior search call."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "chunk_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Chunk UUIDs to rerank, from a prior search_materials result.",
                            },
                            "top_n": {"type": "integer", "default": 5},
                        },
                        "required": ["query", "chunk_ids"],
                    },
                },
            }
        )

    max_iterations = _safe_int_env("AGENTIC_MAX_ITERATIONS", MAX_TOOL_ITERATIONS, 1, 8)
    tool_trace = []
    final_text = ""

    for iteration in range(1, max_iterations + 1):
        started = time.time()
        if on_event:
            on_event({"type": "loop_start", "iteration": iteration, "max": max_iterations})
        if debug:
            logger.info(
                "agentic_loop_debug",
                extra={
                    "event": "openai_request",
                    "chat_id": chat_id,
                    "iteration": iteration,
                    "message_count": len(messages),
                    "grounding_ref_count": len(grounding_refs),
                    "grounding_ref_ids": _id_preview(grounding_refs),
                },
            )
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.2,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        choice = payload["choices"][0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []
        if debug:
            logger.info(
                "agentic_loop_debug",
                extra={
                    "event": "openai_response",
                    "chat_id": chat_id,
                    "iteration": iteration,
                    "finish_reason": choice.get("finish_reason"),
                    "tool_call_count": len(tool_calls),
                    "assistant_excerpt": _truncate_text(_message_text(message), 240),
                },
            )

        if not tool_calls:
            final_text = _message_text(message).strip()
            if not final_text:
                final_text = "I could not synthesize a response from the available context."
            tool_trace.append(
                {
                    "iteration": iteration,
                    "finish_reason": choice.get("finish_reason"),
                    "tool_calls": 0,
                    "latency_ms": int((time.time() - started) * 1000),
                }
            )
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            }
        )

        for call in tool_calls:
            name = call.get("function", {}).get("name")
            raw_args = call.get("function", {}).get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            if debug:
                logger.info(
                    "agentic_loop_debug",
                    extra={
                        "event": "tool_dispatch",
                        "chat_id": chat_id,
                        "iteration": iteration,
                        "tool_name": name,
                        "tool_args": args,
                    },
                )

            if name == "search_materials":
                result = execute_search_materials(
                    conn=conn,
                    query=args.get("query", ""),
                    material_ids=context_material_ids,
                    top_k=args.get("top_k", 8),
                    mode=mode if fusion_enabled else "fresh",
                    anchor_chunk_ids=grounding_refs,
                    resolved_entities=resolved_entities,
                )
                if on_event:
                    found_count = len(result.get("chunk_ids", []))
                    on_event({"type": "sources_found", "chunks": result.get("chunks", []), "result_count": found_count})
            elif name == "web_search":
                if on_event:
                    on_event({"type": "web_search_start", "query": args.get("query", "")})
                result = execute_web_search(conn, args.get("query", ""))
                if on_event:
                    _emit_web_results(on_event, result.get("text", ""))
            elif name == "rerank_results":
                result = execute_rerank(conn, args.get("query", ""), args.get("chunk_ids", []), args.get("top_n", 5))
                if on_event:
                    meta = result.get("meta", {})
                    on_event({
                        "type": "rerank",
                        "input_count": meta.get("input_count", len(args.get("chunk_ids", []))),
                        "output_count": meta.get("output_count", len(result.get("chunk_ids", []))),
                    })
            else:
                result = {
                    "text": f"Unsupported tool: {name}",
                    "chunk_ids": [],
                    "meta": {"tool": name or "unknown", "error": "unsupported_tool"},
                }

            grounding_refs.extend(result.get("chunk_ids", []))
            grounding_refs = _dedupe_preserve_order(grounding_refs)
            if debug:
                logger.info(
                    "agentic_loop_debug",
                    extra={
                        "event": "tool_result",
                        "chat_id": chat_id,
                        "iteration": iteration,
                        "tool_name": name,
                        "result_chunk_count": len(result.get("chunk_ids", []) or []),
                        "result_chunk_ids": _id_preview(result.get("chunk_ids", []) or []),
                        "result_excerpt": _truncate_text(result.get("text", ""), 280),
                        "grounding_ref_count": len(grounding_refs),
                        "grounding_ref_ids": _id_preview(grounding_refs),
                    },
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": result.get("text", ""),
                }
            )
            trace_entry = {
                "iteration": iteration,
                "tool": name,
                "latency_ms": result.get("meta", {}).get("latency_ms"),
                "result_count": result.get("meta", {}).get("result_count"),
                "mode": result.get("meta", {}).get("mode"),
            }
            if name == "web_search":
                trace_entry["urls"] = result.get("meta", {}).get("urls") or []
            tool_trace.append(trace_entry)
        tool_trace.append(
            {
                "iteration": iteration,
                "finish_reason": choice.get("finish_reason"),
                "tool_calls": len(tool_calls),
                "latency_ms": int((time.time() - started) * 1000),
            }
        )

    if not final_text:
        final_text = (
            "I ran out of tool-call iterations before finishing. "
            "Please ask a narrower follow-up."
        )

    verifier_result = {
        "passed": True,
        "missing_entities": [],
        "has_citation": False,
        "looks_generic": False,
    }
    repair_invoked = False
    if verifier_enabled:
        verifier_result = _verify_grounding(final_text, resolver_result, grounding_refs)
        if not verifier_result["passed"]:
            repair_invoked = True
            final_text = _repair_response_openai(
                api_key=api_key,
                model=model,
                messages=messages,
                verifier_result=verifier_result,
                grounding_refs=grounding_refs,
                required_entities=required_entities,
            )
            verifier_result = _verify_grounding(final_text, resolver_result, grounding_refs)

    final_text = _normalize_llm_markdown(final_text)

    if on_event:
        on_event({"type": "text", "content": final_text})

    if debug:
        logger.info(
            "agentic_loop_debug",
            extra={
                "event": "loop_end",
                "chat_id": chat_id,
                "max_iterations": max_iterations,
                "trace_entries": len(tool_trace),
                "tool_call_entries": len([t for t in tool_trace if t.get("tool")]),
                "grounding_ref_count": len(grounding_refs),
                "grounding_ref_ids": _id_preview(grounding_refs),
                "final_excerpt": _truncate_text(final_text, 280),
                "verifier_passed": verifier_result.get("passed", True),
                "repair_invoked": repair_invoked,
            },
        )
    metadata = {
        "intent_type": mode,
        "resolver_confidence": resolver_confidence,
        "resolver_entities": resolved_entities,
        "required_entities": required_entities,
        "verifier_passed": verifier_result.get("passed", True),
        "verifier_missing_required": verifier_result.get("missing_required") or [],
        "repair_invoked": repair_invoked,
        "carryover_ref_count": carryover_count,
        "fresh_ref_count": fresh_count,
        "resolver_reasoning": resolver_result.get("reasoning_brief"),
        "web_handoff": handoff,
        "web_handoff_not_needed_conf_threshold": handoff_conf_threshold,
        "web_handoff_low_conf_override": low_conf_not_needed_override,
        "web_search_allowed_by_handoff": web_search_allowed_by_handoff,
    }
    return final_text, grounding_refs, tool_trace, metadata


_PROVIDERS = {
    "claude": _synthesize_claude,
    "openai": _synthesize_openai,
    "gemini": _synthesize_gemini,
}


def synthesize(
    conn,
    user_id: int,
    ai_provider: str | None,
    ai_model: str | None,
    user_message: str,
    chunks: list,
    chat_id: int | None = None,
    context_material_ids: list | None = None,
    on_event=None,
    force_context_only: bool = False,
) -> tuple:
    """
    Synthesize an LLM response using the user's chosen provider and model.

    Returns:
        (synthesized_text: str, chunk_ids_used: list[int])

    Raises:
        ValueError: if no API key is stored for the provider, or unsupported provider.
        requests.HTTPError: if the provider API returns a non-2xx response.
    """
    ai_provider, ai_model = _resolve_provider_model(ai_provider, ai_model)
    if ai_provider not in _PROVIDERS:
        raise ValueError(f"Unsupported provider: {ai_provider}")

    selected_provider_api_key = _get_api_key(conn, user_id, ai_provider)
    material_scope = context_material_ids if isinstance(context_material_ids, list) else []
    use_agentic = _is_enabled("AGENTIC_LOOP_ENABLED", default=False)
    if force_context_only:
        use_agentic = False

    if use_agentic:
        context = _format_context(chunks)
        fn = _PROVIDERS[ai_provider]
        selected_model_draft = fn(context, user_message, ai_model, selected_provider_api_key)
        web_handoff_enabled = _is_enabled("AGENTIC_WEB_HANDOFF_ENABLED", default=True)
        selected_model_handoff = None
        if web_handoff_enabled:
            selected_model_handoff = _assess_web_search_handoff(
                synthesis_fn=fn,
                model=ai_model,
                api_key=selected_provider_api_key,
                user_message=user_message,
                selected_model_draft=selected_model_draft,
            )
        agentic_api_key = _get_api_key(conn, user_id, DEFAULT_AGENTIC_PROVIDER)
        text, grounding_refs, tool_trace, metadata = run_agent_openai(
            conn=conn,
            user_message=user_message,
            model=DEFAULT_AGENTIC_MODEL,
            api_key=agentic_api_key,
            chunks=chunks,
            chat_id=chat_id,
            context_material_ids=material_scope,
            selected_model_draft=selected_model_draft,
            model_web_handoff=selected_model_handoff,
            on_event=on_event,
        )
        logger.info(
            "agentic_loop_trace",
            extra={
                "chat_id": chat_id,
                "provider": ai_provider,
                "model": ai_model,
                "agentic_provider": DEFAULT_AGENTIC_PROVIDER,
                "agentic_model": DEFAULT_AGENTIC_MODEL,
                "iterations": len([t for t in tool_trace if "tool_calls" in t]),
                "tool_calls": len([t for t in tool_trace if t.get("tool")]),
                "intent_type": metadata.get("intent_type"),
                "resolver_confidence": metadata.get("resolver_confidence"),
                "verifier_passed": metadata.get("verifier_passed"),
                "repair_invoked": metadata.get("repair_invoked"),
                "web_handoff_recommendation": (metadata.get("web_handoff") or {}).get("web_search_recommendation"),
                "web_handoff_confidence": (metadata.get("web_handoff") or {}).get("confidence"),
                "web_handoff_low_conf_override": metadata.get("web_handoff_low_conf_override"),
                "web_search_allowed_by_handoff": metadata.get("web_search_allowed_by_handoff"),
            },
        )
        return text, grounding_refs, metadata, tool_trace

    context = _format_context(chunks)
    fn = _PROVIDERS[ai_provider]
    text = fn(context, user_message, ai_model, selected_provider_api_key)
    text = _normalize_llm_markdown(text)
    chunk_ids = [
        _json_safe_chunk_id(c.get("id"))
        for c in chunks
        if c.get("id") is not None
    ]
    return text, chunk_ids, {
        "intent_type": "fresh",
        "resolver_confidence": 0.0,
        "verifier_passed": True,
        "repair_invoked": False,
        "carryover_ref_count": 0,
        "fresh_ref_count": len(chunk_ids),
    }, []
