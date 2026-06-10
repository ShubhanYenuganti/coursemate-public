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
import mimetypes
import os
import re
import time

import requests
from uuid import UUID


def _raise_for_status_verbose(response) -> None:
    """Like response.raise_for_status() but includes the provider's error body."""
    try:
        response.raise_for_status()
    except requests.HTTPError as original:
        try:
            body = response.json()
            err = body.get("error") or body
            if isinstance(err, dict):
                msg = err.get("message") or ""
                code = err.get("code") or err.get("type") or ""
                detail = f"{code}: {msg}" if code else msg
            else:
                detail = str(err)[:400]
            if detail:
                raise requests.HTTPError(
                    f"{original} — {detail}", response=response
                ) from None
        except (ValueError, AttributeError, KeyError):
            pass
        raise

try:
    from .crypto_utils import decrypt_api_key
except ImportError:
    from crypto_utils import decrypt_api_key


def _fetch_images_as_base64(s3_keys: list) -> list:
    """Fetch S3 images and return list of (mime_type, base64_data) tuples."""
    import base64
    import boto3

    region = os.environ.get('AWS_REGION', 'us-east-1')
    client = boto3.client(
        's3',
        region_name=region,
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    )
    bucket = os.environ.get('AWS_S3_BUCKET_NAME')
    result = []
    for key in (s3_keys or []):
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            data = obj['Body'].read()
            mime = mimetypes.guess_type(key)[0] or "image/jpeg"
            result.append((mime, base64.standard_b64encode(data).decode('utf-8')))
        except Exception:
            logging.getLogger(__name__).warning("Failed to fetch S3 image %s", key)
    return result


def _recall_prior_chat_images(conn, chat_id, query, exclude_s3_keys=None, top_k=3):
    """Similarity-search this chat's prior images and return (mime, base64) tuples
    for the best matches, so the model can "see" images discussed earlier in the
    conversation.

    Uses the embed_query Lambda + the chat_image_embeddings table — independent of
    the retired chunk/embedding (embed_materials) pipeline. Gated on a cheap
    existence check so chats with no stored images skip the embedding call.
    """
    if not chat_id or not (query or "").strip():
        return []
    exclude = set(exclude_s3_keys or [])
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM chat_image_embeddings WHERE chat_id = %s LIMIT 1", (chat_id,)
    )
    has_images = cursor.fetchone() is not None
    cursor.close()
    if not has_images:
        return []
    try:
        from rag import _invoke_embed_query, _search_chat_images
    except ImportError:
        from .rag import _invoke_embed_query, _search_chat_images
    vis_emb, txt_emb = _invoke_embed_query(query=query)
    emb = vis_emb or txt_emb
    if not emb:
        return []
    keys = []
    for hit in _search_chat_images(conn, emb, chat_id):
        key = hit.get("s3_key")
        if key and key not in exclude and key not in keys:
            keys.append(key)
        if len(keys) >= top_k:
            break
    return _fetch_images_as_base64(keys)


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
    "NEVER use \\[ \\] or \\( \\) — the renderer only recognises $ and $$ delimiters. "
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

_JSON_SYNTHESIS_INSTRUCTION = (
    "\n\n**Response format**: Respond using this exact two-block structure — nothing before or after:\n"
    "<REPLY>\n"
    "your full markdown answer here (plain markdown, never JSON-encoded)\n"
    "</REPLY>\n"
    "<META>\n"
    '{\"summary\": \"5-6 word phrase\", \"follow_ups\": [\"q1\", \"q2\", \"q3\"], \"clarifying_question\": null}\n'
    "</META>\n\n"
    "Rules: The REPLY block is plain markdown — write LaTeX exactly as-is (e.g. $\\frac{a}{b}$, $\\lambda$), "
    "never double backslashes. Use $...$ for inline math and $$...$$ for display equations — NEVER \\[ \\] or \\( \\). "
    "The META block is a raw JSON object with keys `summary` (string, ~5–6 words), "
    "`follow_ups` (array of 2–3 short follow-up question strings), and `clarifying_question` (string or null — "
    "only non-null if you genuinely cannot answer without knowing one specific thing)."
)

_AGENTIC_JSON_FINAL_INSTRUCTION = (
    "\n\n**Final answer format**: When you respond with your final answer to the user and you are not "
    "calling any tools in that turn, use this exact two-block structure — nothing before or after:\n"
    "<REPLY>\n"
    "your full markdown answer here (plain markdown, never JSON-encoded)\n"
    "</REPLY>\n"
    "<META>\n"
    '{\"summary\": \"5-6 word phrase\", \"follow_ups\": [\"q1\", \"q2\", \"q3\"], \"clarifying_question\": null}\n'
    "</META>\n\n"
    "Rules: The REPLY block is plain markdown — write LaTeX exactly as-is (e.g. $\\frac{a}{b}$, $\\lambda$), "
    "never double backslashes. Use $...$ for inline math and $$...$$ for display equations — NEVER \\[ \\] or \\( \\). "
    "The META block is a raw JSON object with keys `summary` (string, ~5–6 words), "
    "`follow_ups` (array of 2–3 short follow-up question strings), and `clarifying_question` (string or null — "
    "only non-null if you genuinely cannot answer without knowing one specific thing)."
)

# Agentic loop: same as SYSTEM_PROMPT plus JSON final-answer requirement.
AGENTIC_SYSTEM_PROMPT = SYSTEM_PROMPT + _AGENTIC_JSON_FINAL_INSTRUCTION

_PAGEINDEX_TOOL_USE = (
    "\n\n**Tool use**: A routing index of available course materials is provided below. "
    "Each material includes per-page summaries — use them to identify the right pages and call "
    "`get_page_content(material_id, pages)` directly with a page range (e.g. '3,4,5' or '3-5'). "
    "Only call `get_material_structure(material_id)` if the routing index has no page summaries "
    "for that material or you need sub-section detail not visible in the summaries. "
    "If the fetched content does not fully answer the question, call `get_related_materials(material_id)` "
    "to discover related materials and repeat. "
    "Do NOT call any other tools — only these three are available."
    "\n\n**High-recall retrieval policy**: Prefer recall over minimal context. Before answering, fetch "
    "2-4 candidate evidence locations when the question is conceptual, comparative, broad, multi-part, "
    "or when multiple routing summaries look plausible. Use `get_material_structure(material_id)` for "
    "conceptual or broad questions before final synthesis when page summaries alone may hide sub-section "
    "detail. When you fetch a likely page, include neighboring pages when they are likely to contain setup, "
    "definitions, results, or continuation text. Do not stop after one small fetch unless the fetched page "
    "fully and directly answers the question. For evaluation-style questions, prefer Recall@5 behavior: "
    "retrieve several plausible evidence pages first, then synthesize from the best evidence."
    "\n\n**Structure-first rule**: For broad, conceptual, comparative, multi-part, method, result, or "
    "limitation questions, you must call `get_material_structure(material_id)` before any final answer, "
    "then call `get_page_content` for the most plausible pages from that structure. Skip this only for "
    "narrow fact lookup questions where one routing summary directly identifies the exact page."
    "\n\n**Citation numbering**: Each `get_page_content` call you make becomes one numbered citation, "
    "in the order you called it. The first `get_page_content` call is citation [1], the second is [2], "
    "and so on. When you write the final answer, cite each fact using the bracket that matches the call "
    "that fetched its evidence. Do not invent citation numbers that do not correspond to a "
    "`get_page_content` call. If you fetched the same material on multiple calls, each call gets its own "
    "citation number — do not collapse them."
)

# System prompt for the PageIndex agentic loop. Uses _SYSTEM_PROMPT_BASE for
# citations/formatting, a pageindex-specific tool-use section (not _SYSTEM_PROMPT_TOOL_USE,
# which references search_materials/web_search that don't exist here), and the
# JSON final-answer schema.
PAGEINDEX_SYSTEM_PROMPT = _SYSTEM_PROMPT_BASE + _PAGEINDEX_TOOL_USE + _AGENTIC_JSON_FINAL_INSTRUCTION

_PAGEINDEX_SYNTHESIS_INSTRUCTION = (
    "\n\n**Final synthesis mode**: Retrieval is complete. The retrieved course material "
    "and web results, if any, are provided below as evidence. Answer the current user "
    "message directly from that evidence and the conversation history. Do not say you "
    "will fetch, search, inspect, retrieve, call tools, or look at course materials in "
    "the future. If the provided evidence is insufficient, say what is missing clearly."
)

_CONVERSATION_HISTORY_NOTICE = (
    "\n\n**Conversation history**: Prior turns, if any, are included as messages before "
    "the current user message. Use them for follow-ups, references, corrections, and "
    "pronouns. Respond only to the most recent user message."
)


_SUMMARY_MAX_LEN = 200

_TIMEOUT = 60  # seconds
DEFAULT_AGENTIC_PROVIDER = "openai"
DEFAULT_AGENTIC_MODEL = "gpt-4o-mini"
MAX_TOOL_ITERATIONS = 4
NON_VISION_MODEL_IDS = {"gpt-oss-120b"}

logger = logging.getLogger(__name__)


def _validate_model_supports_images(model: str | None, image_s3_keys: list | None) -> None:
    if image_s3_keys and (model or "").strip().lower() in NON_VISION_MODEL_IDS:
        raise ValueError(f"Model {model} does not support image input")


def _json_safe_chunk_id(value):
    if isinstance(value, UUID):
        return str(value)
    return value


def _is_enabled(env_name: str, default: bool = False) -> bool:
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _is_pageindex_enabled() -> bool:
    # PageIndex is now the only retrieval path. The legacy chunk/embedding
    # pipeline (embed_materials) has been retired, so this is unconditional —
    # the PAGEINDEX_RAG_ENABLED / PAGEINDEX_RETRIEVAL_ENABLED env toggles no
    # longer disable it.
    return True


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


def _cap_summary(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if len(s) > _SUMMARY_MAX_LEN:
        s = s[:_SUMMARY_MAX_LEN].rstrip()
    return s


def _normalize_math_delimiters(text: str) -> str:
    """Convert \[...\] and \(...\) to $$...$$ and $...$ so remark-math renders them."""
    text = re.sub(r'\\\[([\s\S]*?)\\\]', r'$$\1$$', text)
    text = re.sub(r'\\\(([\s\S]*?)\\\)', r'$\1$', text)
    return text


def _parse_meta_block(meta_text: str) -> tuple[str | None, list, str | None]:
    """Parse the META JSON block and return (summary, follow_ups, clarifying_question)."""
    try:
        obj = json.loads(meta_text.strip())
    except json.JSONDecodeError:
        return None, [], None
    if not isinstance(obj, dict):
        return None, [], None
    summ = obj.get("summary")
    raw_follow_ups = obj.get("follow_ups")
    follow_ups = [q for q in raw_follow_ups if isinstance(q, str)] if isinstance(raw_follow_ups, list) else []
    clarifying_question = obj.get("clarifying_question")
    if not isinstance(clarifying_question, str) or not clarifying_question.strip():
        clarifying_question = None
    return (_cap_summary(summ) if isinstance(summ, str) else None), follow_ups, clarifying_question


def _parse_synthesis_json(raw: str) -> tuple[str, str | None, list, str | None]:
    """Three-stage parser: tagged → brace-boundary → whole-text fallback."""
    original = (raw or "").strip()
    logger.debug("llm_raw_reply\n%s", original)
    if not original:
        return "", None, [], None

    # Stage 1: Tagged format — <REPLY>…</REPLY><META>…</META>
    reply_match = re.search(r"<REPLY>(.*?)</REPLY>", original, re.DOTALL)
    meta_match = re.search(r"<META>(.*?)</META>", original, re.DOTALL)
    if reply_match:
        reply = _normalize_math_delimiters(reply_match.group(1).strip())
        if meta_match:
            summary, follow_ups, clarifying_question = _parse_meta_block(meta_match.group(1))
        else:
            summary, follow_ups, clarifying_question = None, [], None
        return reply, summary, follow_ups, clarifying_question

    # Stage 2: Brace-boundary — trailing JSON object appended without tags.
    # Walk backward from the last '}' to find a balanced '{...}' candidate.
    end = original.rfind('}')
    if end != -1:
        depth = 0
        start = -1
        for i in range(end, -1, -1):
            if original[i] == '}':
                depth += 1
            elif original[i] == '{':
                depth -= 1
                if depth == 0:
                    start = i
                    break
        if start != -1:
            candidate = original[start:end + 1]
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and ("summary" in obj or "follow_ups" in obj):
                    reply = _normalize_math_delimiters(original[:start].strip())
                    summary, follow_ups, clarifying_question = _parse_meta_block(candidate)
                    return reply, summary, follow_ups, clarifying_question
            except json.JSONDecodeError:
                pass

    # Stage 3: Whole-text — treat entire output as reply with empty metadata.
    logger.debug("synthesis_parse_whole_text_fallback", extra={"excerpt": _truncate_text(original, 200)})
    return _normalize_math_delimiters(original), None, [], None


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


def _fix_unclosed_latex_delimiters(text: str) -> str:
    """Strip all $ from lines with an odd $ count to prevent broken KaTeX rendering."""
    if not text or "$" not in text:
        return text
    return "\n".join(
        line.replace("$", "") if line.count("$") % 2 != 0 else line
        for line in text.split("\n")
    )


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

    # Strip lines with unclosed LaTeX $ delimiters to prevent broken KaTeX rendering.
    normalized = _fix_unclosed_latex_delimiters(normalized)

    return normalized


def _char_cap_from_tokens(tokens: int) -> int:
    return max(200, int(tokens * 4))


# --- Multi-turn chat memory: budgeting -------------------------------------

_DEFAULT_CONTEXT_WINDOW = 128000

# Per-model context windows (tokens). Unknown models fall back to the default.
MODEL_CONTEXT_WINDOWS = {
    # Claude
    "claude-opus-4-8": 200000,
    "claude-opus-4-7": 200000,
    "claude-opus-4-6": 200000,
    "claude-sonnet-4-6": 200000,
    "claude-haiku-4-5-20251001": 200000,
    "claude-sonnet-4-5-20250929": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    # Gemini
    "gemini-3.5-flash": 1000000,
    "gemini-3.1-pro-preview": 1000000,
    "gemini-3-flash-preview": 1000000,
    "gemini-2.5-pro": 1000000,
    "gemini-2.5-flash": 1000000,
    "gemini-2.5-flash-lite": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-2.0-flash-lite": 1000000,
    # OpenAI
    "gpt-5.5": 400000,
    "gpt-5.4-mini": 400000,
    "gpt-5.4-nano": 400000,
    "gpt-5.2": 400000,
    "gpt-5.1": 400000,
    "gpt-5-mini": 400000,
    "gpt-5-nano": 400000,
    "gpt-4.1": 1000000,
    "gpt-4.1-mini": 1000000,
    "gpt-4.1-nano": 1000000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "o3": 200000,
    "o3-mini": 200000,
    "o3-pro": 200000,
    "o4-mini": 200000,
    "o1": 200000,
    "o1-pro": 200000,
    "gpt-oss-120b": 128000,
}


def _context_window_for(model: str) -> int:
    return MODEL_CONTEXT_WINDOWS.get(model, _DEFAULT_CONTEXT_WINDOW)


def _estimate_tokens(text: str) -> int:
    """Canonical token estimate: ~4 chars/token, floor of 1."""
    if not text:
        return 1
    return max(1, len(text) // 4)


RESPONSE_RESERVE_TOKENS = 4096
SAFETY_MARGIN_RATIO = 0.15
HISTORY_CONTEXT_RATIO = 0.35
OUTPUT_CONTEXT_RATIO = 0.05
MIN_OUTPUT_TOKENS = 2048
MAX_OUTPUT_TOKENS = 8192


def _history_budget(window: int, system_text: str, current_user_text: str) -> int:
    """Tokens left for replayed history after system prompt, response reserve,
    current user message, and a safety margin, capped to a fixed share of the
    model context window. Never negative."""
    used = (
        _estimate_tokens(system_text)
        + RESPONSE_RESERVE_TOKENS
        + _estimate_tokens(current_user_text)
        + int(window * SAFETY_MARGIN_RATIO)
    )
    available = max(0, window - used)
    history_cap = max(0, int(window * HISTORY_CONTEXT_RATIO))
    return min(history_cap, available)


def _output_token_cap(model: str) -> int:
    window = _context_window_for(model)
    return max(MIN_OUTPUT_TOKENS, min(MAX_OUTPUT_TOKENS, int(window * OUTPUT_CONTEXT_RATIO)))


def _compose_history(prior_turns: list, budget_tokens: int) -> list:
    """Return the newest prior turns that fit within budget_tokens, in
    chronological (oldest->newest) order. Drops oldest turns first."""
    kept_reversed = []
    running = 0
    for turn in reversed(prior_turns):  # newest first
        cost = _estimate_tokens(turn.get("content", ""))
        if running + cost > budget_tokens:
            break
        kept_reversed.append(turn)
        running += cost
    return list(reversed(kept_reversed))


def _load_chat_history(conn, chat_id, before_index) -> list:
    """Active-branch prior turns (user + assistant), oldest->newest, excluding
    soft-deleted rows and anything at/after before_index. Returns
    [{"role", "content"}]. reply_history undo blobs are intentionally ignored."""
    if chat_id is None or before_index is None:
        return []
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT role, content
        FROM chat_messages
        WHERE chat_id = %s
          AND is_deleted = FALSE
          AND role IN ('user', 'assistant')
          AND message_index < %s
        ORDER BY message_index ASC
        """,
        (chat_id, before_index),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def _build_history_turns(conn, chat_id, before_index, model, system_text, current_user_text) -> list:
    """Load active-branch history and trim it to the model's budget.
    Returns kept turns as [{"role", "content"}] in chronological order."""
    prior = _load_chat_history(conn, chat_id, before_index)
    if not prior:
        return []
    window = _context_window_for(model)
    budget = _history_budget(window, system_text, current_user_text)
    return _compose_history(prior, budget)


def _shape_history_openai(turns: list) -> list:
    """OpenAI / Responses message shape == canonical {role, content}."""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


def _shape_history_claude(turns: list) -> list:
    """Claude messages use the same role names (user/assistant)."""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


def _shape_history_gemini(turns: list) -> list:
    """Gemini contents: role 'assistant' -> 'model', content -> parts[].text."""
    out = []
    for t in turns:
        role = "model" if t["role"] == "assistant" else "user"
        out.append({"role": role, "parts": [{"text": t["content"]}]})
    return out


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
    _raise_for_status_verbose(response)
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


def _synthesize_claude(context: str, user_message: str, model: str, api_key: str, image_s3_keys: list | None = None) -> str:
    images = _fetch_images_as_base64(image_s3_keys) if image_s3_keys else []
    if images:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
            for mime, data in images
        ] + [{"type": "text", "text": user_message}]
    else:
        content = user_message
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
            "system": f"{_SYSTEM_PROMPT_BASE}{_JSON_SYNTHESIS_INSTRUCTION}\n\nCourse material excerpts:\n{context}",
            "messages": [{"role": "user", "content": content}],
        },
        timeout=_TIMEOUT,
    )
    _raise_for_status_verbose(response)
    return response.json()["content"][0]["text"]


def _openai_should_use_responses_api(model: str | None) -> bool:
    model_id = (model or "").strip().lower()
    return model_id.startswith(("gpt-5", "o1", "o3", "o4", "gpt-oss"))


def _openai_chat_supports_temperature(model: str | None) -> bool:
    model_id = (model or "").strip().lower()
    return not model_id.startswith(("gpt-5", "o1", "o3", "o4"))


def _openai_response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for block in payload.get("output") or []:
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("output_text"), str):
            return block["output_text"]
        for item in block.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "output_text":
                return item.get("text", "")
    return ""


def _synthesize_openai(context: str, user_message: str, model: str, api_key: str, image_s3_keys: list | None = None) -> str:
    images = _fetch_images_as_base64(image_s3_keys) if image_s3_keys else []
    system_text = f"{_SYSTEM_PROMPT_BASE}{_JSON_SYNTHESIS_INSTRUCTION}\n\nCourse material excerpts:\n{context}"

    if _openai_should_use_responses_api(model):
        if images:
            user_content = [
                {"type": "input_image", "image_url": f"data:{mime};base64,{data}"}
                for mime, data in images
            ] + [{"type": "input_text", "text": user_message}]
        else:
            user_content = user_message
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_content},
            ]},
            timeout=_TIMEOUT,
        )
        _raise_for_status_verbose(response)
        return _openai_response_text(response.json())

    if images:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}
            for mime, data in images
        ] + [{"type": "text", "text": user_message}]
    else:
        user_content = user_message
    req_body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_content},
        ],
    }
    if _openai_chat_supports_temperature(model):
        req_body["temperature"] = 0.2
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=req_body,
        timeout=_TIMEOUT,
    )
    _raise_for_status_verbose(response)
    return response.json()["choices"][0]["message"]["content"]


def _synthesize_gemini(context: str, user_message: str, model: str, api_key: str, image_s3_keys: list | None = None) -> str:
    images = _fetch_images_as_base64(image_s3_keys) if image_s3_keys else []
    if images:
        parts = [
            {"inline_data": {"mime_type": mime, "data": data}}
            for mime, data in images
        ] + [{"text": user_message}]
    else:
        parts = [{"text": user_message}]
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "system_instruction": {
                "parts": [{"text": f"{_SYSTEM_PROMPT_BASE}{_JSON_SYNTHESIS_INSTRUCTION}\n\nCourse material excerpts:\n{context}"}]
            },
            "contents": [{"parts": parts}],
        },
        timeout=_TIMEOUT,
    )
    _raise_for_status_verbose(response)
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


def _format_routing_index_block(materials: list[dict]) -> str:
    if not materials:
        return "<course_materials>\n(no materials available)\n</course_materials>"
    lines = ["<course_materials>"]
    for m in materials:
        mid = m.get("material_id", "??")
        title = m.get("title") or ""
        doc_type = m.get("doc_type") or "unknown"
        page_count = m.get("page_count")
        pages_str = f"{page_count}p" if page_count is not None else "?p"
        tags = ", ".join(m.get("tags") or []) or "none"
        summary = (m.get("summary") or "").strip().replace("\n", " ")
        if len(summary) > 240:
            summary = summary[:237] + "..."
        lines.append(
            f"[{mid}] {title} | {doc_type} | {pages_str} | tags: {tags} | summary: {summary}"
        )
        sections = m.get("sections") or []
        if sections:
            snippets = []
            for s in sections[:50]:
                start, end = s["start_page"], s["end_page"]
                page_ref = f"{start}-{end}" if end != start else str(start)
                snip = s["summary"][:80].rstrip()
                snippets.append(f"{page_ref}:{snip}")
            if snippets:
                lines.append(f"  pages: {' · '.join(snippets)}")
    lines.append("</course_materials>")
    return "\n".join(lines)


def _build_pageindex_retrieval_system_context(
    routing_block: str,
    *,
    web_search_enabled: bool,
    clarification_depth: int,
) -> str:
    system_content = (
        PAGEINDEX_SYSTEM_PROMPT
        + "\n\n"
        + routing_block
        + "\n\nUse the material IDs above when calling get_material_structure or get_page_content."
    )
    if web_search_enabled:
        system_content += (
            "\n\n**Web search**: `web_search` is also available. Use it when the question "
            "asks about something not covered in the course materials — such as current software "
            "versions, external libraries, or real-world information. Call it with a specific query."
        )
    if clarification_depth >= 2:
        system_content += (
            "\n\n**Do not ask any further clarifying questions.** Answer the user's question "
            "directly and completely using the available materials."
        )
    return system_content


def _build_pageindex_synthesis_system_context(
    evidence_text: str,
    *,
    clarification_depth: int,
) -> str:
    system_content = (
        _SYSTEM_PROMPT_BASE
        + _JSON_SYNTHESIS_INSTRUCTION
        + _PAGEINDEX_SYNTHESIS_INSTRUCTION
        + _CONVERSATION_HISTORY_NOTICE
    )
    if evidence_text.strip():
        system_content += "\n\nEvidence:\n" + evidence_text.strip()
    else:
        system_content += "\n\nEvidence:\nNo retrieved course material or web results were provided."
    if clarification_depth >= 2:
        system_content += (
            "\n\n**Do not ask any further clarifying questions.** Answer the user's question "
            "directly and completely using the available materials."
        )
    return system_content


def _format_pageindex_evidence(course_contents: list, web_contents: list) -> str:
    parts = []
    if course_contents:
        parts.append(
            "Retrieved course material:\n"
            + "\n\n---\n\n".join(str(c) for c in course_contents)
        )
    if web_contents:
        parts.append(
            "Web search results — use these to answer questions not covered by course materials:\n"
            + "\n\n---\n\n".join(str(c) for c in web_contents)
        )
    return "\n\n".join(parts)



class _ReplyStreamFilter:
    """Strip <REPLY>…</REPLY><META>…</META> wrapper from a streamed response.

    State machine:
      probing    — buffer until we confirm tagged vs. plain format
      in_reply   — emit text between <REPLY> and </REPLY>
      passthrough — model didn't use tags; emit everything directly
      done       — </REPLY> seen; drop remaining (META block)
    """

    _OPEN = "<REPLY>"
    _CLOSE = "</REPLY>"

    def __init__(self, emit):
        self._emit = emit
        self._state = "probing"
        self._buf = ""

    def feed(self, chunk: str) -> None:
        if self._state == "done":
            return
        self._buf += chunk
        if self._state == "probing":
            stripped = self._buf.lstrip()
            if stripped.startswith(self._OPEN):
                self._buf = stripped[len(self._OPEN):]
                self._state = "in_reply"
                self._drain()
            elif len(stripped) >= len(self._OPEN):
                self._state = "passthrough"
                self._emit(self._buf)
                self._buf = ""
        elif self._state == "in_reply":
            self._drain()
        else:  # passthrough
            self._emit(self._buf)
            self._buf = ""

    def _drain(self) -> None:
        idx = self._buf.find(self._CLOSE)
        if idx != -1:
            if idx > 0:
                self._emit(self._buf[:idx])
            self._buf = ""
            self._state = "done"
        else:
            safe = len(self._buf) - len(self._CLOSE) + 1
            if safe > 0:
                self._emit(self._buf[:safe])
                self._buf = self._buf[safe:]

    def flush(self) -> None:
        if self._buf and self._state != "done":
            self._emit(self._buf)
            self._buf = ""


def _filtered_on_event(on_event):
    """Wrap an on_event callback so streamed {"type":"text"} deltas pass through a
    _ReplyStreamFilter (stripping the <REPLY>…</REPLY><META>…</META> wrapper), while
    non-text events pass through untouched. Returns (wrapped_on_event, flush). Used by
    the Claude/Gemini PageIndex loops to match the OpenAI streaming behavior.
    """
    if on_event is None:
        return None, (lambda: None)
    filt = _ReplyStreamFilter(lambda t: on_event({"type": "text", "chunk": t}))

    def _evt(evt):
        if evt.get("type") == "text":
            filt.feed(evt["chunk"])
        else:
            on_event(evt)

    return _evt, filt.flush


def _convert_content_to_responses_format(content):
    """Convert a Chat Completions content value to Responses API format.

    Strings are returned as-is. Content arrays have their part types remapped:
    'image_url' → 'input_image', 'text' → 'input_text'.
    """
    if not isinstance(content, list):
        return content
    out = []
    for part in content:
        if part.get("type") == "image_url":
            url = part["image_url"] if isinstance(part["image_url"], str) else part["image_url"]["url"]
            out.append({"type": "input_image", "image_url": url})
        elif part.get("type") == "text":
            out.append({"type": "input_text", "text": part["text"]})
        else:
            out.append(part)
    return out


def _messages_to_responses_input(messages: list) -> list:
    """Convert Chat Completions messages list to Responses API input items."""
    result = []
    for msg in messages:
        role = msg.get("role")
        if role in ("system", "user"):
            result.append({"role": role, "content": _convert_content_to_responses_format(msg["content"])})
        elif role == "assistant":
            content = msg.get("content")
            if content:
                result.append({"role": "assistant", "content": content})
            for tc in msg.get("tool_calls") or []:
                tc_id = tc["id"]
                # Responses API requires item "id" to start with "fc_"; "call_id" stays as-is
                item_id = "fc_" + tc_id[5:] if tc_id.startswith("call_") else tc_id
                result.append({
                    "type": "function_call",
                    "id": item_id,
                    "call_id": tc_id,
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                })
        elif role == "tool":
            result.append({
                "type": "function_call_output",
                "call_id": msg["tool_call_id"],
                "output": msg["content"],
            })
    return result


def _tools_to_responses_format(tools: list) -> list:
    """Convert OpenAI Chat Completions tool dicts to Responses API function format."""
    result = []
    for t in tools:
        fn = t.get("function", t)
        result.append({
            "type": "function",
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        })
    return result


def _parse_responses_api_output(payload: dict) -> tuple[str, list]:
    """Extract text and tool calls from a Responses API response payload.
    Returns (text, tool_calls) where tool_calls is in Chat Completions format."""
    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for part in item.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    text_parts.append(part.get("text", ""))
        elif item.get("type") == "function_call":
            tool_calls.append({
                "id": item.get("call_id") or item.get("id", ""),
                "type": "function",
                "function": {
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments", "{}"),
                },
            })
    if not text_parts and isinstance(payload.get("output_text"), str):
        text_parts.append(payload["output_text"])
    return "".join(text_parts), tool_calls


def _pageindex_call_responses(
    api_key: str,
    model: str,
    messages: list,
    tools: list | None,
    on_event,
) -> tuple[dict, str | None]:
    """Responses API call for gpt-5+ models in the agentic loop.
    Returns the same (message_dict, finish_reason) shape as _pageindex_stream_call."""
    req_body: dict = {
        "model": model,
        "input": _messages_to_responses_input(messages),
        "max_output_tokens": _output_token_cap(model),
    }
    if tools:
        req_body["tools"] = _tools_to_responses_format(tools)
        req_body["tool_choice"] = "auto"
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=req_body,
        timeout=_TIMEOUT,
    )
    _raise_for_status_verbose(response)
    payload = response.json()
    text, tool_calls_list = _parse_responses_api_output(payload)
    if text and on_event:
        on_event({"type": "text", "chunk": text})
    message: dict = {"content": text}
    if tool_calls_list:
        message["tool_calls"] = tool_calls_list
    finish_reason = "tool_calls" if tool_calls_list else "stop"
    return message, finish_reason


def _pageindex_stream_call(
    api_key: str,
    model: str,
    messages: list,
    tools: list | None,
    on_event,
) -> tuple[dict, str | None]:
    """Stream one OpenAI call for the pageindex loop.

    Emits {"type": "text", "chunk": str} via on_event when the model generates
    text content (the final answer). Returns (message_dict, finish_reason)
    with the same shape as a non-streaming choices[0]["message"].
    """
    if _openai_should_use_responses_api(model):
        return _pageindex_call_responses(api_key, model, messages, tools, on_event)

    req_body: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "stream": True,
    }
    if tools:
        req_body["tools"] = tools
        req_body["tool_choice"] = "auto"

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=req_body,
        stream=True,
        timeout=_TIMEOUT,
    )
    _raise_for_status_verbose(response)

    content_parts: list[str] = []
    tool_calls_acc: dict[int, dict] = {}
    finish_reason: str | None = None

    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if chunk.get("error"):
            raise RuntimeError(f"OpenAI stream error: {chunk['error']}")
        choices = chunk.get("choices") or []
        if not choices:
            continue
        choice = choices[0]
        delta = choice.get("delta", {})
        fr = choice.get("finish_reason")
        if fr:
            finish_reason = fr

        if delta.get("content"):
            content_parts.append(delta["content"])
            if on_event:
                on_event({"type": "text", "chunk": delta["content"]})

        for tc in delta.get("tool_calls") or []:
            idx = tc["index"]
            if idx not in tool_calls_acc:
                tool_calls_acc[idx] = {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", ""),
                    },
                }
            else:
                if tc.get("id"):
                    tool_calls_acc[idx]["id"] = tc["id"]
                fn = tc.get("function", {})
                if fn.get("name"):
                    tool_calls_acc[idx]["function"]["name"] = fn["name"]
                tool_calls_acc[idx]["function"]["arguments"] += fn.get("arguments", "")

    tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
    message: dict = {"content": "".join(content_parts)}
    if tool_calls_list:
        message["tool_calls"] = tool_calls_list
    return message, finish_reason


def _pageindex_tool_list(web_search_enabled: bool = False) -> list:
    """Build the tool list for the PageIndex agent loop."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_material_structure",
                "description": (
                    "Get the hierarchical section/problem index for one material. "
                    "Call to see what's inside a relevant file before fetching pages."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {
                            "type": "integer",
                            "description": "Material ID from the course materials index",
                        },
                    },
                    "required": ["material_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_page_content",
                "description": (
                    "Fetch raw text of specific pages. "
                    "Use ranges like '5-7', comma lists like '3,8', or single pages like '12'. "
                    "Cite answers as 'Material X, page Y'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "integer"},
                        "pages": {
                            "type": "string",
                            "description": "Page spec: '5-7', '3,8', or '12'",
                        },
                    },
                    "required": ["material_id", "pages"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_related_materials",
                "description": (
                    "Get materials related to a specific material via the knowledge graph. "
                    "Use when initial material doesn't fully answer the question - "
                    "e.g., find the lecture behind a homework problem, or a solution for a hw."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {
                            "type": "integer",
                            "description": "Material ID to find neighbors for",
                        },
                    },
                    "required": ["material_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_generation",
                "description": (
                    "Propose a study artifact (quiz, flashcards, or report) for the user to "
                    "build from this conversation. Call this ONLY when the user explicitly asks "
                    "to create one (e.g. 'make me a quiz about X', 'turn this into flashcards'). "
                    "Do not generate the artifact yourself — this tool shows the user a card they "
                    "confirm. After calling it, write a short reply telling them the proposal is ready."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "generation_type": {
                            "type": "string",
                            "enum": ["quiz", "flashcards", "report"],
                        },
                        "title": {"type": "string", "description": "Short human title."},
                        "discussion_summary": {
                            "type": "string",
                            "description": (
                                "Concise distillation of the relevant conversation that should "
                                "ground the generation. A few sentences; this is the source content."
                            ),
                        },
                        "material_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Optional; defaults to the chat's selected materials.",
                        },
                        "params": {
                            "type": "object",
                            "description": (
                                "Type-specific generation parameters. "
                                "Quiz: {\"tf_count\":3,\"sa_count\":2,\"la_count\":1,\"mcq_count\":5}. "
                                "Flashcards: {\"card_count\":20}. "
                                "Report: {\"template_id\":\"<id>\"} where id is one of "
                                "\"study-guide\" (structured outline with key concepts), "
                                "\"briefing\" (executive summary for quick understanding), "
                                "\"summary\" (condensed overview of main points), "
                                "\"custom\" (anything else — also include \"custom_prompt\":\"<specific instruction>\"). "
                                "Choose the most fitting template; use custom only when none of the others fit."
                            ),
                        },
                    },
                    "required": ["generation_type", "title", "discussion_summary"],
                },
            },
        },
    ]
    if web_search_enabled and os.environ.get("AGENTIC_WEB_SEARCH_ENABLED", "").lower() == "true":
        tools.append({
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information to supplement course materials. Use when page content is insufficient.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                },
            },
        })
    return tools


def _dispatch_pageindex_tool(conn, name, args, course_id, grounding_refs, on_event) -> tuple[str, dict]:
    """Dispatch a single PageIndex tool call. Returns (tool-result text, extra trace metadata).
    Appends to grounding_refs and emits events as a side effect."""
    from pageindex_retrieval import get_material_structure, get_page_content

    if name == "get_material_structure":
        material_id = args.get("material_id")
        tool_result = json.dumps(
            get_material_structure(conn, material_id), indent=2
        )
    elif name == "get_page_content":
        material_id = args.get("material_id")
        pages_spec = args.get("pages", "")
        rows = get_page_content(conn, material_id, pages_spec)
        if rows:
            parts = [
                f"--- Page {row['page_number']} ---\n"
                f"{row['text_content'] or '[No text extracted]'}"
                for row in rows
            ]
            tool_result = "\n\n".join(parts)
            grounding_refs.append(f"material:{material_id}")
        else:
            tool_result = "No content found for the requested pages."
        if on_event:
            on_event(
                {
                    "type": "tool_call",
                    "tool": "get_page_content",
                    "material_id": material_id,
                    "pages": pages_spec,
                }
            )
    elif name == "get_related_materials":
        from pageindex_retrieval import get_material_relations

        material_id = args.get("material_id")
        relations = get_material_relations(conn, course_id, material_id)
        if relations:
            lines = []
            for relation in relations:
                score = relation.get("similarity_score")
                score_text = f"{score:.2f}" if score is not None else "?"
                shared_tags = ", ".join(relation.get("shared_tags") or []) or "none"
                lines.append(
                    f"  [{relation['other_material_id']}] "
                    f"{relation['relation_type']} (confidence: {score_text})"
                    f" | shared topics: {shared_tags}"
                )
            tool_result = f"Related materials for {material_id}:\n" + "\n".join(lines)
        else:
            tool_result = f"No known relations for material {material_id}."
        if on_event:
            on_event(
                {
                    "type": "tool_call",
                    "tool": "get_related_materials",
                    "material_id": material_id,
                }
            )
    elif name == "web_search":
        from tools import execute_web_search
        if on_event:
            on_event({"type": "web_search_start", "query": args.get("query", "")})
        result = execute_web_search(conn, args.get("query", ""))
        tool_result = result.get("text", "")
        urls = []
        for url_info in (result.get("meta") or {}).get("urls") or []:
            url = url_info.get("url", "")
            title = url_info.get("title") or url
            if url:
                if on_event:
                    on_event({"type": "web_url_view", "url": url, "title": title})
                grounding_refs.append(f"web:{url}\t{title}")
                urls.append({"url": url, "title": title})
        return str(tool_result), {"urls": urls} if urls else {}
    else:
        tool_result = f"Unknown tool: {name}"

    return str(tool_result), {}


def _pageindex_tools_anthropic(tools: list) -> list:
    """Convert OpenAI-format tool dicts to Anthropic format."""
    result = []
    for t in tools:
        fn = t.get("function", t)
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _pageindex_stream_call_claude(api_key, model, system, messages, tools, on_event):
    """One streaming Anthropic messages call. Returns (content_blocks, stop_reason).
    Emits {"type":"text","chunk":...} for text delta events."""
    body = {
        "model": model,
        "max_tokens": _output_token_cap(model),
        "system": system,
        "messages": messages,
        "stream": True,
    }
    if tools:
        body["tools"] = _pageindex_tools_anthropic(tools)
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        stream=True,
        timeout=_TIMEOUT,
    )
    _raise_for_status_verbose(resp)
    blocks = {}  # index -> {"type","id","name","input_json","text"}
    stop_reason = None
    for raw in resp.iter_lines():
        if not raw:
            continue
        line = raw.decode() if isinstance(raw, bytes) else raw
        if not line.startswith("data: "):
            continue
        evt = json.loads(line[6:])
        t = evt.get("type")
        if t == "content_block_start":
            cb = evt["content_block"]
            idx = evt["index"]
            blocks[idx] = {
                "type": cb["type"],
                "id": cb.get("id"),
                "name": cb.get("name"),
                "input_json": "",
                "text": "",
            }
        elif t == "content_block_delta":
            idx = evt["index"]
            d = evt.get("delta", {})
            if d.get("type") == "input_json_delta":
                blocks[idx]["input_json"] += d.get("partial_json", "")
            elif d.get("type") == "text_delta":
                blocks[idx]["text"] += d["text"]
                if on_event:
                    on_event({"type": "text", "chunk": d["text"]})
        elif t == "message_delta":
            stop_reason = evt.get("delta", {}).get("stop_reason", stop_reason)
        elif t == "error":
            raise RuntimeError(f"Anthropic stream error: {evt}")
        # ping, message_start, content_block_stop, message_stop → no-op
    ordered = [blocks[i] for i in sorted(blocks)]
    return ordered, stop_reason


def _pageindex_tools_gemini(tools: list) -> list:
    """Convert OpenAI-format tool dicts to Gemini functionDeclarations format."""
    declarations = []
    for t in tools:
        fn = t.get("function", t)
        declarations.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return [{"functionDeclarations": declarations}]


def _pageindex_stream_call_gemini(api_key, model, system, contents, tools, on_event):
    """One streaming Gemini generateContent call. Returns (parts, has_function_call).
    Emits {"type":"text","chunk":...} for text parts."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:streamGenerateContent?alt=sse&key={api_key}"
    )
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": _output_token_cap(model)},
    }
    if tools:
        body["tools"] = _pageindex_tools_gemini(tools)
    resp = requests.post(url, json=body, stream=True, timeout=_TIMEOUT)
    _raise_for_status_verbose(resp)
    all_parts = []
    has_function_call = False
    for raw in resp.iter_lines():
        if not raw:
            continue
        line = raw.decode() if isinstance(raw, bytes) else raw
        if not line.startswith("data: "):
            continue
        try:
            evt = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if evt.get("error"):
            raise RuntimeError(f"Gemini stream error: {evt['error']}")
        for candidate in evt.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                all_parts.append(part)
                if "functionCall" in part:
                    has_function_call = True
                elif "text" in part:
                    if on_event:
                        on_event({"type": "text", "chunk": part["text"]})
    return all_parts, has_function_call


def run_agent_pageindex(
    conn,
    user_message: str,
    model: str,
    api_key: str,
    chat_id: int | None,
    course_id: int | None,
    context_material_ids: list,
    on_event=None,
    provider: str = "openai",
    web_search_enabled: bool = False,
    image_s3_keys: list | None = None,
    history_before_index: int | None = None,
    clarification_depth: int = 0,
) -> tuple:
    from pageindex_retrieval import get_course_routing_index

    _validate_model_supports_images(model, image_s3_keys)

    # Image-only messages have no text query; give the retrieval model something to work with.
    if not user_message.strip() and image_s3_keys:
        user_message = "Please analyze this image and find any related course material."

    tools = _pageindex_tool_list(web_search_enabled=web_search_enabled)

    routing_materials = get_course_routing_index(
        conn, course_id, context_material_ids or None
    )
    routing_block = _format_routing_index_block(routing_materials)
    system_content = _build_pageindex_retrieval_system_context(
        routing_block,
        web_search_enabled=web_search_enabled,
        clarification_depth=clarification_depth,
    )

    history_system_content = system_content + _CONVERSATION_HISTORY_NOTICE

    _history_turns = _build_history_turns(
        conn=conn,
        chat_id=chat_id,
        before_index=history_before_index,
        model=model,
        system_text=history_system_content,
        current_user_text=user_message,
    )

    system_content = history_system_content

    # Attached images travel with the first user turn. Each provider has its own
    # multimodal content shape (mirrors _synthesize_claude/openai/gemini). Prior
    # images discussed earlier in the chat are recalled by similarity and prepended
    # so the model retains cross-turn visual context.
    current_images = _fetch_images_as_base64(image_s3_keys) if image_s3_keys else []
    recalled_images = _recall_prior_chat_images(
        conn, chat_id, user_message, exclude_s3_keys=image_s3_keys
    )
    request_images = recalled_images + current_images

    if request_images:
        openai_user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}
            for mime, data in request_images
        ] + [{"type": "text", "text": user_message}]
    else:
        openai_user_content = user_message

    current_user_message = {"role": "user", "content": openai_user_content}
    openai_history_messages = _shape_history_openai(_history_turns)
    messages = (
        [{"role": "system", "content": system_content}]
        + openai_history_messages
        + [current_user_message]
    )
    grounding_refs: list = []
    tool_trace: list = []
    final_text = ""
    proposal_emitted = False
    assistant_follow_ups: list = []
    assistant_clarifying_question = None
    assistant_reply_summary = None
    course_evidence: list[str] = []
    web_evidence: list[str] = []

    def _record_evidence(tool_name: str, tool_result: str) -> None:
        if tool_name == "get_page_content":
            course_evidence.append(str(tool_result))
        elif tool_name == "web_search":
            web_evidence.append(str(tool_result))

    # Retrieval always uses gpt-4o-mini; synthesis always uses the user-selected model.
    retrieval_model = DEFAULT_AGENTIC_MODEL

    def _retrieval_call(msgs, tls):
        """Tool-calling loop: always gpt-4o-mini, non-text events pass through."""
        def _non_text_evt(evt):
            if on_event and evt.get("type") != "text":
                on_event(evt)
        return _pageindex_stream_call(api_key, retrieval_model, msgs, tls, _non_text_evt if on_event else None)

    def _synthesis_call(msgs):
        """Final answer: user-selected model with full text streaming."""
        if on_event is None:
            return _pageindex_stream_call(api_key, model, msgs, None, None)
        filt = _ReplyStreamFilter(lambda t: on_event({"type": "text", "chunk": t}))
        def _evt(evt):
            if evt.get("type") == "text":
                filt.feed(evt["chunk"])
            else:
                on_event(evt)
        result = _pageindex_stream_call(api_key, model, msgs, None, _evt)
        filt.flush()
        return result

    def _non_text_event(evt):
        if on_event and evt.get("type") != "text":
            on_event(evt)

    if provider == "claude":
        if request_images:
            claude_user_content = [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
                for mime, data in request_images
            ] + [{"type": "text", "text": user_message}]
        else:
            claude_user_content = user_message
        claude_messages = _shape_history_claude(_history_turns) + [
            {"role": "user", "content": claude_user_content}
        ]
        for iteration in range(MAX_TOOL_ITERATIONS):
            blocks, stop_reason = _pageindex_stream_call_claude(
                api_key, model, system_content, claude_messages, tools, _non_text_event if on_event else None
            )
            tool_use_blocks = [b for b in blocks if b["type"] == "tool_use"]
            if not tool_use_blocks or stop_reason != "tool_use":
                break
            # Append assistant turn
            assistant_content = []
            for b in blocks:
                if b["type"] == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": b["id"],
                        "name": b["name"],
                        "input": json.loads(b["input_json"]) if b["input_json"] else {},
                    })
                elif b["type"] == "text" and b["text"]:
                    assistant_content.append({"type": "text", "text": b["text"]})
            claude_messages.append({"role": "assistant", "content": assistant_content})
            # Dispatch each tool call and collect results
            tool_results = []
            for b in tool_use_blocks:
                args = json.loads(b["input_json"]) if b["input_json"] else {}
                _tmeta = {}
                if b["name"] == "propose_generation":
                    proposal = {
                        "type": "generation_proposal",
                        "generation_type": args.get("generation_type") or "",
                        "title": args.get("title") or "",
                        "discussion_summary": args.get("discussion_summary") or "",
                        "material_ids": args.get("material_ids") or list(context_material_ids or []),
                        "params": args.get("params") or {},
                    }
                    if on_event:
                        on_event(proposal)
                    proposal_emitted = True
                    result_text = ""
                else:
                    result_text, _tmeta = _dispatch_pageindex_tool(
                        conn=conn,
                        name=b["name"],
                        args=args,
                        course_id=course_id,
                        grounding_refs=grounding_refs,
                        on_event=on_event,
                    )
                    _record_evidence(b["name"], result_text)
                _te = {"tool": b["name"], "args": args, "iteration": iteration}
                if _tmeta.get("urls"):
                    _te["urls"] = _tmeta["urls"]
                tool_trace.append(_te)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": b["id"],
                    "content": result_text,
                })
            if proposal_emitted:
                final_text = ""
                break
            claude_messages.append({"role": "user", "content": tool_results})

        if not proposal_emitted:
            evt_cb, flush = _filtered_on_event(on_event)
            synthesis_system_content = _build_pageindex_synthesis_system_context(
                _format_pageindex_evidence(course_evidence, web_evidence),
                clarification_depth=clarification_depth,
            )
            synthesis_messages = _shape_history_claude(_history_turns) + [
                {"role": "user", "content": claude_user_content}
            ]
            blocks, _ = _pageindex_stream_call_claude(
                api_key, model, synthesis_system_content, synthesis_messages, [], evt_cb
            )
            flush()
            full_text = "".join(b["text"] for b in blocks if b["type"] == "text")
            raw_final = full_text.strip() or "I could not find relevant content in the course materials."
            (
                reply_body,
                assistant_reply_summary,
                assistant_follow_ups,
                assistant_clarifying_question,
            ) = _parse_synthesis_json(raw_final)
            final_text = reply_body if (reply_body or "").strip() else raw_final
            tool_trace.append({"phase": "synthesis"})

        if not final_text and not proposal_emitted:
            final_text = "I could not find relevant content in the course materials."

        return (
            final_text,
            grounding_refs,
            tool_trace,
            {
                "intent_type": "pageindex",
                "verifier_passed": True,
                "repair_invoked": False,
                "history_token_estimate": sum(_estimate_tokens(t["content"]) for t in _history_turns),
                "history_turn_count": len(_history_turns),
            },
            assistant_reply_summary,
            assistant_follow_ups or [],
            assistant_clarifying_question,
        )

    if provider == "gemini":
        if request_images:
            gemini_user_parts = [
                {"inline_data": {"mime_type": mime, "data": data}}
                for mime, data in request_images
            ] + [{"text": user_message}]
        else:
            gemini_user_parts = [{"text": user_message}]
        contents = _shape_history_gemini(_history_turns) + [{"role": "user", "parts": gemini_user_parts}]
        for iteration in range(MAX_TOOL_ITERATIONS):
            parts, has_fc = _pageindex_stream_call_gemini(
                api_key, model, system_content, contents, tools, _non_text_event if on_event else None
            )
            if not has_fc:
                break
            # Append model turn
            contents.append({"role": "model", "parts": parts})
            # Dispatch function calls and collect responses
            fn_responses = []
            for p in parts:
                if "functionCall" in p:
                    fc = p["functionCall"]
                    args = fc.get("args", {})
                    _tmeta = {}
                    if fc["name"] == "propose_generation":
                        proposal = {
                            "type": "generation_proposal",
                            "generation_type": args.get("generation_type") or "",
                            "title": args.get("title") or "",
                            "discussion_summary": args.get("discussion_summary") or "",
                            "material_ids": args.get("material_ids") or list(context_material_ids or []),
                            "params": args.get("params") or {},
                        }
                        if on_event:
                            on_event(proposal)
                        proposal_emitted = True
                        result_text = ""
                    else:
                        result_text, _tmeta = _dispatch_pageindex_tool(
                            conn=conn,
                            name=fc["name"],
                            args=args,
                            course_id=course_id,
                            grounding_refs=grounding_refs,
                            on_event=on_event,
                        )
                        _record_evidence(fc["name"], result_text)
                    _te = {"tool": fc["name"], "args": args, "iteration": iteration}
                    if _tmeta.get("urls"):
                        _te["urls"] = _tmeta["urls"]
                    tool_trace.append(_te)
                    function_response = {
                        "name": fc["name"],
                        "response": {"content": result_text},
                    }
                    if fc.get("id"):
                        function_response["id"] = fc["id"]
                    fn_responses.append({"functionResponse": function_response})
            if proposal_emitted:
                final_text = ""
                break
            contents.append({"role": "user", "parts": fn_responses})

        if not proposal_emitted:
            evt_cb, flush = _filtered_on_event(on_event)
            synthesis_system_content = _build_pageindex_synthesis_system_context(
                _format_pageindex_evidence(course_evidence, web_evidence),
                clarification_depth=clarification_depth,
            )
            synthesis_contents = _shape_history_gemini(_history_turns) + [
                {"role": "user", "parts": gemini_user_parts}
            ]
            parts, _ = _pageindex_stream_call_gemini(
                api_key, model, synthesis_system_content, synthesis_contents, [], evt_cb
            )
            flush()
            full_text = "".join(p.get("text", "") for p in parts if "text" in p)
            raw_final = full_text.strip() or "I could not find relevant content in the course materials."
            (
                reply_body,
                assistant_reply_summary,
                assistant_follow_ups,
                assistant_clarifying_question,
            ) = _parse_synthesis_json(raw_final)
            final_text = reply_body if (reply_body or "").strip() else raw_final
            tool_trace.append({"phase": "synthesis"})

        if not final_text and not proposal_emitted:
            final_text = "I could not find relevant content in the course materials."

        return (
            final_text,
            grounding_refs,
            tool_trace,
            {
                "intent_type": "pageindex",
                "verifier_passed": True,
                "repair_invoked": False,
                "history_token_estimate": sum(_estimate_tokens(t["content"]) for t in _history_turns),
                "history_turn_count": len(_history_turns),
            },
            assistant_reply_summary,
            assistant_follow_ups or [],
            assistant_clarifying_question,
        )

    for iteration in range(MAX_TOOL_ITERATIONS):
        started = time.time()
        message, finish_reason = _retrieval_call(messages, tools)
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            tool_trace.append(
                {
                    "iteration": iteration,
                    "finish_reason": finish_reason,
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

            _tmeta = {}
            if name == "propose_generation":
                proposal = {
                    "type": "generation_proposal",
                    "generation_type": args.get("generation_type") or "",
                    "title": args.get("title") or "",
                    "discussion_summary": args.get("discussion_summary") or "",
                    "material_ids": args.get("material_ids") or list(context_material_ids or []),
                    "params": args.get("params") or {},
                }
                if on_event:
                    on_event(proposal)
                proposal_emitted = True
                tool_result = ""
            else:
                tool_result, _tmeta = _dispatch_pageindex_tool(
                    conn=conn,
                    name=name,
                    args=args,
                    course_id=course_id,
                    grounding_refs=grounding_refs,
                    on_event=on_event,
                )
                _record_evidence(name, tool_result)

            _te = {"tool": name, "args": args, "iteration": iteration}
            if _tmeta.get("urls"):
                _te["urls"] = _tmeta["urls"]
            tool_trace.append(_te)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": name,
                    "content": str(tool_result),
                }
            )

        if proposal_emitted:
            break

    # Synthesis: always the user-selected model, always a separate call from retrieval.
    if proposal_emitted:
        return (
            "",
            grounding_refs,
            tool_trace,
            {
                "intent_type": "pageindex",
                "verifier_passed": True,
                "repair_invoked": False,
                "history_token_estimate": sum(_estimate_tokens(t["content"]) for t in _history_turns),
                "history_turn_count": len(_history_turns),
            },
            None,
            [],
            None,
        )
    started = time.time()
    evidence_text = _format_pageindex_evidence(course_evidence, web_evidence)
    synthesis_system_content = _build_pageindex_synthesis_system_context(
        evidence_text,
        clarification_depth=clarification_depth,
    )
    synthesis_msgs = [
        {"role": "system", "content": synthesis_system_content},
    ] + openai_history_messages + [current_user_message]
    synthesis_message, _ = _synthesis_call(synthesis_msgs)
    raw_final = (
        _message_text(synthesis_message).strip()
        or "I could not find relevant content in the course materials."
    )
    (
        reply_body,
        assistant_reply_summary,
        assistant_follow_ups,
        assistant_clarifying_question,
    ) = _parse_synthesis_json(raw_final)
    final_text = reply_body if (reply_body or "").strip() else raw_final
    import re as _re
    # Always strip [WN] markers; also strip plain [N] markers when web search was used
    # (model may renumber web results as [1], [2] without page chunks to back them up)
    has_web_refs = any(r.startswith("web:") for r in grounding_refs)
    has_page_refs = any(r.startswith("material:") for r in grounding_refs)
    if has_web_refs and not has_page_refs:
        final_text = _re.sub(r'\s*\[\d+\]', '', final_text or "").strip()
    final_text = _re.sub(r'\s*\[W\d+\]', '', final_text or "").strip()
    tool_trace.append(
        {"phase": "synthesis", "latency_ms": int((time.time() - started) * 1000)}
    )

    return (
        final_text or "I could not find relevant content in the course materials.",
        grounding_refs,
        tool_trace,
        {
            "intent_type": "pageindex",
            "verifier_passed": True,
            "repair_invoked": False,
            "history_token_estimate": sum(_estimate_tokens(t["content"]) for t in _history_turns),
            "history_turn_count": len(_history_turns),
        },
        assistant_reply_summary,
        assistant_follow_ups or [],
        assistant_clarifying_question,
    )


_TITLE_MODEL = "gpt-4o-mini"
_TITLE_URL = "https://api.openai.com/v1/chat/completions"


def suggest_chat_title(
    conn,
    user_id: int,
    chat_id: int,
    current_title: str,
) -> str | None:
    """
    Ask GPT-4o-mini to suggest a refined title for the chat based on recent messages.
    Returns a title string (max 80 chars) or None on any failure.
    """
    try:
        api_key = _get_api_key(conn, user_id, "openai")
    except Exception:
        return None

    if not api_key:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE chat_id = %s
              AND is_deleted = FALSE
            ORDER BY message_index DESC
            LIMIT 6
            """,
            (chat_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception:
        return None

    turns = [
        {"role": row["role"], "content": (row["content"] or "")[:300]}
        for row in reversed(rows)
    ]

    system_prompt = (
        "You suggest short chat titles. Given the current title and recent conversation turns, "
        "return a refined title that better reflects the conversation topic. "
        "Rules: max 80 characters, no quotes, no markdown, minimal alteration from the current "
        "title unless the topic has clearly shifted. Return strict JSON: {\"title\": \"...\"}."
    )
    payload = {
        "current_title": current_title or "New Chat",
        "turns": turns,
    }

    try:
        resp = requests.post(
            _TITLE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _TITLE_MODEL,
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=8,
        )
        _raise_for_status_verbose(resp)
        parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
        title = str(parsed.get("title", "")).strip()
        if title:
            return title[:80]
    except Exception:
        pass

    return None


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
    image_s3_keys: list | None = None,
    web_search_enabled: bool = False,
    history_before_index: int | None = None,
    clarification_depth: int = 0,
) -> tuple:
    """
    Synthesize an LLM response using the user's chosen provider and model.

    Returns:
        (synthesized_text: str, chunk_ids_or_grounding_refs, metadata_dict, tool_trace_list, summary_or_none)

    Raises:
        ValueError: if no API key is stored for the provider, or unsupported provider.
        requests.HTTPError: if the provider API returns a non-2xx response.
    """
    ai_provider, ai_model = _resolve_provider_model(ai_provider, ai_model)
    if ai_provider not in _PROVIDERS:
        raise ValueError(f"Unsupported provider: {ai_provider}")

    # PageIndex is the only retrieval path. `chunks` and `force_context_only`
    # remain in the signature for caller compatibility but are no longer used.
    material_scope = context_material_ids if isinstance(context_material_ids, list) else []
    agentic_api_key = _get_api_key(conn, user_id, ai_provider)
    pageindex_course_id = None
    if context_material_ids:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT course_id FROM materials WHERE id = %s",
            (context_material_ids[0],),
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            pageindex_course_id = row["course_id"]
    if pageindex_course_id is None and chat_id is not None:
        cursor = conn.cursor()
        cursor.execute("SELECT course_id FROM chats WHERE id = %s", (chat_id,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            pageindex_course_id = row["course_id"]
    (
        text,
        grounding_refs,
        tool_trace,
        metadata,
        msg_summary,
        follow_ups,
        clarifying_question,
    ) = run_agent_pageindex(
        conn=conn,
        user_message=user_message,
        model=ai_model,
        api_key=agentic_api_key,
        provider=ai_provider,
        chat_id=chat_id,
        course_id=pageindex_course_id,
        context_material_ids=material_scope,
        on_event=on_event,
        web_search_enabled=web_search_enabled,
        image_s3_keys=image_s3_keys,
        history_before_index=history_before_index,
        clarification_depth=clarification_depth,
    )
    return (
        text,
        grounding_refs,
        metadata,
        tool_trace,
        msg_summary,
        follow_ups,
        clarifying_question,
    )
