# Quiz Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement end-to-end quiz generation — database persistence, a `/api/quiz` serverless handler, and wired frontend components (Quiz.jsx + QuizViewer.jsx) — replacing the currently broken `/api/generate` call.

**Architecture:** A single `api/quiz.py` Vercel Python serverless handler (following `api/material.py` patterns) handles four POST actions (`generate`, `save_artifact`, `resolve_regeneration`) and one GET action (`get_generation`). Quiz generation calls the user's configured LLM provider directly via `requests` in JSON mode, persists questions/options to three new DB tables, and returns a viewer-ready payload. The frontend adds a provider/model selector to `Quiz.jsx` and wires `QuizViewer.jsx` buttons including a post-regenerate resolution banner.

**Tech Stack:** Python 3 / psycopg (PostgreSQL), requests (direct REST to OpenAI/Claude/Gemini APIs), React + Tailwind CSS, Vercel Python Serverless Functions

---

## File Map


| File                 | Change | Responsibility                                                                      |
| -------------------- | ------ | ----------------------------------------------------------------------------------- |
| `api/db.py`          | Modify | Add `quiz_generations`, `quiz_questions`, `quiz_question_options` tables            |
| `api/quiz.py`        | Create | All quiz API actions: generate, get_generation, save_artifact, resolve_regeneration |
| `src/Quiz.jsx`       | Modify | Fix broken URLs, add provider/model selector, call `/api/quiz`                      |
| `src/QuizViewer.jsx` | Modify | Wire Save Quiz + Regenerate, add resolution banner                                  |


---

## Task 1: Database Schema

**Files:**

- Modify: `api/db.py`

Add three tables at the end of `init_db()`, before `cursor.close()`, using the same `IF NOT EXISTS` idempotent pattern.

- **Step 1: Add quiz tables to `init_db()`**

In `api/db.py`, append this block before `cursor.close()`:

```python
        # Quiz generation tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_generations (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                generated_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT,
                topic TEXT,
                tf_count INTEGER NOT NULL DEFAULT 0,
                sa_count INTEGER NOT NULL DEFAULT 0,
                la_count INTEGER NOT NULL DEFAULT 0,
                mcq_count INTEGER NOT NULL DEFAULT 0,
                mcq_options INTEGER NOT NULL DEFAULT 4,
                provider VARCHAR(20),
                model_id VARCHAR(100),
                status VARCHAR(20) NOT NULL DEFAULT 'generating'
                    CHECK (status IN ('generating', 'ready', 'failed')),
                error TEXT,
                parent_generation_id INTEGER REFERENCES quiz_generations(id) ON DELETE SET NULL,
                artifact_material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quiz_questions (
                id SERIAL PRIMARY KEY,
                generation_id INTEGER NOT NULL REFERENCES quiz_generations(id) ON DELETE CASCADE,
                question_index INTEGER NOT NULL,
                question_type VARCHAR(10) NOT NULL CHECK (question_type IN ('mcq', 'tf', 'sa', 'la')),
                question_text TEXT NOT NULL,
                correct_answer_text TEXT,
                explanation TEXT
            );

            CREATE TABLE IF NOT EXISTS quiz_question_options (
                id SERIAL PRIMARY KEY,
                question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
                option_index INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                is_correct BOOLEAN NOT NULL DEFAULT FALSE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_gen_course ON quiz_generations(course_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_questions_gen ON quiz_questions(generation_id, question_index);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_options_question ON quiz_question_options(question_id);")
```

---

## Task 2: LLM Validation Helpers

**Files:**

- Create: `api/quiz.py` (partial — validation functions only)

These are pure functions that are easy to test before wiring the HTTP handler.

- **Step 1: Write validation test**

Create `tests/test_quiz_validation.py`:

```python
"""Tests for quiz LLM response validation and normalization."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the functions once they exist
from api.quiz import _normalize_question_type, _validate_and_normalize_questions

def test_type_aliases():
    assert _normalize_question_type('multiple_choice') == 'mcq'
    assert _normalize_question_type('true_false') == 'tf'
    assert _normalize_question_type('short_answer') == 'sa'
    assert _normalize_question_type('long_answer') == 'la'
    assert _normalize_question_type('MCQ') == 'mcq'
    assert _normalize_question_type('TF') == 'tf'

def test_mcq_question_valid():
    q = {
        'type': 'mcq',
        'question': 'What is X?',
        'options': ['A', 'B', 'C', 'D'],
        'answer': 'A',
        'explanation': 'Because A'
    }
    result = _validate_and_normalize_questions([q])
    assert len(result) == 1
    assert result[0]['type'] == 'mcq'
    assert result[0]['options'] == ['A', 'B', 'C', 'D']
    assert result[0]['answer'] == 'A'

def test_tf_normalizes_answer():
    q = {'type': 'tf', 'question': 'Is sky blue?', 'answer': 'yes'}
    result = _validate_and_normalize_questions([q])
    assert result[0]['answer'] == 'True'

def test_tf_false_normalizes():
    q = {'type': 'true_false', 'question': 'Is sky green?', 'answer': 'no'}
    result = _validate_and_normalize_questions([q])
    assert result[0]['answer'] == 'False'

def test_missing_question_text_raises():
    import pytest
    with pytest.raises(ValueError, match='question text'):
        _validate_and_normalize_questions([{'type': 'sa', 'question': '', 'answer': 'x'}])

def test_mcq_missing_options_raises():
    import pytest
    with pytest.raises(ValueError, match='options'):
        _validate_and_normalize_questions([{
            'type': 'mcq', 'question': 'What?', 'options': ['A'], 'answer': 'A'
        }])
```

- **Step 2: Run test to confirm it fails**

```bash
cd /Users/shubhan/OneShotCourseMate
python -m pytest tests/test_quiz_validation.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError` — `api/quiz.py` doesn't exist yet.

- **Step 3: Create `api/quiz.py` with validation helpers**

```python
# Vercel Python Serverless Function — Quiz Generation
# POST /api/quiz  action=generate          → LLM quiz generation, returns viewer-ready payload
# POST /api/quiz  action=save_artifact     → save generation as materials artifact
# POST /api/quiz  action=resolve_regeneration → handle post-regen version resolution
# GET  /api/quiz  action=get_generation    → fetch stored generation in viewer-ready shape

import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request
    from .models import User
    from .courses import Course
    from .db import get_db
    from .crypto_utils import decrypt_api_key
except ImportError:
    from middleware import send_json, handle_options, authenticate_request
    from models import User
    from courses import Course
    from db import get_db
    from crypto_utils import decrypt_api_key

_TIMEOUT = 90  # seconds — LLM generation can be slow

_TYPE_ALIASES = {
    'multiple_choice': 'mcq',
    'multiple-choice': 'mcq',
    'true_false': 'tf',
    'true-false': 'tf',
    'short_answer': 'sa',
    'short-answer': 'sa',
    'long_answer': 'la',
    'long-answer': 'la',
}

_TF_TRUE_VALUES = {'true', 'yes', '1', 't', 'correct'}
_TF_FALSE_VALUES = {'false', 'no', '0', 'f', 'incorrect', 'wrong'}


def _normalize_question_type(t: str) -> str:
    t = (t or '').lower().strip()
    return _TYPE_ALIASES.get(t, t)


def _validate_and_normalize_questions(questions: list) -> list:
    """Validate and normalize raw LLM question list to viewer-ready shape.

    Raises ValueError with a descriptive message on any structural issue.
    Returns normalized list where each item has: type, question, options, answer, explanation.
    """
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
            # Answer must match one option or be a valid index
            if answer not in str_options:
                try:
                    idx = int(answer)
                    answer = str_options[idx]
                except (ValueError, IndexError):
                    # Accept as-is; viewer handles gracefully
                    pass
            options = str_options

        if q_type == 'tf':
            norm = answer.lower()
            if norm in _TF_TRUE_VALUES:
                answer = 'True'
            elif norm in _TF_FALSE_VALUES:
                answer = 'False'
            else:
                answer = 'True'  # safe default

        result.append({
            'type': q_type,
            'question': text,
            'options': options if q_type == 'mcq' else None,
            'answer': answer,
            'explanation': explanation,
        })
    return result
```

- **Step 4: Run tests — expect pass**

```bash
cd /Users/shubhan/OneShotCourseMate
python -m pytest tests/test_quiz_validation.py -v
```

Expected: `6 passed`

---

## Task 3: Material Context Fetching + Prompt Building

**Files:**

- Modify: `api/quiz.py`
- **Step 1: Write material context test**

Append to `tests/test_quiz_validation.py`:

```python
from api.quiz import _build_quiz_prompt

def test_build_prompt_includes_topic():
    system, user = _build_quiz_prompt(
        topic='Neural Networks',
        tf_count=2, sa_count=1, la_count=0, mcq_count=3, mcq_options=4,
        material_context='Context text here'
    )
    assert 'Neural Networks' in user
    assert 'mcq' in user.lower() or 'multiple' in user.lower()
    assert 'Context text here' in user
    assert 'JSON' in system

def test_build_prompt_no_topic_fallback():
    system, user = _build_quiz_prompt(
        topic='', tf_count=1, sa_count=0, la_count=0, mcq_count=0, mcq_options=4,
        material_context='Some material'
    )
    assert 'course material' in user.lower()
```

- **Step 2: Run test — expect fail**

```bash
python -m pytest tests/test_quiz_validation.py::test_build_prompt_includes_topic -v
```

Expected: `ImportError` — `_build_quiz_prompt` not yet defined.

- **Step 3: Add material context + prompt builder to `api/quiz.py`**

Append after the validation functions:

```python
_MATERIAL_CHUNK_LIMIT = 80  # max chunks to pull for context
_CONTEXT_CHAR_BUDGET = 24_000  # ~6k tokens at 4 chars/token


def _fetch_material_context(conn, material_ids: list) -> str:
    """Fetch chunk content for given material IDs and concatenate into a context string."""
    if not material_ids:
        return "No course materials selected."
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.content
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.material_id = ANY(%s::int[])
        ORDER BY d.material_id, c.chunk_index
        LIMIT %s
    """, (material_ids, _MATERIAL_CHUNK_LIMIT))
    rows = cursor.fetchall()
    cursor.close()
    if not rows:
        return "No indexed content found for the selected materials."
    parts = []
    total = 0
    for row in rows:
        content = row['content'] or ''
        if total + len(content) > _CONTEXT_CHAR_BUDGET:
            remaining = _CONTEXT_CHAR_BUDGET - total
            if remaining > 200:
                parts.append(content[:remaining])
            break
        parts.append(content)
        total += len(content)
    return '\n\n---\n\n'.join(parts)


def _build_quiz_prompt(topic: str, tf_count: int, sa_count: int, la_count: int,
                        mcq_count: int, mcq_options: int, material_context: str):
    """Return (system_prompt, user_prompt) for the quiz generation LLM call."""
    system = (
        "You are a quiz generator. Respond with valid JSON ONLY — no markdown fences, "
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
```

- **Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_quiz_validation.py -v
```

Expected: `8 passed`

---

## Task 4: LLM Provider Calls

**Files:**

- Modify: `api/quiz.py`

These are the three provider-specific JSON-mode LLM call functions.

- **Step 1: Add provider call functions to `api/quiz.py`**

Append after `_build_quiz_prompt`:

```python
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
            'response_format': {'type': 'json_object'},
            'temperature': 0.7,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return json.loads(resp.json()['choices'][0]['message']['content'])


def _call_claude_json(api_key: str, model_id: str, system: str, user: str) -> dict:
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
        },
        json={
            'model': model_id,
            'max_tokens': 4096,
            'system': system,
            'messages': [{'role': 'user', 'content': user}],
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    raw = resp.json()['content'][0]['text']
    # Claude may wrap in markdown fences despite instructions — strip them
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    return json.loads(raw)


def _call_gemini_json(api_key: str, model_id: str, system: str, user: str) -> dict:
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model_id}:generateContent?key={api_key}'
    )
    resp = requests.post(
        url,
        json={
            'contents': [{'parts': [{'text': user}]}],
            'systemInstruction': {'parts': [{'text': system}]},
            'generationConfig': {
                'responseMimeType': 'application/json',
                'temperature': 0.7,
            },
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
    return json.loads(raw)


def _call_llm_json(provider: str, api_key: str, model_id: str, system: str, user: str) -> dict:
    """Route to the correct provider JSON call."""
    if provider == 'openai':
        return _call_openai_json(api_key, model_id, system, user)
    if provider == 'claude':
        return _call_claude_json(api_key, model_id, system, user)
    if provider == 'gemini':
        return _call_gemini_json(api_key, model_id, system, user)
    raise ValueError(f"Unsupported provider: {provider}")
```

- **Step 2: Run existing tests still pass**

```bash
python -m pytest tests/test_quiz_validation.py -v
```

Expected: `8 passed`

---

## Task 5: DB Persistence Helpers

**Files:**

- Modify: `api/quiz.py`
- **Step 1: Add persistence helpers to `api/quiz.py`**

Append after `_call_llm_json`:

```python
def _persist_generation(conn, course_id: int, user_id: int, title: str, topic: str,
                         tf_count: int, sa_count: int, la_count: int, mcq_count: int,
                         mcq_options: int, provider: str, model_id: str,
                         parent_generation_id) -> int:
    """Insert a quiz_generations row with status='generating'. Returns new id."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO quiz_generations
            (course_id, generated_by, title, topic, tf_count, sa_count, la_count,
             mcq_count, mcq_options, provider, model_id, status, parent_generation_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'generating', %s)
        RETURNING id
    """, (course_id, user_id, title, topic, tf_count, sa_count, la_count,
          mcq_count, mcq_options, provider, model_id, parent_generation_id or None))
    gen_id = cursor.fetchone()['id']
    cursor.close()
    return gen_id


def _persist_questions(conn, generation_id: int, questions: list):
    """Insert quiz_questions and quiz_question_options rows."""
    cursor = conn.cursor()
    for idx, q in enumerate(questions):
        cursor.execute("""
            INSERT INTO quiz_questions
                (generation_id, question_index, question_type, question_text,
                 correct_answer_text, explanation)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (generation_id, idx, q['type'], q['question'], q['answer'], q['explanation']))
        q_id = cursor.fetchone()['id']
        for opt_idx, opt_text in enumerate(q['options'] or []):
            is_correct = (opt_text == q['answer'])
            cursor.execute("""
                INSERT INTO quiz_question_options (question_id, option_index, option_text, is_correct)
                VALUES (%s, %s, %s, %s)
            """, (q_id, opt_idx, opt_text, is_correct))
    cursor.close()


def _mark_generation_ready(conn, generation_id: int, title: str):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE quiz_generations SET status='ready', title=%s WHERE id=%s",
        (title, generation_id)
    )
    cursor.close()


def _mark_generation_failed(conn, generation_id: int, error: str):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE quiz_generations SET status='failed', error=%s WHERE id=%s",
        (error[:500], generation_id)
    )
    cursor.close()


def _build_viewer_payload(generation_id: int, questions: list, title: str,
                           parent_generation_id=None) -> dict:
    """Build the viewer-ready response payload."""
    return {
        'generation_id': generation_id,
        'parent_generation_id': parent_generation_id,
        'title': title,
        'questions': questions,
    }


def _load_generation_from_db(conn, generation_id: int) -> dict:
    """Rebuild viewer-ready payload from persisted DB rows."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM quiz_generations WHERE id=%s AND status='ready'",
        (generation_id,)
    )
    gen = cursor.fetchone()
    if not gen:
        cursor.close()
        return None
    cursor.execute(
        "SELECT * FROM quiz_questions WHERE generation_id=%s ORDER BY question_index",
        (generation_id,)
    )
    q_rows = cursor.fetchall()
    questions = []
    for qr in q_rows:
        cursor.execute(
            "SELECT option_text FROM quiz_question_options WHERE question_id=%s ORDER BY option_index",
            (qr['id'],)
        )
        opts = [r['option_text'] for r in cursor.fetchall()]
        questions.append({
            'type': qr['question_type'],
            'question': qr['question_text'],
            'options': opts if qr['question_type'] == 'mcq' else None,
            'answer': qr['correct_answer_text'],
            'explanation': qr['explanation'],
        })
    cursor.close()
    return _build_viewer_payload(
        generation_id=generation_id,
        questions=questions,
        title=gen['title'] or '',
        parent_generation_id=gen['parent_generation_id'],
    )
```

- **Step 2: Run existing tests still pass**

```bash
python -m pytest tests/test_quiz_validation.py -v
```

Expected: `8 passed`

---

## Task 6: HTTP Handler — `generate` Action

**Files:**

- Modify: `api/quiz.py`
- **Step 1: Add the HTTP handler class with `generate` to `api/quiz.py`**

Append at the end of `api/quiz.py`:

```python
class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # ─── GET ──────────────────────────────────────────────────────────────────

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
        action = params.get('action', [None])[0]

        if action == 'get_generation':
            self._get_generation(params, user)
        else:
            send_json(self, 400, {'error': f'Unknown action: {action}'})

    # ─── POST ─────────────────────────────────────────────────────────────────

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

        if action == 'generate':
            self._generate(body, user)
        elif action == 'save_artifact':
            self._save_artifact(body, user)
        elif action == 'resolve_regeneration':
            self._resolve_regeneration(body, user)
        else:
            send_json(self, 400, {'error': f'Unknown action: {action}'})

    # ─── generate ─────────────────────────────────────────────────────────────

    def _generate(self, body: dict, user: dict):
        course_id = body.get('course_id')
        if not course_id:
            send_json(self, 400, {'error': 'course_id required'})
            return

        provider = body.get('provider', 'openai')
        model_id = body.get('model_id', 'gpt-4o-mini')
        topic = str(body.get('topic') or '').strip()
        tf_count = int(body.get('tf_count', 0))
        sa_count = int(body.get('sa_count', 0))
        la_count = int(body.get('la_count', 0))
        mcq_count = int(body.get('mcq_count', 0))
        mcq_options = max(2, min(6, int(body.get('mcq_options', 4))))
        material_ids = [int(x) for x in (body.get('material_ids') or [])]
        parent_generation_id = body.get('parent_generation_id')

        total = tf_count + sa_count + la_count + mcq_count
        if total == 0:
            send_json(self, 400, {'error': 'At least one question required'})
            return

        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()

            # Verify course access
            if not Course.verify_access(course_id, user_id):
                cursor.close()
                send_json(self, 403, {'error': 'Access denied to this course'})
                return

            # Validate parent_generation_id ownership if provided
            if parent_generation_id:
                try:
                    parent_generation_id = int(parent_generation_id)
                except (TypeError, ValueError):
                    cursor.close()
                    send_json(self, 400, {'error': 'Invalid parent_generation_id'})
                    return
                cursor.execute(
                    "SELECT id FROM quiz_generations WHERE id=%s AND generated_by=%s",
                    (parent_generation_id, user_id)
                )
                if not cursor.fetchone():
                    cursor.close()
                    send_json(self, 403, {'error': 'parent_generation_id not owned by user'})
                    return

            # Fetch API key
            cursor.execute(
                'SELECT encrypted_key FROM user_api_keys WHERE user_id=%s AND provider=%s',
                (user_id, provider)
            )
            key_row = cursor.fetchone()
            cursor.close()
            if not key_row:
                send_json(self, 400, {'error': f'No {provider} API key configured. Add it in Settings.'})
                return
            api_key = decrypt_api_key(key_row['encrypted_key'])

            # Fetch material context
            material_context = _fetch_material_context(conn, material_ids)

            # Insert generation row
            gen_id = _persist_generation(
                conn, course_id, user_id, '', topic,
                tf_count, sa_count, la_count, mcq_count, mcq_options,
                provider, model_id, parent_generation_id
            )

        # Build prompt and call LLM (outside DB transaction — can be slow)
        system, user_prompt = _build_quiz_prompt(
            topic, tf_count, sa_count, la_count, mcq_count, mcq_options, material_context
        )
        try:
            raw = _call_llm_json(provider, api_key, model_id, system, user_prompt)
        except Exception as exc:
            with get_db() as conn:
                _mark_generation_failed(conn, gen_id, str(exc))
            send_json(self, 502, {'error': f'LLM call failed: {exc}'})
            return

        # Validate
        raw_questions = raw.get('questions') or []
        title = str(raw.get('title') or topic or 'Quiz').strip()
        try:
            questions = _validate_and_normalize_questions(raw_questions)
        except ValueError as exc:
            with get_db() as conn:
                _mark_generation_failed(conn, gen_id, str(exc))
            send_json(self, 422, {'error': f'LLM output validation failed: {exc}'})
            return

        # Persist questions
        with get_db() as conn:
            _persist_questions(conn, gen_id, questions)
            _mark_generation_ready(conn, gen_id, title)

        payload = _build_viewer_payload(gen_id, questions, title, parent_generation_id)
        send_json(self, 200, payload)
```

- **Step 2: Smoke test the handler imports cleanly**

```bash
python -c "from api.quiz import handler; print('OK')"
```

Expected: `OK`

---

## Task 7: HTTP Handler — Remaining Actions

**Files:**

- Modify: `api/quiz.py`
- **Step 1: Add `_get_generation`, `_save_artifact`, `_resolve_regeneration` to the handler class**

Append inside the `handler` class (after `_generate`):

```python
    # ─── get_generation ───────────────────────────────────────────────────────

    def _get_generation(self, params: dict, user: dict):
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)
        user_id = user['id']
        with get_db() as conn:
            # Ownership check before loading
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM quiz_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user_id)
            )
            if not cursor.fetchone():
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return
            cursor.close()
            payload = _load_generation_from_db(conn, gen_id)
        if not payload:
            send_json(self, 404, {'error': 'Generation not found or not ready'})
            return
        send_json(self, 200, payload)

    # ─── save_artifact ────────────────────────────────────────────────────────

    def _save_artifact(self, body: dict, user: dict):
        gen_id = body.get('generation_id')
        if not gen_id:
            send_json(self, 400, {'error': 'generation_id required'})
            return
        user_id = user['id']
        with get_db() as conn:
            cursor = conn.cursor()
            # Verify generation belongs to this user
            cursor.execute(
                "SELECT id, title, course_id, artifact_material_id FROM quiz_generations "
                "WHERE id=%s AND generated_by=%s AND status='ready'",
                (gen_id, user_id)
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return
            if gen['artifact_material_id']:
                cursor.close()
                # Already saved — return existing material_id
                send_json(self, 200, {'material_id': gen['artifact_material_id'], 'already_saved': True})
                return
            # Create a materials row for the generated quiz
            title = gen['title'] or 'Generated Quiz'
            course_id = gen['course_id']
            cursor.execute("""
                INSERT INTO materials (name, file_url, file_type, source_type, uploaded_by, course_id, doc_type)
                VALUES (%s, %s, 'json', 'generated', %s, %s, 'quiz')
                RETURNING id
            """, (title, f'quiz://generation/{gen_id}', user_id, course_id))
            material_id = cursor.fetchone()['id']
            cursor.execute(
                "UPDATE quiz_generations SET artifact_material_id=%s WHERE id=%s",
                (material_id, gen_id)
            )
            cursor.close()
            # Register the material with the course (mirrors material.py confirm_upload pattern)
            Course.add_material(course_id, material_id)
        send_json(self, 200, {'material_id': material_id, 'already_saved': False})

    # ─── resolve_regeneration ─────────────────────────────────────────────────

    def _resolve_regeneration(self, body: dict, user: dict):
        gen_id = body.get('generation_id')
        parent_gen_id = body.get('parent_generation_id')
        resolution = body.get('resolution')
        if not gen_id or not parent_gen_id or resolution not in ('save_both', 'replace', 'revert'):
            send_json(self, 400, {'error': 'generation_id, parent_generation_id, and resolution required'})
            return
        user_id = user['id']
        try:
            gen_id = int(gen_id)
            parent_gen_id = int(parent_gen_id)
        except (TypeError, ValueError):
            send_json(self, 400, {'error': 'generation_id and parent_generation_id must be integers'})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            # Verify ownership of both rows (single query, avoids ANY([]) psycopg3 ambiguity)
            cursor.execute(
                "SELECT id FROM quiz_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user_id)
            )
            if not cursor.fetchone():
                cursor.close()
                send_json(self, 403, {'error': 'Forbidden'})
                return
            cursor.execute(
                "SELECT id FROM quiz_generations WHERE id=%s AND generated_by=%s",
                (parent_gen_id, user_id)
            )
            if not cursor.fetchone():
                cursor.close()
                send_json(self, 403, {'error': 'Forbidden'})
                return

            if resolution == 'save_both':
                cursor.close()
                send_json(self, 200, {'resolution': 'save_both'})
                return

            if resolution == 'replace':
                # Hard delete old generation (cascade drops questions/options)
                # Also delete its artifact material if it had one
                cursor.execute(
                    "SELECT artifact_material_id FROM quiz_generations WHERE id=%s",
                    (parent_gen_id,)
                )
                old = cursor.fetchone()
                if old and old['artifact_material_id']:
                    cursor.execute("DELETE FROM materials WHERE id=%s", (old['artifact_material_id'],))
                cursor.execute("DELETE FROM quiz_generations WHERE id=%s", (parent_gen_id,))
                # Clear parent link on new generation
                cursor.execute(
                    "UPDATE quiz_generations SET parent_generation_id=NULL WHERE id=%s",
                    (gen_id,)
                )
                cursor.close()
                send_json(self, 200, {'resolution': 'replace'})
                return

            if resolution == 'revert':
                # Hard delete new generation (cascade), then load parent — all on same connection
                # to avoid nested get_db() pool contention
                cursor.execute("DELETE FROM quiz_generations WHERE id=%s", (gen_id,))
                payload = _load_generation_from_db(conn, parent_gen_id)
                cursor.close()
                if not payload:
                    send_json(self, 404, {'error': 'Parent generation not found'})
                    return
                send_json(self, 200, {'resolution': 'revert', 'generation': payload})
                return
```

- **Step 2: Verify clean import**

```bash
python -c "from api.quiz import handler; print('handler methods:', [m for m in dir(handler) if m.startswith('_') and not m.startswith('__')])"
```

Expected: output includes `_generate`, `_get_generation`, `_save_artifact`, `_resolve_regeneration`

---

## Task 8: Update `Quiz.jsx`

**Files:**

- Modify: `src/Quiz.jsx`

Three changes: fix `/api/materials` → `/api/material`, add provider/model selector, replace `/api/generate` with `/api/quiz`.

- **Step 1: Fix materials URL and generate call, add provider state**

Replace the existing `Quiz` component with the updated version. Key changes are marked with comments.

At the top of the existing imports, add nothing — QuizViewer is already imported.

**Add PROVIDER_MODELS constant** (same data as ChatTab) at the top of `Quiz.jsx`, after the existing icon components and before `Quiz`:

```js
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

**Inside the `Quiz` component**, add provider state after the existing quiz config state:

```js
  // Provider / model selector
  const [availableProviders, setAvailableProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(
    () => localStorage.getItem('quiz_selected_provider') || 'openai'
  );
  const [selectedModelId, setSelectedModelId] = useState(
    () => localStorage.getItem('quiz_selected_model_id') || 'gpt-4o-mini'
  );
  const [providerDropdownOpen, setProviderDropdownOpen] = useState(false);
```

**Replace the existing `useEffect` for materials** (currently calls `/api/materials`):

```js
  useEffect(() => {
    if (!course?.id || !sessionToken) return;
    setMaterialsLoading(true);
    fetch(`/api/material?course_id=${course.id}`, {   // fixed: /api/material (singular)
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id, sessionToken]);
```

**Add a second `useEffect`** after the materials one to load available providers:

```js
  useEffect(() => {
    if (!sessionToken) return;
    fetch('/api/user_api_keys', {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => {
        const available = Object.entries(data || {})
          .filter(([, has]) => has)
          .map(([p]) => p);
        setAvailableProviders(available);
        const saved = localStorage.getItem('quiz_selected_provider');
        const provider = available.includes(saved) ? saved : (available[0] || 'openai');
        const savedModel = localStorage.getItem('quiz_selected_model_id');
        const modelList = PROVIDER_MODELS[provider] ?? [];
        const modelId = modelList.find((m) => m.id === savedModel)?.id ?? modelList[0]?.id ?? null;
        setSelectedProvider(provider);
        setSelectedModelId(modelId);
      })
      .catch(() => {});
  }, [sessionToken]);
```

**Replace `handleGenerate`** (fixes the broken `/api/generate` call):

```js
  async function handleGenerate(parentGenerationId = null) {
    if (generating) return;
    setGenerateError('');
    setGenerating(true);
    try {
      const contextIds = selectAll
        ? materials.map((m) => m.id)
        : Array.from(selectedSources);
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'generate',
          course_id: course?.id,
          topic,
          tf_count: tfCount,
          sa_count: saCount,
          la_count: laCount,
          mcq_count: mcqCount,
          mcq_options: mcqOptions,
          material_ids: contextIds,
          provider: selectedProvider,
          model_id: selectedModelId,
          parent_generation_id: parentGenerationId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setGenerateError(err.error || 'Generation failed. Please try again.');
      } else {
        const data = await res.json().catch(() => null);
        if (data) {
          setGenerationId(data.generation_id);
          setParentGenerationId(data.parent_generation_id || null);
          setQuizData(data);
        }
      }
    } catch {
      setGenerateError('Something went wrong. Please try again.');
    } finally {
      setGenerating(false);
    }
  }
```

**Add generation ID state** alongside `quizData`:

```js
  const [generationId, setGenerationId] = useState(null);
  const [parentGenerationId, setParentGenerationId] = useState(null);
```

**Update the QuizViewer render** (pass new props):

```jsx
  if (quizData) {
    return (
      <QuizViewer
        quiz={quizData}
        generationId={generationId}
        parentGenerationId={parentGenerationId}
        sessionToken={sessionToken}
        onClose={() => { setQuizData(null); setGenerationId(null); setParentGenerationId(null); }}
        onRegenerate={() => handleGenerate(generationId)}
        onResolve={(resolution, revertPayload) => {
          if (resolution === 'revert' && revertPayload) {
            setQuizData(revertPayload);
            setGenerationId(revertPayload.generation_id);
            setParentGenerationId(revertPayload.parent_generation_id || null);
          } else {
            setParentGenerationId(null);
          }
        }}
      />
    );
  }
```

**Add provider selector UI** inside the quiz config form, after the MCQ option count section and before the summary block:

```jsx
        {/* Provider / Model selector */}
        {availableProviders.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">AI Model</label>
            <div className="relative inline-block" ref={null}>
              <button
                type="button"
                onClick={() => setProviderDropdownOpen((o) => !o)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-white text-xs text-gray-700 hover:border-indigo-400 transition-colors"
              >
                <span className="font-medium">{MODEL_LABELS[selectedProvider] || selectedProvider}</span>
                <span className="text-gray-400">·</span>
                <span>{PROVIDER_MODELS[selectedProvider]?.find((m) => m.id === selectedModelId)?.label || selectedModelId}</span>
                <ChevronDownIcon />
              </button>
              {providerDropdownOpen && (
                <div className="absolute z-20 mt-1 left-0 bg-white border border-gray-200 rounded-xl shadow-lg py-1 min-w-[200px]">
                  {availableProviders.map((p) => (
                    <div key={p}>
                      <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                        {MODEL_LABELS[p] || p}
                      </p>
                      {(PROVIDER_MODELS[p] || []).map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setSelectedProvider(p);
                            setSelectedModelId(m.id);
                            localStorage.setItem('quiz_selected_provider', p);
                            localStorage.setItem('quiz_selected_model_id', m.id);
                            setProviderDropdownOpen(false);
                          }}
                          className={`w-full text-left px-4 py-1.5 text-xs hover:bg-indigo-50 transition-colors ${
                            m.id === selectedModelId ? 'text-indigo-600 font-medium' : 'text-gray-700'
                          }`}
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
```

Note: `ChevronDownIcon` is not yet in `Quiz.jsx` — add it with the other icon components at the top:

```jsx
function ChevronDownIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
```

- **Step 2: Close the provider dropdown on outside click**

Add a `useRef` and `useEffect` for the dropdown (add after the provider state declarations):

```js
  const providerDropdownRef = useRef(null);
  useEffect(() => {
    if (!providerDropdownOpen) return;
    function onOutside(e) {
      if (providerDropdownRef.current && !providerDropdownRef.current.contains(e.target)) {
        setProviderDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', onOutside);
    return () => document.removeEventListener('mousedown', onOutside);
  }, [providerDropdownOpen]);
```

Attach `ref={providerDropdownRef}` to the outer `<div className="relative inline-block">` for the dropdown.

Also add `useRef` to the import at the top of `Quiz.jsx`:

```js
import { useState, useEffect, useRef } from 'react';
```

- **Step 3: Verify the component renders without errors**

Run the dev server and open the Quiz tab. Confirm:

- No console errors on load
- Materials list fetches correctly
- Provider dropdown appears if API keys are configured
- Generate button is clickable

---

## Task 9: Update `QuizViewer.jsx`

**Files:**

- Modify: `src/QuizViewer.jsx`

Wire Save Quiz button, add resolution banner. The Regenerate and Close buttons already call `onRegenerate`/`onClose` — no changes needed there.

- **Step 1: Add `useState` for save state and resolution to the QuizViewer component**

Update the `QuizViewer` function signature and add state:

```jsx
export default function QuizViewer({ quiz, generationId, parentGenerationId, sessionToken, onClose, onRegenerate, onResolve }) {
  const questions = quiz?.questions || (Array.isArray(quiz) ? quiz : []);
  const total = questions.length;

  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState({});
  const answeredCount = Object.keys(submitted).length;

  const [saveStatus, setSaveStatus] = useState('idle'); // idle | saving | saved | error
  const [resolving, setResolving] = useState(false);
```

- **Step 2: Add `handleSave` and `handleResolve` functions**

Add inside `QuizViewer` before the return:

```js
  async function handleSave() {
    if (!generationId || saveStatus === 'saving' || saveStatus === 'saved') return;
    setSaveStatus('saving');
    try {
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: 'save_artifact', generation_id: generationId }),
      });
      if (res.ok) {
        setSaveStatus('saved');
      } else {
        setSaveStatus('error');
      }
    } catch {
      setSaveStatus('error');
    }
  }

  async function handleResolve(resolution) {
    if (resolving || !parentGenerationId) return;
    setResolving(true);
    try {
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'resolve_regeneration',
          generation_id: generationId,
          parent_generation_id: parentGenerationId,
          resolution,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        onResolve?.(resolution, data.generation || null);
      }
    } catch {
      // silent — banner stays visible so user can retry
    } finally {
      setResolving(false);
    }
  }
```

- **Step 3: Wire the Save Quiz button**

Replace the existing unwired Save Quiz button:

```jsx
            <button
              type="button"
              onClick={handleSave}
              disabled={saveStatus === 'saving' || saveStatus === 'saved'}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                saveStatus === 'saved'
                  ? 'border-green-300 text-green-700 bg-green-50 cursor-default'
                  : saveStatus === 'error'
                  ? 'border-red-300 text-red-600 hover:bg-red-50'
                  : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              <BookmarkIcon />
              {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved ✓' : saveStatus === 'error' ? 'Retry Save' : 'Save Quiz'}
            </button>
```

- **Step 4: Add resolution banner**

Add this block immediately after the opening `<div className="min-h-screen ...">` tag and before the `<header>`:

```jsx
      {/* Resolution banner — shown after regeneration until user resolves */}
      {parentGenerationId && (
        <div className="bg-amber-50 border-b border-amber-200 px-8 py-3">
          <div className="max-w-5xl mx-auto flex items-center justify-between gap-4">
            <p className="text-sm text-amber-800 font-medium">
              New version generated. What would you like to do with the previous version?
            </p>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                type="button"
                onClick={() => handleResolve('save_both')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg border border-amber-300 text-xs font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50"
              >
                Save Both
              </button>
              <button
                type="button"
                onClick={() => handleResolve('replace')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg border border-amber-300 text-xs font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50"
              >
                Replace Previous
              </button>
              <button
                type="button"
                onClick={() => handleResolve('revert')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 transition-colors disabled:opacity-50"
              >
                Revert
              </button>
            </div>
          </div>
        </div>
      )}
```

- **Step 5: Verify full flow in browser**

1. Open the Quiz tab for a course that has materials and a configured API key
2. Configure question counts and click Generate Quiz
3. Confirm the viewer renders with questions
4. Click Save Quiz — confirm button changes to "Saved ✓"
5. Click Regenerate — confirm a new set of questions loads and the amber resolution banner appears
6. Try each resolution option:
  - **Save Both** — banner disappears, both generations still queryable via `GET /api/quiz?action=get_generation&generation_id=...`
  - **Replace Previous** — banner disappears
  - **Revert** — viewer swaps back to previous questions, banner disappears
7. Confirm Close button returns to the config form

---

## Task 10: Manual E2E Validation

- **Verify all question types render correctly**

Generate a quiz with at least 1 of each type (TF, MCQ, SA, LA). Confirm:

- MCQ shows 4 option buttons; clicking one marks correct/wrong immediately
- TF shows True/False buttons; clicking marks correct/wrong immediately
- SA shows text input + Submit button; submitted shows correct answer
- LA shows textarea + Submit button; submitted shows correct answer
- "Don't know?" button marks any card as submitted without penalty
- **Verify provider selector**

In Settings, add an OpenAI key. Confirm the provider dropdown appears in Quiz.jsx. Switch to Gemini if a Gemini key is also configured. Confirm a quiz generates successfully with each provider.

- **Verify error states**
- Remove the API key for a provider, attempt to generate — confirm `"No X API key configured"` error message
- Test with 0 total questions (all steppers at 0) — Generate button should be disabled
- **Verify the generation persists across page refresh**

After generating, note the `generation_id` from browser DevTools Network tab. Navigate away and call:

```
GET /api/quiz?action=get_generation&generation_id=<id>
```

from browser with correct Auth header. Confirm viewer-ready JSON is returned.
---

## Session 2 Changes (2026-03-25): Polish, UX & Refinements

> These changes were implemented as incremental bug fixes and UX improvements after the initial end-to-end flow was working. Include all of these when replicating this pattern for Flashcards or other generation types.

---

### Change 1: Async Generation with Polling

**Problem:** Vercel serverless functions time out during long LLM calls, causing "Something went wrong" errors even when generation succeeds.

**Pattern:** Fire-and-forget + 5-second polling.

**Backend additions to `api/quiz.py`:**

1. Add `estimate` POST action — creates a `draft` row, returns token estimates + `generation_id`. No LLM call.
2. Add `GET action=get_generation_status` — lightweight poll returning `{generation_id, status, error}`.
3. Add `GET action=list_generations` — returns all rows for a course with `status`, `topic`, question counts, `selected_material_ids`.
4. Schema change: add `status VARCHAR(20) CHECK (status IN ('draft', 'generating', 'ready', 'failed'))` and `selected_material_ids JSONB` to `quiz_generations`.

**`_generate` backend change:** Accept `generation_id` in body. When provided, load the draft row and UPDATE it (`status='generating'`, and update `provider`/`model_id` if overrides provided in body) rather than INSERT a new row.

```python
# When draft_generation_id provided:
provider = body.get('provider') or draft.get('provider') or provider
model_id = body.get('model_id') or draft.get('model_id') or model_id
# UPDATE row with new provider/model before running LLM
cursor.execute(
    "UPDATE quiz_generations SET status='generating', provider=%s, model_id=%s, parent_generation_id=%s WHERE id=%s",
    (provider, model_id, parent_generation_id_int, draft_generation_id),
)
```

**Frontend `Quiz.jsx` polling infrastructure:**

```js
// State
const [generatingIds, setGeneratingIds] = useState(new Set());
const pollTimersRef = useRef({});

const stopPolling = useCallback((genId) => {
  clearInterval(pollTimersRef.current[genId]);
  delete pollTimersRef.current[genId];
  setGeneratingIds((prev) => { const s = new Set(prev); s.delete(genId); return s; });
}, []);

const startPolling = useCallback((genId) => {
  if (pollTimersRef.current[genId]) return;
  setGeneratingIds((prev) => new Set(prev).add(genId));
  pollTimersRef.current[genId] = setInterval(async () => {
    const r = await fetch(`/api/quiz?action=get_generation_status&generation_id=${genId}`, ...);
    const data = await r.json();
    if (data.status === 'ready') {
      stopPolling(genId);
      setHistoryGenerations(prev => prev.map(g => g.generation_id === genId ? {...g, status:'ready'} : g));
      loadHistory();
    } else if (data.status === 'failed') {
      stopPolling(genId);
      setHistoryGenerations(prev => prev.map(g => g.generation_id === genId ? {...g, status:'failed'} : g));
    }
  }, 5000);
}, [stopPolling]);
```

**`triggerGeneration(genId, parentId, provider, modelId)`:**
- Starts polling immediately
- Optimistically sets row to `'generating'` in `historyGenerations`
- Fires fire-and-forget POST to generate; if HTTP holds, uses response directly and stops polling
- On stopPolling, patches row to `'ready'`/`'failed'` in `historyGenerations`

**Auto-resume on refresh:** In `loadHistory()`, after setting state, loop over returned generations:
```js
generations.forEach((g) => {
  if (g.status === 'generating') startPolling(g.generation_id);
});
```

---

### Change 2: Draft Lifecycle

**Estimate creates a draft row** — visible in history immediately as `status='draft'`.

**Confirm modal flow:** User clicks Generate → estimate runs → `GenerationConfirmModal` shown with token counts. On confirm: `triggerGeneration(genId)`. On "Save as Draft": close modal, call `loadHistory()` (draft already in DB). On cancel: DELETE the draft, optimistically remove from `historyGenerations`.

```js
function cancelConfirm() {
  const genId = confirmModalData?.generation_id;
  setConfirmModalData(null);
  if (!genId) return;
  setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
  fetch(`/api/quiz?generation_id=${genId}`, { method: 'DELETE', ... }).catch(() => {});
}
```

**History UI states:**
- `draft`: shows "Generate" button → calls `triggerGeneration(g.generation_id)` directly
- `generating`: shows spinner + "Processing…"
- `ready`: shows "Reopen" + "Regenerate" buttons
- `failed`: shows error indicator
- All rows: trash icon (rightmost), calls `deleteGeneration(genId)` which stops polling + optimistic remove + DELETE

---

### Change 3: Delete with Material Backpropagation

**Backend `do_DELETE`:** Before deleting the generation row, check `artifact_material_id`. If set, delete the linked material first.

```python
cursor.execute("SELECT artifact_material_id FROM quiz_generations WHERE id=%s AND generated_by=%s", ...)
row = cursor.fetchone()
if row['artifact_material_id']:
    cursor.execute("DELETE FROM materials WHERE id=%s", (row['artifact_material_id'],))
cursor.execute("DELETE FROM quiz_generations WHERE id=%s AND generated_by=%s RETURNING id", ...)
```

**Schema:** `artifact_material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL` — the FK nullifies on material delete, but we need the reverse (quiz delete → material delete) handled in code.

---

### Change 4: Reopen from History

`reopenFromHistory(gen)` fetches the full generation via `GET action=get_generation` and sets `quizData`. Does NOT restore form fields.

---

### Change 5: Save Quiz Persistence

`saveStatus` initialized from `quiz?.artifact_material_id ? 'saved' : 'idle'`. The save button persists across reopens.

Backend: `_build_viewer_payload` and `_load_generation_from_db` must include `artifact_material_id` in the returned payload.

---

### Change 6: Deferred Grading + "Show the Answer"

**No immediate grading.** Changes to `QuizViewer.jsx`:

- `submitted` state renamed to `revealed` — tracks which questions have been revealed (Set of indices), NOT whether quiz was submitted.
- MCQ/TF: clicking an option selects it but does NOT reveal correctness. `revealed` controls whether correct/incorrect indicator shows.
- SA/LA: no inline submit button per-question.
- **"Show the answer" text button** on each `QuestionCard` — calls `onReveal(index)`. If answer already selected, grades it; if not, marks as incorrect and reveals correct answer + explanation.
- **Submit Quiz** button: calls `handleSubmitAttempt`, which reveals all questions and submits to backend.
- `answeredCount`: counts non-empty answers (not reveals).

---

### Change 7: Question Shuffling + Attempt History

**Shuffling:** In `QuizViewer`, questions are shuffled once per quiz load via `useMemo` keyed on `generation_id`. Each question gets `originalIndex` (its DB position). On submission, `answers_by_index` maps using `q.originalIndex` not display index.

```js
const questions = useMemo(() => {
  const arr = (quiz?.questions || []).map((q, i) => ({ ...q, originalIndex: i }));
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}, [quiz?.generation_id]);
```

**Attempt history backend additions to `api/quiz.py`:**
- `GET action=list_attempts&generation_id=<id>` — returns `[{attempt_id, submitted_at, score_percent, manual_review_count}]`
- `GET action=get_attempt&attempt_id=<id>` — returns per-question breakdown with `user_response`, `is_correct`, `correct_answer`, `explanation`, `options`

**Attempt history frontend in `QuizViewer.jsx`:**
- `viewMode` state: `'quiz' | 'attempts' | 'attempt-detail'`
- "Attempts" button always visible in header
- Attempts list: score with color coding (green ≥70, amber ≥40, red <40), date, "Review" button
- Attempt detail: per-question cards with correct/incorrect/skipped badge

---

### Change 8: Model Selection at Regenerate Time

**`GenerationConfirmModal.jsx`** gains a model picker dropdown (replaces static model text). Props added: `availableProviders`, `providerModels`, `modelLabels`. `onConfirm` now receives `{ provider, model_id }` from the modal's local state.

**`Quiz.jsx`:** `confirmGenerate({ provider, model_id })` destructures from modal and passes to `triggerGeneration(genId, parentId, provider, modelId)`. Both `GenerationConfirmModal` instances receive the model picker props.

**`QuizViewerRoute.jsx`:** Regenerate now routes through estimate → confirm modal (same as Quiz.jsx). Adds `availableProviders` fetch from `/api/generate?action=available_providers`. On cancel, fires DELETE to clean up the created draft.

**Backend:** When generating from a draft, body `provider`/`model_id` override stored draft values. The UPDATE that transitions `draft → generating` now also persists the new provider/model:
```python
cursor.execute(
    "UPDATE quiz_generations SET status='generating', provider=%s, model_id=%s, parent_generation_id=%s WHERE id=%s",
    (provider, model_id, parent_generation_id_int, draft_generation_id),
)
```

---

### Change 9: Select All Toggle for Sources

Pattern used in Reports.jsx and Flashcards.jsx (and extended to Quiz.jsx and ChatTab.jsx):

```js
const [selectAll, setSelectAll] = useState(true);
const [selectedSources, setSelectedSources] = useState(new Set());

function toggleSource(id) {
  setSelectAll(false); // deselecting any item turns off "all"
  setSelectedSources((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
}

function toggleSelectAll() {
  if (selectAll) { setSelectAll(false); setSelectedSources(new Set()); }
  else { setSelectAll(true); setSelectedSources(new Set()); }
}

function isSourceSelected(id) { return selectAll || selectedSources.has(id); }
const selectedCount = selectAll ? materials.length : selectedSources.size;
```

**UI placement:** Toggle goes right-justified next to the `selectedCount/total` label (ChatTab) or after the "Select sources to include in generation" subtext (Quiz, Reports, Flashcards). Use the existing `SourceToggle` / `MaterialToggle` component.

---

### Key Architectural Patterns to Replicate

| Concern | Pattern |
|---------|---------|
| LLM timeout | estimate → draft → fire-and-forget generate → 5s polling |
| Draft cleanup | Cancel modal → optimistic remove from list + background DELETE |
| Model override | Confirm modal holds local provider/model state; passed to generate API |
| Delete backprop | Check `artifact_material_id` before deleting generation; DELETE material first |
| Shuffle stability | `useMemo` keyed on `generation_id`; `originalIndex` preserved for backend |
| Save persistence | Initialize from payload's `artifact_material_id`; include in DB load helper |
| Auto-resume polling | In `loadHistory`, start polling for any row with `status='generating'` |

---

## Session 2 Changes Addendum (2026-03-25): Async Worker + Queue Hardening

> This addendum captures the final production architecture and all key resolutions from this thread. Treat this as the source of truth over earlier "polling-only from API runtime" assumptions.

### Final Architecture Decision

- Keep `POST action=estimate` as synchronous and lightweight (creates `draft` + token estimates).
- Keep `POST action=generate` lightweight in API runtime:
  - lock generation row (`FOR UPDATE`)
  - transition status `draft|failed -> queued`
  - commit transaction
  - enqueue async job to queue URL from `QUIZ_GENERATION_QUEUE_URL`
  - return `202 Accepted` immediately
- Move heavy LLM work out of API runtime into a dedicated worker:
  - `lambda/quiz_generate/handler.py` is invoked by queue event source mapping
  - worker transitions `queued -> generating -> ready|failed`
  - worker persists questions/options + title + validation failures
- Frontend always treats generation as async and status-driven (history + polling + resume after refresh).

### Queue + Worker Runtime Notes

- Queue trigger is created outside app code (AWS event source mapping).
- Lambda worker deployment is driven by `lambda/quiz_generate/build.sh`, aligned to existing lambda build flows in repo.
- Queue URL must be set in API runtime env (`QUIZ_GENERATION_QUEUE_URL`), and `AWS_REGION`/`AWS_DEFAULT_REGION` must be present.
- API runtime needs permission to send queue messages; worker runtime needs permission to consume queue, write logs, and access DB/network.
- Dead-letter queue is required for poison messages and retry exhaustion.

### Critical Backend Resolutions Implemented

1. **Commit-before-enqueue race fix**
   - Root issue: queue message could be sent before DB `queued` status was committed.
   - Resolution: commit status transition first, enqueue second.

2. **Cursor lifecycle fix (`cursor is closed`)**
   - Root issue: legacy synchronous path logic still executed in async draft branch.
   - Resolution: guard legacy key/material fetch logic so it only runs when not in async draft flow.

3. **JSONB adaptation fix (`cannot adapt type 'dict'`)**
   - Root issue: raw Python dict/list passed to `%s` for JSONB fields.
   - Resolution: explicit `json.dumps` for JSONB inserts/updates (`generation_settings`, `selected_material_ids`).

4. **Region resolution fix (`You must specify a region`)**
   - Root issue: SQS client created without region in some environments.
   - Resolution: explicit region selection (`AWS_REGION` fallback chain + default), then pass to `boto3.client('sqs', region_name=...)`.

5. **Status lifecycle hardening**
   - DB status constraint expanded to include `queued`.
   - Default status set to `draft`.
   - Added status index for polling/list performance.

### LLM Provider Call Parity Resolutions

All provider calls were aligned across API and worker to match known-good patterns from `api/llm.py`:

- **OpenAI**
  - remove unsupported `temperature` from chat completions payload for targeted models
  - robust error extraction from response body (not only `raise_for_status`)
- **Claude**
  - normalize message content parsing across text blocks
  - align header casing/shape to stable request path
- **Gemini**
  - use header-based API key flow (`x-goog-api-key`) and aligned request body shape
  - robust candidate/content extraction
- **Shared**
  - add resilient JSON extraction helper for fenced/raw/embedded JSON outputs

### Frontend Reliability Resolutions

- Prevent event-object leakage into payload (`onClick={() => handleGenerate()}`) to avoid circular JSON serialization errors.
- Make generation start flow `await` the API acknowledgement before local status mutation.
- Add `keepalive: true` for request durability during navigation/refresh.
- Improve surfaced errors to show real backend/provider failure cause instead of generic fallback where possible.
- Keep modal locked while queueing to prevent duplicate/conflicting actions.
- Resume active generations from history after refresh by re-starting polling for in-flight rows.

### Operational Checklist for This Architecture

- API runtime env:
  - `QUIZ_GENERATION_QUEUE_URL`
  - `AWS_REGION` (or `AWS_DEFAULT_REGION`)
  - `DATABASE_URL`
  - `API_KEY_ENCRYPTION_KEY`
- Worker env:
  - `DATABASE_URL`
  - `API_KEY_ENCRYPTION_KEY`
  - provider keys as required by runtime strategy
- Infra:
  - queue exists, DLQ attached, visibility timeout sized for generation runtime
  - event source mapping enabled and attached to `quiz_generate`
  - IAM policies attached for send/consume/log permissions

### Migration SQL Used for Async Lifecycle

```sql
BEGIN;

ALTER TABLE quiz_generations
  DROP CONSTRAINT IF EXISTS quiz_generations_status_check;

ALTER TABLE quiz_generations
  ADD CONSTRAINT quiz_generations_status_check
  CHECK (status IN ('draft', 'queued', 'generating', 'ready', 'failed'));

ALTER TABLE quiz_generations
  ALTER COLUMN status SET DEFAULT 'draft';

CREATE INDEX IF NOT EXISTS idx_quiz_gen_status_created_at
  ON quiz_generations(status, created_at DESC);

COMMIT;
```
