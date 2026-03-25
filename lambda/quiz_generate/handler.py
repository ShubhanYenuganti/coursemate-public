"""
AWS Lambda handler — quiz_generate

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

TYPE_ALIASES = {
    'multiple_choice': 'mcq',
    'multiple-choice': 'mcq',
    'true_false': 'tf',
    'true-false': 'tf',
    'short_answer': 'sa',
    'short-answer': 'sa',
    'long_answer': 'la',
    'long-answer': 'la',
}
TF_TRUE_VALUES = {'true', 'yes', '1', 't', 'correct'}
TF_FALSE_VALUES = {'false', 'no', '0', 'f', 'incorrect', 'wrong'}


def _get_fernet() -> Fernet:
    raw = os.environ.get('API_KEY_ENCRYPTION_KEY')
    if not raw:
        raise ValueError("API_KEY_ENCRYPTION_KEY environment variable is not set")
    return Fernet(raw.encode())


def decrypt_api_key(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt API key — ciphertext may be corrupted "
            "or encrypted with a different key"
        )


def _normalize_question_type(t: str) -> str:
    t = (t or '').lower().strip()
    return TYPE_ALIASES.get(t, t)


def _validate_and_normalize_questions(questions: list) -> list:
    result = []
    for i, q in enumerate(questions):
        q_type = _normalize_question_type(q.get('type', ''))
        if q_type not in ('mcq', 'tf', 'sa', 'la'):
            raise ValueError(f"Question {i}: unknown type '{q.get('type')}'")

        text = (q.get('question') or q.get('text') or '').strip()
        if not text:
            raise ValueError(f"Question {i}: missing question text")

        answer = str(q.get('answer') or '').strip()
        options = q.get('options') or []
        explanation = str(q.get('explanation') or '').strip()

        if q_type == 'mcq':
            if len(options) < 2:
                raise ValueError(f"Question {i}: MCQ needs at least 2 options, got {len(options)}")
            str_options = [str(o).strip() for o in options]
            if not answer:
                raise ValueError(f"Question {i}: MCQ missing answer")
            if answer not in str_options:
                try:
                    idx = int(answer)
                    answer = str_options[idx]
                except (ValueError, IndexError):
                    pass
            options = str_options

        if q_type == 'tf':
            norm = answer.lower()
            if norm in TF_TRUE_VALUES:
                answer = 'True'
            elif norm in TF_FALSE_VALUES:
                answer = 'False'
            else:
                answer = 'True'

        result.append({
            'type': q_type,
            'question': text,
            'options': options if q_type == 'mcq' else None,
            'answer': answer,
            'explanation': explanation,
        })
    return result


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
        content = row['content'] or ''
        if total + len(content) > CONTEXT_CHAR_BUDGET:
            remaining = CONTEXT_CHAR_BUDGET - total
            if remaining > 200:
                parts.append(content[:remaining])
            break
        parts.append(content)
        total += len(content)
    return '\n\n---\n\n'.join(parts)


def _build_quiz_prompt(topic: str, tf_count: int, sa_count: int, la_count: int,
                       mcq_count: int, mcq_options: int, material_context: str):
    system = (
        "You are a quiz generator. Respond with valid JSON ONLY -- no markdown fences, "
        "no explanation, no preamble. Your entire response must be parseable by json.loads().\n\n"
        "Output format:\n"
        '{"title": "Quiz title", "questions": [\n'
        '  {"type": "mcq", "question": "...", "options": ["A","B","C","D"], "answer": "A", "explanation": "..."},\n'
        '  {"type": "tf", "question": "...", "answer": "True", "explanation": "..."},\n'
        '  {"type": "sa", "question": "...", "answer": "...", "explanation": "..."},\n'
        '  {"type": "la", "question": "...", "answer": "...", "explanation": "..."}\n'
        "]}\n\n"
        "Rules:\n"
        "- MCQ: options must be distinct strings; answer must exactly match one option text\n"
        "- TF: answer must be exactly 'True' or 'False'\n"
        "- Generate exactly the count requested for each type\n"
        "- Base all questions strictly on the provided course material"
    )
    topic_line = f"the topic: **{topic}**" if topic.strip() else "the course material provided"
    user = (
        f"Course materials:\n{material_context}\n\n"
        f"Generate a quiz on {topic_line}.\n\n"
        f"Required counts:\n"
        f"- Multiple choice (mcq): {mcq_count} questions, {mcq_options} options each\n"
        f"- True/False (tf): {tf_count} questions\n"
        f"- Short answer (sa): {sa_count} questions\n"
        f"- Long answer (la): {la_count} questions"
    )
    return system, user


def _call_openai_json(api_key: str, model_id: str, system: str, user: str) -> dict:
    resp = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': model_id,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
        },
        timeout=TIMEOUT_SECONDS,
    )
    if not resp.ok:
        detail = ''
        try:
            payload = resp.json()
            detail = payload.get('error', {}).get('message') or payload.get('error') or ''
        except Exception:
            detail = resp.text[:500]
        raise requests.HTTPError(
            f"OpenAI chat.completions failed ({resp.status_code}): {detail}",
            response=resp,
        )
    raw = (resp.json().get('choices') or [{}])[0].get('message', {}).get('content', '')
    return _parse_model_json(raw)


def _call_claude_json(api_key: str, model_id: str, system: str, user: str) -> dict:
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': model_id,
            'max_tokens': 4096,
            'system': system,
            'messages': [{'role': 'user', 'content': user}],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    payload = resp.json()
    content_blocks = payload.get('content') or []
    text_parts = [b.get('text', '') for b in content_blocks if isinstance(b, dict) and b.get('type') == 'text']
    raw = '\n'.join([p for p in text_parts if p]).strip()
    return _parse_model_json(raw)


def _call_gemini_json(api_key: str, model_id: str, system: str, user: str) -> dict:
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent'
    resp = requests.post(
        url,
        headers={
            'x-goog-api-key': api_key,
            'Content-Type': 'application/json',
        },
        json={
            'system_instruction': {'parts': [{'text': system}]},
            'contents': [{'parts': [{'text': user}]}],
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    payload = resp.json()
    candidates = payload.get('candidates') or []
    parts = (((candidates[0] if candidates else {}).get('content') or {}).get('parts') or [])
    raw = '\n'.join([str(p.get('text', '')) for p in parts if isinstance(p, dict) and p.get('text')]).strip()
    return _parse_model_json(raw)


def _parse_model_json(raw: str) -> dict:
    """Best-effort parser for model output expected to contain one JSON object."""
    raw = (raw or '').strip()
    if not raw:
        raise ValueError("Model returned empty content; expected JSON object")

    # 1) Direct parse
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2) Remove fenced code blocks if present
    if raw.startswith('```'):
        stripped = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        try:
            return json.loads(stripped)
        except Exception:
            raw = stripped

    # 3) Extract first object-like block
    match = re.search(r'\{.*\}', raw, flags=re.DOTALL)
    if match:
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError("Could not parse model JSON output")


def _call_llm_json(provider: str, api_key: str, model_id: str, system: str, user: str) -> dict:
    if provider == 'openai':
        return _call_openai_json(api_key, model_id, system, user)
    if provider == 'claude':
        return _call_claude_json(api_key, model_id, system, user)
    if provider == 'gemini':
        return _call_gemini_json(api_key, model_id, system, user)
    raise ValueError(f"Unsupported provider: {provider}")


def _persist_questions(conn, generation_id: int, questions: list):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quiz_questions WHERE generation_id=%s", (generation_id,))
    for idx, q in enumerate(questions):
        cursor.execute(
            """
            INSERT INTO quiz_questions
                (generation_id, question_index, question_type, question_text, correct_answer_text, explanation)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (generation_id, idx, q['type'], q['question'], q['answer'], q['explanation']),
        )
        q_id = cursor.fetchone()['id']
        for opt_idx, opt_text in enumerate(q['options'] or []):
            cursor.execute(
                """
                INSERT INTO quiz_question_options (question_id, option_index, option_text, is_correct)
                VALUES (%s, %s, %s, %s)
                """,
                (q_id, opt_idx, opt_text, opt_text == q['answer']),
            )
    cursor.close()


def _mark_generation_failed(generation_id: int, error: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE quiz_generations SET status='failed', error=%s WHERE id=%s",
            ((error or '')[:500], generation_id),
        )
        cursor.close()


def _process_generation(generation_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM quiz_generations WHERE id=%s FOR UPDATE",
            (generation_id,),
        )
        gen = cursor.fetchone()
        if not gen:
            cursor.close()
            return

        if gen['status'] != 'queued':
            # already handled / cancelled / invalid state
            cursor.close()
            return

        cursor.execute(
            "UPDATE quiz_generations SET status='generating', error=NULL WHERE id=%s",
            (generation_id,),
        )

        provider = gen.get('provider') or 'openai'
        model_id = gen.get('model_id') or 'gpt-4o-mini'
        user_id = gen['generated_by']
        topic = str(gen.get('topic') or '').strip()
        tf_count = int(gen.get('tf_count') or 0)
        sa_count = int(gen.get('sa_count') or 0)
        la_count = int(gen.get('la_count') or 0)
        mcq_count = int(gen.get('mcq_count') or 0)
        mcq_options = int(gen.get('mcq_options') or 4)
        material_ids = gen.get('selected_material_ids') or []
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
            raise ValueError(f'No {provider} API key configured for generation user')
        api_key = decrypt_api_key(key_row['encrypted_key'])

        material_context = _fetch_material_context(conn, material_ids)
        cursor.close()

    system, user_prompt = _build_quiz_prompt(
        topic, tf_count, sa_count, la_count, mcq_count, mcq_options, material_context
    )
    raw = _call_llm_json(provider, api_key, model_id, system, user_prompt)
    title = str(raw.get('title') or topic or 'Quiz').strip()
    questions = _validate_and_normalize_questions(raw.get('questions') or [])

    with get_db() as conn:
        _persist_questions(conn, generation_id, questions)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE quiz_generations SET status='ready', title=%s, error=NULL WHERE id=%s",
            (title, generation_id),
        )
        cursor.close()


def lambda_handler(event, context):
    records = event.get('Records') or []
    for record in records:
        try:
            body = json.loads(record.get('body') or '{}')
            generation_id = int(body['generation_id'])
        except Exception:
            continue

        try:
            _process_generation(generation_id)
        except Exception as exc:
            _mark_generation_failed(generation_id, str(exc))
            raise

    return {'statusCode': 200, 'body': json.dumps({'ok': True})}

