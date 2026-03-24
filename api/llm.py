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
import time

import requests
from uuid import UUID

try:
    from .crypto_utils import decrypt_api_key
except ImportError:
    from crypto_utils import decrypt_api_key
try:
    from .tools import execute_search_materials, pull_grounding_context
except ImportError:
    from tools import execute_search_materials, pull_grounding_context

SYSTEM_PROMPT = (
    "You are a helpful course assistant. Answer the user's question using the "
    "provided course material excerpts.\n\n"
    "**Citations**: Cite sources using isolated bracket notation — [1] for one "
    "source, [1], [2] for two, [1], [2], [3] for three, and so on. Always place "
    "a comma and space between multiple citations. Only use numbers that correspond "
    "to the excerpts provided. Never write adjacent brackets without separation "
    "(e.g. never write [1][2]).\n\n"
    "**Formatting**: Use rich Markdown to make your response clear and readable:\n"
    "- **Bold** or *italic* for key terms and emphasis.\n"
    "- Fenced code blocks (```language\\n...\\n```) for code, pseudocode, and "
    "command-line examples — specify the language (python, js, bash, etc.) where applicable.\n"
    "- `inline code` for function names, variable names, file paths, and short "
    "code references inline in prose.\n"
    "- Block quotes (> ...) for verbatim quotations from readings or source material.\n"
    "- Numbered or bulleted lists for steps, enumerations, and comparisons.\n"
    "- Headers (## or ###) to organise longer multi-section responses.\n\n"
    "**Math**: Wrap all mathematical expressions in LaTeX delimiters: "
    "$...$ for inline math and $$...$$ for display/block equations.\n\n"
    "If the materials don't contain enough information to answer fully, say so clearly."
)

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
            "system": f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}",
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
                    "content": f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}",
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
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}"}]
            },
            "contents": [{"parts": [{"text": user_message}]}],
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def run_agent_openai(
    conn,
    user_message: str,
    model: str,
    api_key: str,
    chunks: list,
    chat_id: int | None,
    context_material_ids: list,
) -> tuple[str, list, list]:
    grounding_refs = _dedupe_preserve_order(
        [_json_safe_chunk_id(c.get("id")) for c in chunks if c.get("id") is not None]
    )
    grounding_text = ""
    if chat_id is not None:
        pulled = pull_grounding_context(conn, chat_id, user_message)
        grounding_text = pulled.get("text", "")
        grounding_refs.extend(pulled.get("chunk_ids", []))
        grounding_refs = _dedupe_preserve_order(grounding_refs)

    messages = [
        {"role": "system", "content": _build_system_context(chunks, grounding_text)},
        {"role": "user", "content": user_message},
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

    max_iterations = _safe_int_env("AGENTIC_MAX_ITERATIONS", MAX_TOOL_ITERATIONS, 1, 8)
    tool_trace = []
    final_text = ""

    for iteration in range(1, max_iterations + 1):
        started = time.time()
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

            if name == "search_materials":
                result = execute_search_materials(
                    conn=conn,
                    query=args.get("query", ""),
                    material_ids=context_material_ids,
                    top_k=args.get("top_k", 8),
                )
            else:
                result = {
                    "text": f"Unsupported tool: {name}",
                    "chunk_ids": [],
                    "meta": {"tool": name or "unknown", "error": "unsupported_tool"},
                }

            grounding_refs.extend(result.get("chunk_ids", []))
            grounding_refs = _dedupe_preserve_order(grounding_refs)
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
            }
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
    return final_text, grounding_refs, tool_trace


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

    api_key = _get_api_key(conn, user_id, ai_provider)
    material_scope = context_material_ids if isinstance(context_material_ids, list) else []
    use_agentic = (
        _is_enabled("AGENTIC_LOOP_ENABLED", default=True)
        and ai_provider == "openai"
        and ai_model == DEFAULT_AGENTIC_MODEL
    )

    if use_agentic:
        text, grounding_refs, tool_trace = run_agent_openai(
            conn=conn,
            user_message=user_message,
            model=ai_model,
            api_key=api_key,
            chunks=chunks,
            chat_id=chat_id,
            context_material_ids=material_scope,
        )
        logger.info(
            "agentic_loop_trace",
            extra={
                "chat_id": chat_id,
                "provider": ai_provider,
                "model": ai_model,
                "iterations": len([t for t in tool_trace if "tool_calls" in t]),
                "tool_calls": len([t for t in tool_trace if t.get("tool")]),
            },
        )
        return text, grounding_refs

    context = _format_context(chunks)
    fn = _PROVIDERS[ai_provider]
    text = fn(context, user_message, ai_model, api_key)
    chunk_ids = [
        _json_safe_chunk_id(c.get("id"))
        for c in chunks
        if c.get("id") is not None
    ]
    return text, chunk_ids
