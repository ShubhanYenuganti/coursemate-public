# Vercel Python Serverless Function -- Quiz Generation
# POST /api/quiz  action=generate          -> LLM quiz generation, returns viewer-ready payload
# POST /api/quiz  action=save_artifact     -> save generation as materials artifact
# POST /api/quiz  action=resolve_regeneration -> handle post-regen version resolution
# GET  /api/quiz  action=get_generation    -> fetch stored generation in viewer-ready shape

import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    from .middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from .models import User
    from .courses import Course
    from .db import get_db
    from .crypto_utils import decrypt_api_key
    from .services.quiz_token_estimator import estimate_quiz_token_ranges
    from .services.quiz_attempt_grader import grade_quiz_attempt
    from .services.quiz_pdf_builder import build_quiz_pdf_bytes
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from models import User
    from courses import Course
    from db import get_db
    from crypto_utils import decrypt_api_key
    from services.quiz_token_estimator import estimate_quiz_token_ranges
    from services.quiz_attempt_grader import grade_quiz_attempt
    from services.quiz_pdf_builder import build_quiz_pdf_bytes

_TIMEOUT = 90  # seconds -- LLM generation can be slow

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
            if answer not in str_options:
                try:
                    idx = int(answer)
                    answer = str_options[idx]
                except (ValueError, IndexError):
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


_MATERIAL_CHUNK_LIMIT = 80
_CONTEXT_CHAR_BUDGET = 24_000


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
    raw = resp.json()['content'][0]['text'].strip()
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


def _persist_draft_generation(
    conn,
    course_id: int,
    user_id: int,
    title: str,
    topic: str,
    tf_count: int,
    sa_count: int,
    la_count: int,
    mcq_count: int,
    mcq_options: int,
    provider: str,
    model_id: str,
    *,
    material_ids: list[int],
    prompt_text: str,
    generation_settings: dict,
    estimated_prompt_tokens_low: int,
    estimated_prompt_tokens_high: int,
    estimated_total_tokens_low: int,
    estimated_total_tokens_high: int,
) -> int:
    """Insert a quiz_generations row with status='draft'. Returns new id."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO quiz_generations
            (course_id, generated_by, title, topic,
             tf_count, sa_count, la_count, mcq_count, mcq_options,
             provider, model_id, status, parent_generation_id,
             estimated_prompt_tokens_low, estimated_prompt_tokens_high,
             estimated_total_tokens_low, estimated_total_tokens_high,
             selected_material_ids, prompt_text, generation_settings)
        VALUES
            (%s, %s, %s, %s,
             %s, %s, %s, %s, %s,
             %s, %s, 'draft', NULL,
             %s, %s,
             %s, %s,
             %s, %s, %s)
        RETURNING id
        """,
        (
            course_id,
            user_id,
            title,
            topic,
            tf_count,
            sa_count,
            la_count,
            mcq_count,
            mcq_options,
            provider,
            model_id,
            estimated_prompt_tokens_low,
            estimated_prompt_tokens_high,
            estimated_total_tokens_low,
            estimated_total_tokens_high,
            json.dumps(material_ids),
            prompt_text,
            json.dumps(generation_settings),
        ),
    )
    gen_id = cursor.fetchone()["id"]
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
                           parent_generation_id=None, *,
                           course_id=None,
                           topic=None,
                           tf_count=None,
                           sa_count=None,
                           la_count=None,
                           mcq_count=None,
                           mcq_options=None,
                           provider=None,
                           model_id=None,
                           selected_material_ids=None) -> dict:
    """Build the viewer-ready response payload."""
    return {
        'generation_id': generation_id,
        'parent_generation_id': parent_generation_id,
        'course_id': course_id,
        'topic': topic,
        'tf_count': tf_count,
        'sa_count': sa_count,
        'la_count': la_count,
        'mcq_count': mcq_count,
        'mcq_options': mcq_options,
        'provider': provider,
        'model_id': model_id,
        'selected_material_ids': selected_material_ids,
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
        course_id=gen.get('course_id'),
        topic=gen.get('topic'),
        tf_count=gen.get('tf_count'),
        sa_count=gen.get('sa_count'),
        la_count=gen.get('la_count'),
        mcq_count=gen.get('mcq_count'),
        mcq_options=gen.get('mcq_options'),
        provider=gen.get('provider'),
        model_id=gen.get('model_id'),
        selected_material_ids=gen.get('selected_material_ids'),
    )


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # --- GET -------------------------------------------------------------------

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
        elif action == 'get_generation_status':
            self._get_generation_status(params, user)
        elif action == 'list_generations':
            self._list_generations(params, user)
        elif action == 'export_pdf':
            self._export_pdf(params, user)
        else:
            send_json(self, 400, {'error': f'Unknown action: {action}'})

    # --- POST ------------------------------------------------------------------

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
        elif action == 'submit_attempt':
            self._submit_attempt(body, user)
        elif action == 'save_artifact':
            self._save_artifact(body, user)
        elif action == 'resolve_regeneration':
            self._resolve_regeneration(body, user)
        else:
            send_json(self, 400, {'error': f'Unknown action: {action}'})

    # --- generate --------------------------------------------------------------

    def _generate(self, body: dict, user: dict):
        draft_generation_id_raw = body.get('generation_id')
        draft_generation_id = None
        if draft_generation_id_raw is not None:
            try:
                draft_generation_id = int(draft_generation_id_raw)
            except (TypeError, ValueError):
                send_json(self, 400, {'error': 'Invalid generation_id'})
                return

        course_id = body.get('course_id')
        if not course_id and draft_generation_id is None:
            send_json(self, 400, {'error': 'course_id required'})
            return

        user_id = user['id']
        provider = body.get('provider', 'openai')
        model_id = body.get('model_id', 'gpt-4o-mini')
        topic = str(body.get('topic') or '').strip()
        tf_count = int(body.get('tf_count', 0))
        sa_count = int(body.get('sa_count', 0))
        la_count = int(body.get('la_count', 0))
        mcq_count = int(body.get('mcq_count', 0))
        mcq_options = max(2, min(6, int(body.get('mcq_options', 4))))
        material_ids_from_request = [int(x) for x in (body.get('material_ids') or [])]
        material_ids = material_ids_from_request

        parent_generation_id = body.get('parent_generation_id')
        parent_generation_id_int = None
        if parent_generation_id is not None and parent_generation_id != '':
            try:
                parent_generation_id_int = int(parent_generation_id)
            except (TypeError, ValueError):
                send_json(self, 400, {'error': 'Invalid parent_generation_id'})
                return

        gen_id = None
        api_key = None
        material_context = None

        with get_db() as conn:
            cursor = conn.cursor()

            # --- Draft flow: generate from an existing estimate row ---
            if draft_generation_id is not None:
                cursor.execute(
                    "SELECT * FROM quiz_generations WHERE id=%s AND generated_by=%s",
                    (draft_generation_id, user_id),
                )
                draft = cursor.fetchone()
                if not draft:
                    cursor.close()
                    send_json(self, 404, {'error': 'Draft generation not found'})
                    return

                course_id = draft['course_id']
                provider = draft.get('provider') or provider
                model_id = draft.get('model_id') or model_id
                topic = draft.get('topic') or topic
                tf_count = int(draft.get('tf_count') or 0)
                sa_count = int(draft.get('sa_count') or 0)
                la_count = int(draft.get('la_count') or 0)
                mcq_count = int(draft.get('mcq_count') or 0)
                mcq_options = int(draft.get('mcq_options') or mcq_options)

                stored_material_ids = draft.get('selected_material_ids') or []
                if isinstance(stored_material_ids, list) and stored_material_ids:
                    material_ids = [int(x) for x in stored_material_ids]
                elif material_ids_from_request:
                    material_ids = material_ids_from_request

                total = tf_count + sa_count + la_count + mcq_count
                if total == 0:
                    cursor.close()
                    send_json(self, 400, {'error': 'At least one question required'})
                    return

                # Verify course access
                if not Course.verify_access(course_id, user_id):
                    cursor.close()
                    send_json(self, 403, {'error': 'Access denied to this course'})
                    return

                # Validate parent_generation_id ownership if provided
                if parent_generation_id_int is not None:
                    cursor.execute(
                        "SELECT id FROM quiz_generations WHERE id=%s AND generated_by=%s",
                        (parent_generation_id_int, user_id),
                    )
                    if not cursor.fetchone():
                        cursor.close()
                        send_json(self, 403, {'error': 'parent_generation_id not owned by user'})
                        return

                # Move draft to generating (reuses same generation_id)
                cursor.execute(
                    "UPDATE quiz_generations SET status='generating', parent_generation_id=%s WHERE id=%s",
                    (parent_generation_id_int, draft_generation_id),
                )
                gen_id = draft_generation_id

            # --- Legacy flow: create a new generation row directly ---
            else:
                if not course_id:
                    cursor.close()
                    send_json(self, 400, {'error': 'course_id required'})
                    return

                total = tf_count + sa_count + la_count + mcq_count
                if total == 0:
                    cursor.close()
                    send_json(self, 400, {'error': 'At least one question required'})
                    return

                # Verify course access
                if not Course.verify_access(course_id, user_id):
                    cursor.close()
                    send_json(self, 403, {'error': 'Access denied to this course'})
                    return

                # Validate parent_generation_id ownership if provided
                if parent_generation_id_int is not None:
                    cursor.execute(
                        "SELECT id FROM quiz_generations WHERE id=%s AND generated_by=%s",
                        (parent_generation_id_int, user_id),
                    )
                    if not cursor.fetchone():
                        cursor.close()
                        send_json(self, 403, {'error': 'parent_generation_id not owned by user'})
                        return

                # Insert generation row
                gen_id = _persist_generation(
                    conn,
                    int(course_id),
                    user_id,
                    '',
                    topic,
                    tf_count,
                    sa_count,
                    la_count,
                    mcq_count,
                    mcq_options,
                    provider,
                    model_id,
                    parent_generation_id_int,
                )
                # Persist enough snapshot data for deep-linking and regeneration.
                cursor.execute(
                    """
                    UPDATE quiz_generations
                    SET selected_material_ids=%s,
                        generation_settings=%s
                    WHERE id=%s
                    """,
                    (
                        json.dumps(material_ids),
                        json.dumps(
                            {
                                "topic": topic,
                                "tf_count": tf_count,
                                "sa_count": sa_count,
                                "la_count": la_count,
                                "mcq_count": mcq_count,
                                "mcq_options": mcq_options,
                                "provider": provider,
                                "model_id": model_id,
                            }
                        ),
                        gen_id,
                    ),
                )

            # Fetch API key
            cursor.execute(
                'SELECT encrypted_key FROM user_api_keys WHERE user_id=%s AND provider=%s',
                (user_id, provider),
            )
            key_row = cursor.fetchone()
            cursor.close()
            if not key_row:
                send_json(self, 400, {'error': f'No {provider} API key configured. Add it in Settings.'})
                return
            api_key = decrypt_api_key(key_row['encrypted_key'])

            # Fetch material context
            material_context = _fetch_material_context(conn, material_ids)

        # Build prompt and call LLM (outside DB transaction -- can be slow)
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
            # Avoid duplicate questions/options if the same generation_id is replayed.
            cursor = conn.cursor()
            cursor.execute("DELETE FROM quiz_questions WHERE generation_id=%s", (gen_id,))
            cursor.close()
            _persist_questions(conn, gen_id, questions)
            _mark_generation_ready(conn, gen_id, title)

        payload = _build_viewer_payload(
            gen_id,
            questions,
            title,
            parent_generation_id_int,
            course_id=course_id,
            topic=topic,
            tf_count=tf_count,
            sa_count=sa_count,
            la_count=la_count,
            mcq_count=mcq_count,
            mcq_options=mcq_options,
            provider=provider,
            model_id=model_id,
            selected_material_ids=material_ids,
        )
        send_json(self, 200, payload)

    # --- estimate --------------------------------------------------------------

    def _estimate(self, body: dict, user: dict):
        course_id = body.get("course_id")
        if not course_id:
            send_json(self, 400, {"error": "course_id required"})
            return

        provider = body.get("provider", "openai")
        model_id = body.get("model_id", "gpt-4o-mini")
        topic = str(body.get("topic") or "").strip()

        tf_count = int(body.get("tf_count", 0))
        sa_count = int(body.get("sa_count", 0))
        la_count = int(body.get("la_count", 0))
        mcq_count = int(body.get("mcq_count", 0))
        mcq_options = max(2, min(6, int(body.get("mcq_options", 4))))
        material_ids = [int(x) for x in (body.get("material_ids") or []) if str(x).isdigit() or isinstance(x, int)]

        total = tf_count + sa_count + la_count + mcq_count
        if total == 0:
            send_json(self, 400, {"error": "At least one question required"})
            return

        user_id = user["id"]
        with get_db() as conn:
            cursor = conn.cursor()

            # Verify course access
            if not Course.verify_access(course_id, user_id):
                cursor.close()
                send_json(self, 403, {"error": "Access denied to this course"})
                return

            # Token estimation: build the exact prompts we would use for generation
            material_context = _fetch_material_context(conn, material_ids)
            system_prompt, user_prompt = _build_quiz_prompt(
                topic, tf_count, sa_count, la_count, mcq_count, mcq_options, material_context
            )

            estimate = estimate_quiz_token_ranges(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tf_count=tf_count,
                sa_count=sa_count,
                la_count=la_count,
                mcq_count=mcq_count,
                mcq_options=mcq_options,
            )

            title = str(topic or "Quiz").strip() or "Quiz"
            prompt_text = system_prompt + "\n\n" + user_prompt
            generation_settings = {
                "topic": topic,
                "tf_count": tf_count,
                "sa_count": sa_count,
                "la_count": la_count,
                "mcq_count": mcq_count,
                "mcq_options": mcq_options,
                "provider": provider,
                "model_id": model_id,
            }

            gen_id = _persist_draft_generation(
                conn,
                int(course_id),
                user_id,
                title,
                topic,
                tf_count,
                sa_count,
                la_count,
                mcq_count,
                mcq_options,
                provider,
                model_id,
                material_ids=material_ids,
                prompt_text=prompt_text,
                generation_settings=generation_settings,
                estimated_prompt_tokens_low=estimate["estimated_prompt_tokens_low"],
                estimated_prompt_tokens_high=estimate["estimated_prompt_tokens_high"],
                estimated_total_tokens_low=estimate["estimated_total_tokens_low"],
                estimated_total_tokens_high=estimate["estimated_total_tokens_high"],
            )

            cursor.close()

        send_json(
            self,
            200,
            {
                "generation_id": gen_id,
                **estimate,
            },
        )

    # --- submit_attempt --------------------------------------------------------

    def _submit_attempt(self, body: dict, user: dict):
        gen_id_raw = body.get('generation_id')
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)

        answers_by_index = body.get('answers_by_index') or {}

        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, course_id
                FROM quiz_generations
                WHERE id=%s AND status='ready'
                """,
                (gen_id,),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return

            if not Course.verify_access(gen['course_id'], user_id):
                cursor.close()
                send_json(self, 403, {'error': 'Access denied to this course'})
                return

            cursor.execute(
                """
                SELECT id, question_index, question_type, correct_answer_text
                FROM quiz_questions
                WHERE generation_id=%s
                ORDER BY question_index
                """,
                (gen_id,),
            )
            question_rows = cursor.fetchall()
            cursor.close()

        if not question_rows:
            send_json(self, 404, {'error': 'Questions not found for this generation'})
            return

        questions = [
            {
                'question_id': r['id'],
                'question_index': r['question_index'],
                'question_type': r['question_type'],
                'correct_answer_text': r['correct_answer_text'],
            }
            for r in question_rows
        ]

        grade = grade_quiz_attempt(questions=questions, answers_by_index=answers_by_index)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO quiz_attempts
                    (generation_id, user_id, submitted_at, score_percent,
                     auto_graded_count, manual_review_count, result_summary)
                VALUES
                    (%s, %s, CURRENT_TIMESTAMP, %s,
                     %s, %s, %s)
                RETURNING id
                """,
                (
                    gen_id,
                    user_id,
                    grade.get('score_percent'),
                    grade.get('auto_graded_count', 0),
                    grade.get('manual_review_count', 0),
                    json.dumps(grade),
                ),
            )
            attempt_id = cursor.fetchone()['id']

            # Insert per-question answers.
            answers_by_index_normalized = {}
            for k, v in (answers_by_index or {}).items():
                try:
                    answers_by_index_normalized[int(k)] = v
                except (TypeError, ValueError):
                    continue

            feedback_for_manual = "Response did not exactly match the expected answer."
            for q in questions:
                idx = q['question_index']
                q_id = q['question_id']
                q_result = next((pq for pq in grade['per_question'] if pq['question_index'] == idx), None)
                if not q_result:
                    continue

                is_skipped = bool(q_result.get('skipped'))
                resp = answers_by_index_normalized.get(idx)
                response_text = None if resp is None or str(resp).strip() == "" else str(resp)

                is_correct = q_result.get('is_correct')
                grader_feedback = None
                if q_result.get('manual_review_needed'):
                    grader_feedback = feedback_for_manual

                cursor.execute(
                    """
                    INSERT INTO quiz_attempt_answers
                        (attempt_id, question_id, response_text, is_correct, grader_feedback, skipped)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (attempt_id, question_id) DO UPDATE SET
                        response_text = EXCLUDED.response_text,
                        is_correct = EXCLUDED.is_correct,
                        grader_feedback = EXCLUDED.grader_feedback,
                        skipped = EXCLUDED.skipped
                    """,
                    (
                        attempt_id,
                        q_id,
                        response_text,
                        is_correct,
                        grader_feedback,
                        is_skipped,
                    ),
                )

            cursor.close()

        send_json(
            self,
            200,
            {
                'attempt_id': attempt_id,
                'score_percent': grade.get('score_percent'),
                'manual_review_required': grade.get('manual_review_required', False),
                'per_question': grade.get('per_question', []),
            },
        )

    # --- get_generation_status -------------------------------------------------

    def _get_generation_status(self, params: dict, user: dict):
        """Lightweight poll endpoint — returns only {generation_id, status, error}."""
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)
        user_id = user['id']
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, status, error FROM quiz_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user_id),
            )
            row = cursor.fetchone()
            cursor.close()
        if not row:
            send_json(self, 404, {'error': 'Generation not found'})
            return
        send_json(self, 200, {
            'generation_id': row['id'],
            'status': row['status'],
            'error': row.get('error'),
        })

    # --- get_generation --------------------------------------------------------

    def _get_generation(self, params: dict, user: dict):
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)
        user_id = user['id']
        with get_db() as conn:
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

    # --- list_generations ------------------------------------------------------

    def _list_generations(self, params: dict, user: dict):
        course_id_raw = params.get('course_id', [None])[0]
        if not course_id_raw or not str(course_id_raw).isdigit():
            send_json(self, 400, {'error': 'course_id required'})
            return
        course_id = int(course_id_raw)

        user_id = user['id']
        if not Course.verify_access(course_id, user_id):
            send_json(self, 403, {'error': 'Access denied to this course'})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id AS generation_id,
                    title,
                    topic,
                    tf_count, sa_count, la_count, mcq_count, mcq_options,
                    provider, model_id,
                    status,
                    error,
                    parent_generation_id,
                    selected_material_ids,
                    estimated_prompt_tokens_low, estimated_prompt_tokens_high,
                    estimated_total_tokens_low, estimated_total_tokens_high,
                    created_at
                FROM quiz_generations
                WHERE course_id=%s
                  AND generated_by=%s
                ORDER BY created_at DESC
                LIMIT 12
                """,
                (course_id, user_id),
            )
            rows = cursor.fetchall()
            cursor.close()

        send_json(self, 200, {'generations': rows})

    # --- export_pdf -------------------------------------------------------------

    def _export_pdf(self, params: dict, user: dict):
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return
        gen_id = int(gen_id_raw)

        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM quiz_generations
                WHERE id=%s AND status='ready'
                """,
                (gen_id,),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return

            course_id = gen['course_id']
            if not Course.verify_access(course_id, user_id):
                cursor.close()
                send_json(self, 403, {'error': 'Access denied to this course'})
                return

            cursor.execute(
                """
                SELECT
                    id,
                    question_index,
                    question_type,
                    question_text,
                    correct_answer_text,
                    explanation
                FROM quiz_questions
                WHERE generation_id=%s
                ORDER BY question_index
                """,
                (gen_id,),
            )
            q_rows = cursor.fetchall()

            # MCQ options only needed for HTML rendering; load them as well.
            questions = []
            for qr in q_rows:
                opts = None
                if (qr['question_type'] or '') in ('mcq',):
                    cur2 = conn.cursor()
                    cur2.execute(
                        """
                        SELECT option_text
                        FROM quiz_question_options
                        WHERE question_id=%s
                        ORDER BY option_index
                        """,
                        (qr['id'],),
                    )
                    opts = [r['option_text'] for r in cur2.fetchall()]
                    cur2.close()

                questions.append(
                    {
                        'question_index': qr['question_index'],
                        'type': qr['question_type'],
                        'question': qr['question_text'],
                        'options': opts,
                        'answer': qr['correct_answer_text'],
                    }
                )

            cursor.close()

        quiz_payload = {
            'title': gen.get('title') or 'Quiz',
            'topic': gen.get('topic') or '',
            'provider': gen.get('provider'),
            'model_id': gen.get('model_id'),
            'generated_at': str(gen.get('created_at') or ''),
            'generation_settings': gen.get('generation_settings') or {},
            'questions': questions,
        }

        try:
            pdf_bytes = build_quiz_pdf_bytes(quiz=quiz_payload)
        except Exception as e:
            send_json(self, 500, {'error': 'Failed to build PDF', 'detail': str(e)})
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        for key, value in get_cors_headers().items():
            self.send_header(key, value)
        filename = f'quiz-{gen_id}.pdf'
        self.send_header('Content-Disposition', f'attachment; filename=\"{filename}\"')
        self.end_headers()
        self.wfile.write(pdf_bytes)

    # --- save_artifact ---------------------------------------------------------

    def _save_artifact(self, body: dict, user: dict):
        gen_id = body.get('generation_id')
        if not gen_id:
            send_json(self, 400, {'error': 'generation_id required'})
            return
        user_id = user['id']
        with get_db() as conn:
            cursor = conn.cursor()
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
                send_json(self, 200, {'material_id': gen['artifact_material_id'], 'already_saved': True})
                return
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
            Course.add_material(course_id, material_id)
        send_json(self, 200, {'material_id': material_id, 'already_saved': False})

    # --- resolve_regeneration --------------------------------------------------

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
                cursor.execute(
                    "SELECT artifact_material_id FROM quiz_generations WHERE id=%s",
                    (parent_gen_id,)
                )
                old = cursor.fetchone()
                if old and old['artifact_material_id']:
                    cursor.execute("DELETE FROM materials WHERE id=%s", (old['artifact_material_id'],))
                cursor.execute("DELETE FROM quiz_generations WHERE id=%s", (parent_gen_id,))
                cursor.execute(
                    "UPDATE quiz_generations SET parent_generation_id=NULL WHERE id=%s",
                    (gen_id,)
                )
                cursor.close()
                send_json(self, 200, {'resolution': 'replace'})
                return

            if resolution == 'revert':
                cursor.execute("DELETE FROM quiz_generations WHERE id=%s", (gen_id,))
                payload = _load_generation_from_db(conn, parent_gen_id)
                cursor.close()
                if not payload:
                    send_json(self, 404, {'error': 'Parent generation not found'})
                    return
                send_json(self, 200, {'resolution': 'revert', 'generation': payload})
