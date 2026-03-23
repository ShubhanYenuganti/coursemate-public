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
import requests

try:
    from .crypto_utils import decrypt_api_key
except ImportError:
    from crypto_utils import decrypt_api_key

SYSTEM_PROMPT = (
    "You are a helpful course assistant. Answer the user's question using the "
    "provided course material excerpts. Cite excerpt numbers (e.g. [1]) when "
    "referencing specific content. If the materials don't contain enough "
    "information to answer fully, say so clearly."
)

_TIMEOUT = 60  # seconds


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
        header = f"[{i}] ({c.get('source_type', c['chunk_type'])}"
        if c.get('section_title'):
            header += f", section: {c['section_title']}"
        if c.get('page_number'):
            header += f", page {c['page_number']}"
        if c.get('week'):
            header += f", week {c['week']}"
        header += f", similarity={c['similarity']:.3f})"
        body = c['chunk_text']
        if c.get('linked_context'):
            body += f"\n\n[Related context: {c['linked_context']['chunk_text']}]"
        parts.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(parts)


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


_PROVIDERS = {
    "claude": _synthesize_claude,
    "openai": _synthesize_openai,
    "gemini": _synthesize_gemini,
}


def synthesize(
    conn,
    user_id: int,
    ai_provider: str,
    ai_model: str,
    user_message: str,
    chunks: list,
) -> tuple:
    """
    Synthesize an LLM response using the user's chosen provider and model.

    Returns:
        (synthesized_text: str, chunk_ids_used: list[int])

    Raises:
        ValueError: if no API key is stored for the provider, or unsupported provider.
        requests.HTTPError: if the provider API returns a non-2xx response.
    """
    if ai_provider not in _PROVIDERS:
        raise ValueError(f"Unsupported provider: {ai_provider}")

    api_key = _get_api_key(conn, user_id, ai_provider)
    context = _format_context(chunks)
    fn = _PROVIDERS[ai_provider]
    text = fn(context, user_message, ai_model, api_key)
    chunk_ids = [c["id"] for c in chunks]
    return text, chunk_ids
