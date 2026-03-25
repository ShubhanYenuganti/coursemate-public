"""
AWS Lambda handler -- flashcards_generate

Triggered by SQS messages from the API enqueue step.
Each message body is expected to include:
  {"generation_id": <int>, "generated_by": <int>}
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
ALLOWED_DEPTHS = {"brief", "moderate", "in-depth"}


def _get_fernet() -> Fernet:
    raw = os.environ.get("API_KEY_ENCRYPTION_KEY")
    if not raw:
        raise ValueError("API_KEY_ENCRYPTION_KEY environment variable is not set")
    return Fernet(raw.encode())


def decrypt_api_key(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt API key -- ciphertext may be corrupted "
            "or encrypted with a different key"
        )


def _normalize_depth(value: str) -> str:
    depth = (value or "moderate").strip().lower()
    if depth in ("in_depth", "indepth"):
        depth = "in-depth"
    return depth if depth in ALLOWED_DEPTHS else "moderate"


def _fetch_material_context(conn, material_ids: list) -> str:
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
        if total + len(content) > CONTEXT_CHAR_BUDGET:
            remaining = CONTEXT_CHAR_BUDGET - total
            if remaining > 200:
                parts.append(content[:remaining])
            break
        parts.append(content)
        total += len(content)
    return "\n\n---\n\n".join(parts)


def _build_flashcards_prompt(topic: str, card_count: int, depth: str, material_context: str):
    system = (
        "You are a flashcards generator. Return valid JSON only. No markdown fences, "
        "no preamble. Your full output must be json.loads() parseable.\n\n"
        "Output format:\n"
        '{"title":"Deck title","cards":[\n'
        '  {"front":"...","back":"...","hint":"..."}\n'
        "]}\n\n"
        "Rules:\n"
        "- Generate exactly the requested number of cards\n"
        "- Keep front concise and unambiguous\n"
        "- Back should match requested depth and stay factual to provided material\n"
        "- hint is optional and brief\n"
        "- Base all content strictly on provided material"
    )
    topic_line = f"topic: {topic}" if (topic or "").strip() else "the provided course material"
    user = (
        f"Course materials:\n{material_context}\n\n"
        f"Generate flashcards for {topic_line}.\n"
        f"Requested card count: {card_count}\n"
        f"Requested depth: {depth}"
    )
    return system, user


def _parse_model_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Model returned empty content; expected JSON object")

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
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError("Could not parse model JSON output")


def _call_openai_json(api_key: str, model_id: str, system: str, user: str) -> dict:
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
            payload = resp.json()
            detail = payload.get("error", {}).get("message") or payload.get("error") or ""
        except Exception:
            detail = resp.text[:500]
        raise requests.HTTPError(
            f"OpenAI chat.completions failed ({resp.status_code}): {detail}",
            response=resp,
        )
    raw = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
    return _parse_model_json(raw)


def _call_claude_json(api_key: str, model_id: str, system: str, user: str) -> dict:
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
    payload = resp.json()
    content_blocks = payload.get("content") or []
    text_parts = [b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
    raw = "\n".join([p for p in text_parts if p]).strip()
    return _parse_model_json(raw)


def _call_gemini_json(api_key: str, model_id: str, system: str, user: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    resp = requests.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    payload = resp.json()
    candidates = payload.get("candidates") or []
    parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
    raw = "\n".join([str(p.get("text", "")) for p in parts if isinstance(p, dict) and p.get("text")]).strip()
    return _parse_model_json(raw)


def _call_llm_json(provider: str, api_key: str, model_id: str, system: str, user: str) -> dict:
    if provider == "openai":
        return _call_openai_json(api_key, model_id, system, user)
    if provider == "claude":
        return _call_claude_json(api_key, model_id, system, user)
    if provider == "gemini":
        return _call_gemini_json(api_key, model_id, system, user)
    raise ValueError(f"Unsupported provider: {provider}")


def _normalize_card(raw: dict, idx: int) -> dict:
    front = str(
        raw.get("front")
        or raw.get("term")
        or raw.get("question")
        or raw.get("prompt")
        or ""
    ).strip()
    back = str(
        raw.get("back")
        or raw.get("definition")
        or raw.get("answer")
        or raw.get("explanation")
        or ""
    ).strip()
    hint = str(raw.get("hint") or raw.get("clue") or "").strip()

    if not front:
        raise ValueError(f"Card {idx}: missing front text")
    if not back:
        raise ValueError(f"Card {idx}: missing back text")

    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "front_text": front,
        "back_text": back,
        "hint_text": hint or None,
        "metadata": metadata,
    }


def _validate_and_normalize_cards(raw_payload: dict, expected_count: int) -> tuple[str, list]:
    title = str(raw_payload.get("title") or "Flashcards").strip() or "Flashcards"

    cards = raw_payload.get("cards")
    if cards is None and isinstance(raw_payload.get("flashcards"), list):
        cards = raw_payload.get("flashcards")
    if cards is None and isinstance(raw_payload.get("items"), list):
        cards = raw_payload.get("items")

    if not isinstance(cards, list):
        raise ValueError("Model output is missing cards array")

    normalized = []
    for idx, card in enumerate(cards):
        if not isinstance(card, dict):
            raise ValueError(f"Card {idx}: expected object")
        normalized.append(_normalize_card(card, idx))

    if len(normalized) < expected_count:
        raise ValueError(
            f"Model returned too few cards ({len(normalized)}), expected at least {expected_count}"
        )
    if len(normalized) > expected_count:
        normalized = normalized[:expected_count]

    return title, normalized


def _persist_cards(conn, generation_id: int, cards: list):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM flashcard_cards WHERE generation_id=%s", (generation_id,))
    for idx, card in enumerate(cards):
        cursor.execute(
            """
            INSERT INTO flashcard_cards
                (generation_id, card_index, front_text, back_text, hint_text, metadata)
            VALUES
                (%s, %s, %s, %s, %s, %s)
            """,
            (
                generation_id,
                idx,
                card["front_text"],
                card["back_text"],
                card["hint_text"],
                json.dumps(card["metadata"]),
            ),
        )
    cursor.close()


def _mark_generation_failed(generation_id: int, error: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE flashcard_generations SET status='failed', error=%s WHERE id=%s",
            ((error or "")[:500], generation_id),
        )
        cursor.close()


def _process_generation(generation_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM flashcard_generations WHERE id=%s FOR UPDATE",
            (generation_id,),
        )
        gen = cursor.fetchone()
        if not gen:
            cursor.close()
            return

        if gen["status"] != "queued":
            cursor.close()
            return

        cursor.execute(
            "UPDATE flashcard_generations SET status='generating', error=NULL WHERE id=%s",
            (generation_id,),
        )

        provider = gen.get("provider") or "openai"
        model_id = gen.get("model_id") or "gpt-4o-mini"
        user_id = gen["generated_by"]
        topic = str(gen.get("topic") or "").strip()
        card_count = int(gen.get("card_count") or 20)
        depth = _normalize_depth(gen.get("depth") or "moderate")
        material_ids = gen.get("selected_material_ids") or []
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
            raise ValueError(f"No {provider} API key configured for generation user")
        api_key = decrypt_api_key(key_row["encrypted_key"])

        material_context = _fetch_material_context(conn, material_ids)
        cursor.close()

    system, user_prompt = _build_flashcards_prompt(topic, card_count, depth, material_context)
    raw = _call_llm_json(provider, api_key, model_id, system, user_prompt)
    title, cards = _validate_and_normalize_cards(raw, card_count)

    with get_db() as conn:
        _persist_cards(conn, generation_id, cards)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE flashcard_generations SET status='ready', title=%s, error=NULL WHERE id=%s",
            (title, generation_id),
        )
        cursor.close()


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
            _mark_generation_failed(generation_id, str(exc))
            raise

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
