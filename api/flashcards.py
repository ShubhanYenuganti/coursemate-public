# Vercel Python Serverless Function -- Flashcards Generation
# POST /api/flashcards  action=estimate            -> create draft + token estimates
# POST /api/flashcards  action=generate            -> queue existing draft generation
# POST /api/flashcards  action=save_artifact       -> save generation as materials artifact
# POST /api/flashcards  action=resolve_regeneration -> handle post-regen resolution
# GET  /api/flashcards  action=get_generation      -> fetch stored generation payload

import json
import os
import re
import boto3
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

try:
    from .middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from .models import User
    from .courses import Course
    from .db import get_db
    from .services.flashcards_token_estimator import estimate_flashcards_token_ranges
    from .services.flashcards_pdf_builder import build_flashcards_pdf_bytes
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from models import User
    from courses import Course
    from db import get_db
    from services.flashcards_token_estimator import estimate_flashcards_token_ranges
    from services.flashcards_pdf_builder import build_flashcards_pdf_bytes

_FLASHCARDS_QUEUE_URL = os.environ.get('FLASHCARDS_GENERATION_QUEUE_URL')
_AWS_REGION = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'

_MATERIAL_CHUNK_LIMIT = 80
_CONTEXT_CHAR_BUDGET = 24_000
_ALLOWED_DEPTHS = {'brief', 'moderate', 'in-depth'}


def _pdf_filename_from_title(title: str | None, fallback_prefix: str, fallback_id: int) -> str:
    """Build a safe downloadable PDF filename from artifact title."""
    base = (title or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    if not base:
        base = f"{fallback_prefix}-{fallback_id}"
    return f"{base}.pdf"


def _normalize_depth(value: str) -> str:
    depth = (value or 'moderate').strip().lower()
    if depth in ('in_depth', 'indepth'):
        depth = 'in-depth'
    return depth if depth in _ALLOWED_DEPTHS else 'moderate'


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

    parts = []
    total = 0
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


def _build_flashcards_prompt(topic: str, card_count: int, depth: str, material_context: str):
    system = (
        "You are a flashcards generator. Return valid JSON only. No markdown fences, no preamble. "
        "Your full output must be json.loads() parseable.\\n\\n"
        "Output format:\\n"
        '{"title":"Deck title","cards":[\\n'
        '  {"front":"...","back":"...","hint":"..."}\\n'
        ']}\\n\\n'
        "Rules:\\n"
        "- Generate exactly the requested number of cards\\n"
        "- Keep front concise and unambiguous\\n"
        "- Back should match requested depth and stay factual to provided material\\n"
        "- hint is optional and brief\\n"
        "- Base all content strictly on provided material"
    )
    topic_line = f"topic: {topic}" if (topic or '').strip() else 'the provided course material'
    user = (
        f"Course materials:\\n{material_context}\\n\\n"
        f"Generate flashcards for {topic_line}.\\n"
        f"Requested card count: {card_count}\\n"
        f"Requested depth: {depth}"
    )
    return system, user


def _enqueue_flashcards_generation_job(generation_id: int, user_id: int):
    if not _FLASHCARDS_QUEUE_URL:
        raise ValueError('FLASHCARDS_GENERATION_QUEUE_URL env var is not set')
    sqs = boto3.client('sqs', region_name=_AWS_REGION)
    sqs.send_message(
        QueueUrl=_FLASHCARDS_QUEUE_URL,
        MessageBody=json.dumps({
            'generation_id': generation_id,
            'generated_by': user_id,
        }),
    )


def _persist_draft_generation(
    conn,
    *,
    course_id: int,
    user_id: int,
    title: str,
    topic: str,
    card_count: int,
    depth: str,
    provider: str,
    model_id: str,
    material_ids: list,
    prompt_text: str,
    generation_settings: dict,
    estimated_prompt_tokens_low: int,
    estimated_prompt_tokens_high: int,
    estimated_total_tokens_low: int,
    estimated_total_tokens_high: int,
    parent_generation_id=None,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO flashcard_generations
            (course_id, generated_by, title, topic, card_count, depth, provider, model_id,
             status, parent_generation_id, selected_material_ids, prompt_text, generation_settings,
             estimated_prompt_tokens_low, estimated_prompt_tokens_high,
             estimated_total_tokens_low, estimated_total_tokens_high)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s,
             'draft', %s, %s, %s, %s,
             %s, %s, %s, %s)
        RETURNING id
        """,
        (
            course_id,
            user_id,
            title,
            topic,
            card_count,
            depth,
            provider,
            model_id,
            parent_generation_id,
            json.dumps(material_ids),
            prompt_text,
            json.dumps(generation_settings),
            estimated_prompt_tokens_low,
            estimated_prompt_tokens_high,
            estimated_total_tokens_low,
            estimated_total_tokens_high,
        ),
    )
    generation_id = cursor.fetchone()['id']
    cursor.close()
    return generation_id


def _build_viewer_payload(gen: dict, cards: list) -> dict:
    payload_cards = []
    for c in cards:
        payload_cards.append(
            {
                'card_index': c.get('card_index'),
                'front': c.get('front_text') or '',
                'back': c.get('back_text') or '',
                'hint': c.get('hint_text') or '',
                'metadata': c.get('metadata') or {},
            }
        )

    return {
        'generation_id': gen.get('id'),
        'parent_generation_id': gen.get('parent_generation_id'),
        'course_id': gen.get('course_id'),
        'title': gen.get('title') or 'Flashcards',
        'topic': gen.get('topic') or '',
        'card_count': gen.get('card_count') or len(payload_cards),
        'depth': gen.get('depth') or 'moderate',
        'provider': gen.get('provider'),
        'model_id': gen.get('model_id'),
        'selected_material_ids': gen.get('selected_material_ids') or [],
        'generation_settings': gen.get('generation_settings') or {},
        'artifact_material_id': gen.get('artifact_material_id'),
        'status': gen.get('status'),
        'cards': payload_cards,
        'flashcards': payload_cards,
    }


def _load_generation_from_db(conn, generation_id: int):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM flashcard_generations WHERE id=%s AND status='ready'",
        (generation_id,),
    )
    gen = cursor.fetchone()
    if not gen:
        cursor.close()
        return None

    cursor.execute(
        """
        SELECT generation_id, card_index, front_text, back_text, hint_text, metadata
        FROM flashcard_cards
        WHERE generation_id=%s
        ORDER BY card_index
        """,
        (generation_id,),
    )
    cards = cursor.fetchall()
    cursor.close()
    return _build_viewer_payload(gen, cards)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # --- GET ------------------------------------------------------------------

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

    # --- DELETE ---------------------------------------------------------------

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
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return

        gen_id = int(gen_id_raw)
        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT artifact_material_id FROM flashcard_generations WHERE id=%s AND generated_by=%s',
                (gen_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return

            if row.get('artifact_material_id'):
                cursor.execute('DELETE FROM materials WHERE id=%s', (row['artifact_material_id'],))

            cursor.execute(
                'DELETE FROM flashcard_generations WHERE id=%s AND generated_by=%s RETURNING id',
                (gen_id, user_id),
            )
            deleted = cursor.fetchone()
            cursor.close()

        if not deleted:
            send_json(self, 404, {'error': 'Generation not found'})
            return

        send_json(self, 200, {'deleted': gen_id})

    # --- POST -----------------------------------------------------------------

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

    # --- estimate -------------------------------------------------------------

    def _estimate(self, body: dict, user: dict):
        course_id = body.get('course_id')
        if not course_id:
            send_json(self, 400, {'error': 'course_id required'})
            return

        provider = body.get('provider', 'openai')
        model_id = body.get('model_id', 'gpt-4o-mini')
        topic = str(body.get('topic') or '').strip()
        depth = _normalize_depth(body.get('depth', 'moderate'))

        try:
            card_count = int(body.get('card_count', 20))
        except (TypeError, ValueError):
            send_json(self, 400, {'error': 'card_count must be an integer'})
            return

        card_count = max(1, min(100, card_count))
        material_ids = [
            int(x) for x in (body.get('material_ids') or [])
            if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
        ]

        user_id = user['id']
        with get_db() as conn:
            cursor = conn.cursor()

            if not Course.verify_access(course_id, user_id):
                cursor.close()
                send_json(self, 403, {'error': 'Access denied to this course'})
                return

            material_context = _fetch_material_context(conn, material_ids)
            system_prompt, user_prompt = _build_flashcards_prompt(topic, card_count, depth, material_context)
            estimate = estimate_flashcards_token_ranges(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                card_count=card_count,
                depth=depth,
            )

            title = str(topic or 'Flashcards').strip() or 'Flashcards'
            prompt_text = system_prompt + '\n\n' + user_prompt
            generation_settings = {
                'topic': topic,
                'card_count': card_count,
                'depth': depth,
                'provider': provider,
                'model_id': model_id,
            }

            generation_id = _persist_draft_generation(
                conn,
                course_id=int(course_id),
                user_id=user_id,
                title=title,
                topic=topic,
                card_count=card_count,
                depth=depth,
                provider=provider,
                model_id=model_id,
                material_ids=material_ids,
                prompt_text=prompt_text,
                generation_settings=generation_settings,
                estimated_prompt_tokens_low=estimate['estimated_prompt_tokens_low'],
                estimated_prompt_tokens_high=estimate['estimated_prompt_tokens_high'],
                estimated_total_tokens_low=estimate['estimated_total_tokens_low'],
                estimated_total_tokens_high=estimate['estimated_total_tokens_high'],
                parent_generation_id=body.get('parent_generation_id'),
            )
            cursor.close()

        send_json(
            self,
            200,
            {
                'generation_id': generation_id,
                'provider': provider,
                'model_id': model_id,
                'card_count': card_count,
                'depth': depth,
                **estimate,
            },
        )

    # --- generate -------------------------------------------------------------

    def _generate(self, body: dict, user: dict):
        generation_id_raw = body.get('generation_id')
        if generation_id_raw is None:
            send_json(self, 400, {'error': 'generation_id required'})
            return

        try:
            generation_id = int(generation_id_raw)
        except (TypeError, ValueError):
            send_json(self, 400, {'error': 'Invalid generation_id'})
            return

        parent_generation_id = body.get('parent_generation_id')
        parent_generation_id_int = None
        if parent_generation_id not in (None, ''):
            try:
                parent_generation_id_int = int(parent_generation_id)
            except (TypeError, ValueError):
                send_json(self, 400, {'error': 'Invalid parent_generation_id'})
                return

        user_id = user['id']
        should_enqueue = False
        status_response = None

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM flashcard_generations WHERE id=%s AND generated_by=%s FOR UPDATE',
                (generation_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                send_json(self, 404, {'error': 'Draft generation not found'})
                return

            if not Course.verify_access(row['course_id'], user_id):
                cursor.close()
                send_json(self, 403, {'error': 'Access denied to this course'})
                return

            if parent_generation_id_int is not None:
                cursor.execute(
                    'SELECT id FROM flashcard_generations WHERE id=%s AND generated_by=%s',
                    (parent_generation_id_int, user_id),
                )
                if not cursor.fetchone():
                    cursor.close()
                    send_json(self, 403, {'error': 'parent_generation_id not owned by user'})
                    return

            provider = body.get('provider') or row.get('provider') or 'openai'
            model_id = body.get('model_id') or row.get('model_id') or 'gpt-4o-mini'

            current_status = row.get('status')
            if current_status in ('draft', 'failed'):
                cursor.execute(
                    """
                    UPDATE flashcard_generations
                    SET status='queued', provider=%s, model_id=%s, parent_generation_id=%s, error=NULL
                    WHERE id=%s
                    """,
                    (provider, model_id, parent_generation_id_int, generation_id),
                )
                should_enqueue = True
                current_status = 'queued'
            elif current_status in ('queued', 'generating', 'ready'):
                pass
            else:
                cursor.close()
                send_json(self, 409, {'error': f"Generation cannot be queued from status '{current_status}'"})
                return

            status_response = {
                'generation_id': generation_id,
                'status': current_status,
            }
            cursor.close()

        # Commit-before-enqueue guarantee: enqueue after transaction exits.
        if should_enqueue:
            try:
                _enqueue_flashcards_generation_job(generation_id, user_id)
            except Exception as exc:
                with get_db() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute(
                        "UPDATE flashcard_generations SET status='failed', error=%s WHERE id=%s",
                        (f'Failed to enqueue generation job: {exc}'[:500], generation_id),
                    )
                    cur2.close()
                send_json(self, 500, {'error': 'Failed to queue generation', 'detail': str(exc)})
                return

        send_json(self, 202, status_response)

    # --- get_generation_status ------------------------------------------------

    def _get_generation_status(self, params: dict, user: dict):
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return

        generation_id = int(gen_id_raw)
        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, status, error FROM flashcard_generations WHERE id=%s AND generated_by=%s',
                (generation_id, user_id),
            )
            row = cursor.fetchone()
            cursor.close()

        if not row:
            send_json(self, 404, {'error': 'Generation not found'})
            return

        send_json(
            self,
            200,
            {
                'generation_id': row['id'],
                'status': row['status'],
                'error': row.get('error'),
            },
        )

    # --- get_generation -------------------------------------------------------

    def _get_generation(self, params: dict, user: dict):
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return

        generation_id = int(gen_id_raw)
        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM flashcard_generations WHERE id=%s AND generated_by=%s',
                (generation_id, user_id),
            )
            owned = cursor.fetchone()
            cursor.close()
            if not owned:
                send_json(self, 404, {'error': 'Generation not found'})
                return

            payload = _load_generation_from_db(conn, generation_id)

        if not payload:
            send_json(self, 404, {'error': 'Generation not found or not ready'})
            return

        send_json(self, 200, payload)

    # --- list_generations -----------------------------------------------------

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
                    card_count,
                    depth,
                    provider,
                    model_id,
                    status,
                    error,
                    parent_generation_id,
                    artifact_material_id,
                    selected_material_ids,
                    estimated_prompt_tokens_low,
                    estimated_prompt_tokens_high,
                    estimated_total_tokens_low,
                    estimated_total_tokens_high,
                    created_at
                FROM flashcard_generations
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

    # --- export_pdf -----------------------------------------------------------

    def _export_pdf(self, params: dict, user: dict):
        gen_id_raw = params.get('generation_id', [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {'error': 'generation_id required'})
            return

        generation_id = int(gen_id_raw)
        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM flashcard_generations WHERE id=%s AND status='ready'",
                (generation_id,),
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
                SELECT card_index, front_text, back_text, hint_text
                FROM flashcard_cards
                WHERE generation_id=%s
                ORDER BY card_index
                """,
                (generation_id,),
            )
            rows = cursor.fetchall()
            cursor.close()

        deck = {
            'title': gen.get('title') or 'Flashcards',
            'topic': gen.get('topic') or '',
            'provider': gen.get('provider') or '',
            'model_id': gen.get('model_id') or '',
            'depth': gen.get('depth') or 'moderate',
            'generated_at': str(gen.get('created_at') or ''),
            'cards': [
                {
                    'card_index': r.get('card_index'),
                    'front': r.get('front_text') or '',
                    'back': r.get('back_text') or '',
                    'hint': r.get('hint_text') or '',
                }
                for r in rows
            ],
        }

        try:
            pdf_bytes = build_flashcards_pdf_bytes(deck=deck)
        except Exception as e:
            send_json(self, 500, {'error': 'Failed to build PDF', 'detail': str(e)})
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        for key, value in get_cors_headers().items():
            self.send_header(key, value)
        filename = _pdf_filename_from_title(gen.get('title'), 'flashcards', generation_id)
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(pdf_bytes)

    # --- save_artifact --------------------------------------------------------

    def _save_artifact(self, body: dict, user: dict):
        generation_id = body.get('generation_id')
        if not generation_id:
            send_json(self, 400, {'error': 'generation_id required'})
            return

        user_id = user['id']

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, title, course_id, artifact_material_id
                FROM flashcard_generations
                WHERE id=%s AND generated_by=%s AND status='ready'
                """,
                (generation_id, user_id),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {'error': 'Generation not found'})
                return

            if gen.get('artifact_material_id'):
                cursor.close()
                send_json(self, 200, {'material_id': gen['artifact_material_id'], 'already_saved': True})
                return

            title = gen.get('title') or 'Generated Flashcards'
            course_id = gen['course_id']
            cursor.execute(
                """
                INSERT INTO materials (name, file_url, file_type, source_type, uploaded_by, course_id, doc_type)
                VALUES (%s, %s, 'json', 'generated', %s, %s, 'flashcards')
                RETURNING id
                """,
                (title, f'flashcards://generation/{generation_id}', user_id, course_id),
            )
            material_id = cursor.fetchone()['id']

            cursor.execute(
                'UPDATE flashcard_generations SET artifact_material_id=%s WHERE id=%s',
                (material_id, generation_id),
            )
            cursor.close()
            Course.add_material(course_id, material_id)

        send_json(self, 200, {'material_id': material_id, 'already_saved': False})

    # --- resolve_regeneration -------------------------------------------------

    def _resolve_regeneration(self, body: dict, user: dict):
        generation_id = body.get('generation_id')
        parent_generation_id = body.get('parent_generation_id')
        resolution = body.get('resolution')

        if not generation_id or not parent_generation_id or resolution not in ('save_both', 'replace', 'revert'):
            send_json(self, 400, {'error': 'generation_id, parent_generation_id, and resolution required'})
            return

        user_id = user['id']
        try:
            generation_id = int(generation_id)
            parent_generation_id = int(parent_generation_id)
        except (TypeError, ValueError):
            send_json(self, 400, {'error': 'generation_id and parent_generation_id must be integers'})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM flashcard_generations WHERE id=%s AND generated_by=%s',
                (generation_id, user_id),
            )
            if not cursor.fetchone():
                cursor.close()
                send_json(self, 403, {'error': 'Forbidden'})
                return

            cursor.execute(
                'SELECT id FROM flashcard_generations WHERE id=%s AND generated_by=%s',
                (parent_generation_id, user_id),
            )
            if not cursor.fetchone():
                cursor.close()
                send_json(self, 403, {'error': 'Forbidden'})
                return

            if resolution == 'save_both':
                cursor.execute(
                    "UPDATE flashcard_generations SET parent_generation_id=NULL WHERE id=%s",
                    (generation_id,)
                )
                cursor.close()
                send_json(self, 200, {'resolution': 'save_both'})
                return

            if resolution == 'replace':
                cursor.execute(
                    'SELECT artifact_material_id FROM flashcard_generations WHERE id=%s',
                    (parent_generation_id,),
                )
                old = cursor.fetchone()
                if old and old.get('artifact_material_id'):
                    cursor.execute('DELETE FROM materials WHERE id=%s', (old['artifact_material_id'],))

                cursor.execute('DELETE FROM flashcard_generations WHERE id=%s', (parent_generation_id,))
                cursor.execute(
                    'UPDATE flashcard_generations SET parent_generation_id=NULL WHERE id=%s',
                    (generation_id,),
                )
                cursor.close()
                send_json(self, 200, {'resolution': 'replace'})
                return

            # revert
            cursor.execute('DELETE FROM flashcard_generations WHERE id=%s', (generation_id,))
            payload = _load_generation_from_db(conn, parent_generation_id)
            cursor.close()
            if not payload:
                send_json(self, 404, {'error': 'Parent generation not found'})
                return
            send_json(self, 200, {'resolution': 'revert', 'generation': payload})
