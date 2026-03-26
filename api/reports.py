# Vercel Python Serverless Function -- Reports Generation
# POST /api/reports  action=estimate            -> draft row + token estimates
# POST /api/reports  action=generate            -> transition draft->queued, SQS enqueue, 202
# POST /api/reports  action=save_artifact       -> save generation as materials artifact
# POST /api/reports  action=resolve_regeneration -> post-regen resolution
# GET  /api/reports  action=get_generation      -> full viewer payload (status=ready)
# GET  /api/reports  action=get_generation_status -> lightweight poll
# GET  /api/reports  action=list_generations    -> history for course
# GET  /api/reports  action=export_pdf          -> PDF download
# DELETE /api/reports ?generation_id=           -> delete generation + artifact material

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import boto3

try:
    from .middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from .models import User
    from .courses import Course
    from .db import get_db
    from .services.reports_token_estimator import estimate_reports_token_ranges
    from .services.reports_contracts import (
        build_report_prompt,
        normalize_report_sections,
        VALID_TEMPLATES,
    )
    from .services.reports_pdf_builder import build_reports_pdf_bytes
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, get_cors_headers
    from models import User
    from courses import Course
    from db import get_db
    from services.reports_token_estimator import estimate_reports_token_ranges
    from services.reports_contracts import (
        build_report_prompt,
        normalize_report_sections,
        VALID_TEMPLATES,
    )
    from services.reports_pdf_builder import build_reports_pdf_bytes


_REPORTS_QUEUE_URL = os.environ.get("REPORTS_GENERATION_QUEUE_URL")
_AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

_MATERIAL_CHUNK_LIMIT = 300
_CONTEXT_CHAR_BUDGET = 80_000
_MAX_REQUEST_BODY_BYTES = 1_000_000


def _as_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_int_list(values) -> list[int]:
    if not values:
        return []
    out = []
    for value in values:
        parsed = _as_int(value)
        if parsed is not None:
            out.append(parsed)
    return out


def _fetch_material_context(conn, material_ids: list[int]) -> str:
    if not material_ids:
        return "No course materials selected."

    cursor = conn.cursor()

    # Pass 1: documents.raw_content — clean pre-chunking text, no visual-chunk artifacts
    cursor.execute(
        """
        SELECT d.raw_content, d.id
        FROM documents d
        WHERE d.material_id = ANY(%s::int[])
          AND d.raw_content IS NOT NULL
          AND d.raw_content != ''
        ORDER BY d.material_id
        """,
        (material_ids,),
    )
    doc_rows = cursor.fetchall()

    parts = []
    total = 0
    covered_doc_ids = []

    for row in doc_rows:
        text = (row.get("raw_content") or "").strip()
        if not text:
            continue
        covered_doc_ids.append(str(row["id"]))
        if total + len(text) > _CONTEXT_CHAR_BUDGET:
            remaining = _CONTEXT_CHAR_BUDGET - total
            if remaining > 500:
                parts.append(text[:remaining])
            total = _CONTEXT_CHAR_BUDGET
            break
        parts.append(text)
        total += len(text)

    # Pass 2: text chunks for documents without raw_content
    if total < _CONTEXT_CHAR_BUDGET:
        if covered_doc_ids:
            cursor.execute(
                """
                SELECT c.content
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.material_id = ANY(%s::int[])
                  AND c.retrieval_type != 'visual'
                  AND c.document_id != ALL(%s::uuid[])
                ORDER BY d.material_id, c.chunk_index
                LIMIT %s
                """,
                (material_ids, covered_doc_ids, _MATERIAL_CHUNK_LIMIT),
            )
        else:
            cursor.execute(
                """
                SELECT c.content
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.material_id = ANY(%s::int[])
                  AND c.retrieval_type != 'visual'
                ORDER BY d.material_id, c.chunk_index
                LIMIT %s
                """,
                (material_ids, _MATERIAL_CHUNK_LIMIT),
            )
        for row in cursor.fetchall():
            content = (row.get("content") or "").strip()
            if not content:
                continue
            if total + len(content) > _CONTEXT_CHAR_BUDGET:
                remaining = _CONTEXT_CHAR_BUDGET - total
                if remaining > 200:
                    parts.append(content[:remaining])
                break
            parts.append(content)
            total += len(content)

    cursor.close()

    if not parts:
        return "No indexed content found for the selected materials."

    return "\n\n---\n\n".join(parts)


def _validate_material_ids_for_course(conn, course_id: int, user_id: int, material_ids: list[int]) -> bool:
    if not material_ids:
        return True

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
        FROM materials
        WHERE id = ANY(%s::int[])
          AND course_id = %s
          AND (visibility = 'public' OR uploaded_by = %s)
        """,
        (material_ids, course_id, user_id),
    )
    rows = cursor.fetchall()
    cursor.close()
    allowed_ids = {row["id"] for row in rows}
    return all(material_id in allowed_ids for material_id in material_ids)


def _remove_material_from_course(cursor, course_id: int | None, material_id: int | None):
    if not course_id or not material_id:
        return
    cursor.execute(
        """
        UPDATE courses
        SET material_ids = material_ids - %s::text
        WHERE id = %s
        """,
        (str(material_id), course_id),
    )


def _build_estimate_prompt(template_id: str, material_context: str, custom_prompt: str | None) -> tuple[str, str]:
    """Build prompt for estimate; custom templates use a placeholder schema."""
    if template_id == "custom":
        placeholder_system = (
            "You are a report generator. "
            f"User request: {custom_prompt or 'Custom report'}. "
            "Produce a structured JSON report."
        )
        return placeholder_system, f"Course materials:\n{material_context}"

    return build_report_prompt(
        template_id=template_id,
        material_context=material_context,
        custom_prompt=custom_prompt,
        synthesized_schema=None,
    )


def _enqueue_reports_generation_job(generation_id: int, user_id: int):
    if not _REPORTS_QUEUE_URL:
        raise ValueError("REPORTS_GENERATION_QUEUE_URL env var is not set")

    sqs = boto3.client("sqs", region_name=_AWS_REGION)
    sqs.send_message(
        QueueUrl=_REPORTS_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "generation_id": generation_id,
                "generated_by": user_id,
            }
        ),
    )


def _persist_draft(
    conn,
    *,
    course_id: int,
    user_id: int,
    template_id: str,
    custom_prompt: str | None,
    provider: str,
    model_id: str,
    material_ids: list[int],
    prompt_text: str,
    generation_settings: dict,
    est_pl: int,
    est_ph: int,
    est_tl: int,
    est_th: int,
    parent_generation_id=None,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO report_generations
            (course_id, generated_by, template_id, custom_prompt,
             provider, model_id, status, parent_generation_id,
             selected_material_ids, prompt_text, generation_settings,
             estimated_prompt_tokens_low, estimated_prompt_tokens_high,
             estimated_total_tokens_low, estimated_total_tokens_high)
        VALUES
            (%s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            course_id,
            user_id,
            template_id,
            custom_prompt or None,
            provider,
            model_id,
            parent_generation_id,
            json.dumps(material_ids),
            prompt_text,
            json.dumps(generation_settings),
            est_pl,
            est_ph,
            est_tl,
            est_th,
        ),
    )
    generation_id = cursor.fetchone()["id"]
    cursor.close()
    return generation_id


def _build_viewer_payload(gen: dict, version: dict | None) -> dict:
    normalized_version = normalize_report_sections(version or {})
    return {
        "generation_id": gen.get("id"),
        "parent_generation_id": gen.get("parent_generation_id"),
        "course_id": gen.get("course_id"),
        "template_id": gen.get("template_id"),
        "custom_prompt": gen.get("custom_prompt"),
        "title": normalized_version.get("title") or "Report",
        "subtitle": normalized_version.get("subtitle") or "",
        "page_count": normalized_version.get("page_count") or 2,
        "sections": normalized_version.get("sections") or [],
        "provider": gen.get("provider"),
        "model_id": gen.get("model_id"),
        "selected_material_ids": gen.get("selected_material_ids") or [],
        "generation_settings": gen.get("generation_settings") or {},
        "artifact_material_id": gen.get("artifact_material_id"),
        "status": gen.get("status"),
    }


def _load_generation_from_db(conn, generation_id: int):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM report_generations WHERE id=%s AND status='ready'",
        (generation_id,),
    )
    gen = cursor.fetchone()
    if not gen:
        cursor.close()
        return None

    cursor.execute(
        """
        SELECT generation_id, version_number, title, subtitle, page_count,
               sections_json, template_snapshot, source_snapshot, created_at
        FROM report_versions
        WHERE generation_id=%s
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (generation_id,),
    )
    version = cursor.fetchone()
    cursor.close()
    return _build_viewer_payload(gen, version)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    # --- GET -----------------------------------------------------------------

    def do_GET(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        params = parse_qs(urlparse(self.path).query)
        action = (params.get("action") or [None])[0]

        if action == "get_generation":
            self._get_generation(params, user)
        elif action == "get_generation_status":
            self._get_generation_status(params, user)
        elif action == "list_generations":
            self._list_generations(params, user)
        elif action == "export_pdf":
            self._export_pdf(params, user)
        else:
            send_json(self, 400, {"error": f"Unknown action: {action}"})

    def _get_generation(self, params: dict, user: dict):
        gen_id_raw = (params.get("generation_id") or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {"error": "generation_id required"})
            return

        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user["id"]),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {"error": "Generation not found"})
                return

            version = None
            if gen.get("status") == "ready":
                cursor.execute(
                    """
                    SELECT generation_id, version_number, title, subtitle, page_count,
                           sections_json, template_snapshot, source_snapshot, created_at
                    FROM report_versions
                    WHERE generation_id=%s
                    ORDER BY version_number DESC
                    LIMIT 1
                    """,
                    (gen_id,),
                )
                version = cursor.fetchone()
            cursor.close()

        if gen.get("status") != "ready":
            send_json(self, 404, {"error": "Generation not ready"})
            return
        if not version:
            send_json(self, 404, {"error": "No version data found"})
            return

        send_json(self, 200, _build_viewer_payload(gen, version))

    def _get_generation_status(self, params: dict, user: dict):
        gen_id_raw = (params.get("generation_id") or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {"error": "generation_id required"})
            return

        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, status, error FROM report_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user["id"]),
            )
            row = cursor.fetchone()
            cursor.close()

        if not row:
            send_json(self, 404, {"error": "Generation not found"})
            return

        send_json(
            self,
            200,
            {
                "generation_id": row["id"],
                "status": row["status"],
                "error": row.get("error"),
            },
        )

    def _list_generations(self, params: dict, user: dict):
        course_id_raw = (params.get("course_id") or [None])[0]
        if not course_id_raw or not str(course_id_raw).isdigit():
            send_json(self, 400, {"error": "course_id required"})
            return

        course_id = int(course_id_raw)
        if not Course.verify_access(course_id, user["id"]):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rg.id, rg.template_id, rg.custom_prompt, rg.status, rg.error,
                       rg.provider, rg.model_id, rg.artifact_material_id,
                       rg.parent_generation_id, rg.created_at,
                       rg.estimated_total_tokens_low, rg.estimated_total_tokens_high,
                       rg.generation_settings,
                       rv.title AS version_title
                FROM report_generations rg
                LEFT JOIN LATERAL (
                    SELECT title
                    FROM report_versions
                    WHERE generation_id = rg.id
                    ORDER BY version_number DESC
                    LIMIT 1
                ) rv ON true
                WHERE rg.course_id=%s AND rg.generated_by=%s
                ORDER BY rg.created_at DESC
                LIMIT 50
                """,
                (course_id, user["id"]),
            )
            rows = cursor.fetchall()
            cursor.close()

        results = []
        for row in rows:
            created_at = row.get("created_at")
            results.append(
                {
                    "generation_id": row["id"],
                    "template_id": row.get("template_id"),
                    "custom_prompt": row.get("custom_prompt"),
                    "status": row.get("status"),
                    "error": row.get("error"),
                    "provider": row.get("provider"),
                    "model_id": row.get("model_id"),
                    "artifact_material_id": row.get("artifact_material_id"),
                    "parent_generation_id": row.get("parent_generation_id"),
                    "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else None,
                    "estimated_total_tokens_low": row.get("estimated_total_tokens_low"),
                    "estimated_total_tokens_high": row.get("estimated_total_tokens_high"),
                    "generation_settings": row.get("generation_settings") or {},
                    "title": row.get("version_title"),
                }
            )

        send_json(self, 200, {"generations": results})

    def _export_pdf(self, params: dict, user: dict):
        gen_id_raw = (params.get("generation_id") or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {"error": "generation_id required"})
            return

        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s AND status='ready'",
                (gen_id, user["id"]),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {"error": "Ready generation not found"})
                return

            cursor.execute(
                """
                SELECT generation_id, version_number, title, subtitle, page_count,
                       sections_json, template_snapshot, source_snapshot, created_at
                FROM report_versions
                WHERE generation_id=%s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (gen_id,),
            )
            version = cursor.fetchone()
            cursor.close()

        if not version:
            send_json(self, 404, {"error": "No version data found"})
            return

        payload = _build_viewer_payload(gen, version)
        try:
            pdf_bytes = build_reports_pdf_bytes(report=payload)
        except Exception:
            send_json(self, 500, {"error": "Failed to build PDF"})
            return

        title_slug = (payload.get("title") or "report").replace(" ", "_")[:40]
        content_type = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/html; charset=utf-8"
        cors = get_cors_headers()
        self.send_response(200)
        for key, value in cors.items():
            self.send_header(key, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{title_slug}.pdf"')
        self.send_header("Content-Length", str(len(pdf_bytes)))
        self.end_headers()
        self.wfile.write(pdf_bytes)

    # --- DELETE ---------------------------------------------------------------

    def do_DELETE(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        params = parse_qs(urlparse(self.path).query)
        gen_id_raw = (params.get("generation_id") or [None])[0]
        if not gen_id_raw or not str(gen_id_raw).isdigit():
            send_json(self, 400, {"error": "generation_id required"})
            return

        gen_id = int(gen_id_raw)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT artifact_material_id, course_id FROM report_generations WHERE id=%s AND generated_by=%s",
                (gen_id, user["id"]),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                send_json(self, 404, {"error": "Generation not found"})
                return

            artifact_material_id = row.get("artifact_material_id")
            course_id = row.get("course_id")
            if artifact_material_id:
                cursor.execute("DELETE FROM materials WHERE id=%s", (artifact_material_id,))
                _remove_material_from_course(cursor, course_id, artifact_material_id)

            cursor.execute(
                "DELETE FROM report_generations WHERE id=%s AND generated_by=%s RETURNING id",
                (gen_id, user["id"]),
            )
            deleted = cursor.fetchone()
            cursor.close()

        if not deleted:
            send_json(self, 404, {"error": "Generation not found"})
            return

        send_json(self, 200, {"deleted": gen_id})

    # --- POST ----------------------------------------------------------------

    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length < 0 or length > _MAX_REQUEST_BODY_BYTES:
                send_json(self, 413, {"error": "Request body too large"})
                return
            body = json.loads(self.rfile.read(length) if length else b"{}")
        except (json.JSONDecodeError, ValueError):
            send_json(self, 400, {"error": "Invalid JSON body"})
            return

        action = body.get("action") or parse_qs(urlparse(self.path).query).get("action", [None])[0]
        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return

        if action == "estimate":
            self._estimate(body, user)
        elif action == "generate":
            self._generate(body, user)
        elif action == "save_artifact":
            self._save_artifact(body, user)
        elif action == "resolve_regeneration":
            self._resolve_regeneration(body, user)
        else:
            send_json(self, 400, {"error": f"Unknown action: {action}"})

    def _estimate(self, body: dict, user: dict):
        course_id_raw = body.get("course_id")
        course_id = _as_int(course_id_raw)
        if course_id is None:
            send_json(self, 400, {"error": "course_id required"})
            return

        template_id = str(body.get("template_id") or "study-guide").strip()
        if template_id not in VALID_TEMPLATES:
            send_json(self, 400, {"error": f"template_id must be one of: {', '.join(VALID_TEMPLATES)}"})
            return

        custom_prompt = str(body.get("custom_prompt") or "").strip() or None
        if template_id == "custom" and not custom_prompt:
            send_json(self, 400, {"error": "custom_prompt required for custom template"})
            return

        provider = str(body.get("provider") or "openai").strip() or "openai"
        model_id = str(body.get("model_id") or "gpt-4o-mini").strip() or "gpt-4o-mini"
        material_ids = _as_int_list(body.get("material_ids") or [])
        parent_generation_id = _as_int(body.get("parent_generation_id"))

        if not Course.verify_access(course_id, user["id"]):
            send_json(self, 403, {"error": "Access denied to this course"})
            return

        with get_db() as conn:
            if not _validate_material_ids_for_course(conn, course_id, user["id"], material_ids):
                send_json(self, 400, {"error": "One or more selected materials are invalid for this course"})
                return
            material_context = _fetch_material_context(conn, material_ids)
            system_prompt, user_prompt = _build_estimate_prompt(template_id, material_context, custom_prompt)
            estimate = estimate_reports_token_ranges(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                template_id=template_id,
            )

            generation_settings = {
                "template_id": template_id,
                "custom_prompt": custom_prompt,
                "provider": provider,
                "model_id": model_id,
            }
            generation_id = _persist_draft(
                conn,
                course_id=course_id,
                user_id=user["id"],
                template_id=template_id,
                custom_prompt=custom_prompt,
                provider=provider,
                model_id=model_id,
                material_ids=material_ids,
                prompt_text=system_prompt + "\n\n" + user_prompt,
                generation_settings=generation_settings,
                est_pl=estimate["estimated_prompt_tokens_low"],
                est_ph=estimate["estimated_prompt_tokens_high"],
                est_tl=estimate["estimated_total_tokens_low"],
                est_th=estimate["estimated_total_tokens_high"],
                parent_generation_id=parent_generation_id,
            )

        send_json(
            self,
            200,
            {
                "generation_id": generation_id,
                "template_id": template_id,
                "provider": provider,
                "model_id": model_id,
                **estimate,
            },
        )

    def _generate(self, body: dict, user: dict):
        gen_id = _as_int(body.get("generation_id"))
        if gen_id is None:
            send_json(self, 400, {"error": "generation_id required"})
            return

        provider_override = body.get("provider")
        model_id_override = body.get("model_id")

        should_enqueue = False
        status_response = None

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s FOR UPDATE",
                (gen_id, user["id"]),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                send_json(self, 404, {"error": "Draft generation not found"})
                return

            current_status = row.get("status")
            if current_status in ("queued", "generating"):
                cursor.close()
                send_json(
                    self,
                    202,
                    {
                        "generation_id": gen_id,
                        "status": current_status,
                        "message": f"Generation already {current_status}",
                    },
                )
                return
            if current_status not in ("draft", "failed"):
                cursor.close()
                send_json(self, 409, {"error": f"Cannot generate from status: {current_status}"})
                return

            update_fields = ["status=%s"]
            update_values = ["queued"]
            if provider_override:
                update_fields.append("provider=%s")
                update_values.append(provider_override)
            if model_id_override:
                update_fields.append("model_id=%s")
                update_values.append(model_id_override)
            update_values.extend([gen_id, user["id"]])

            cursor.execute(
                f"UPDATE report_generations SET {', '.join(update_fields)} WHERE id=%s AND generated_by=%s",
                update_values,
            )
            cursor.close()
            should_enqueue = True
            status_response = {"generation_id": gen_id, "status": "queued"}

        if should_enqueue:
            try:
                _enqueue_reports_generation_job(gen_id, user["id"])
            except Exception as exc:
                with get_db() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute(
                        "UPDATE report_generations SET status='failed', error=%s WHERE id=%s AND generated_by=%s",
                        ("Failed to enqueue generation job", gen_id, user["id"]),
                    )
                    cur2.close()
                send_json(self, 500, {"error": "Failed to queue generation"})
                return

        self.send_response(202)
        cors = get_cors_headers()
        for key, value in cors.items():
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(status_response).encode())

    def _save_artifact(self, body: dict, user: dict):
        gen_id = _as_int(body.get("generation_id"))
        if gen_id is None:
            send_json(self, 400, {"error": "generation_id required"})
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM report_generations WHERE id=%s AND generated_by=%s AND status='ready' FOR UPDATE",
                (gen_id, user["id"]),
            )
            gen = cursor.fetchone()
            if not gen:
                cursor.close()
                send_json(self, 404, {"error": "Ready generation not found"})
                return

            if gen.get("artifact_material_id"):
                cursor.close()
                send_json(
                    self,
                    200,
                    {"material_id": gen["artifact_material_id"], "already_saved": True},
                )
                return

            cursor.execute(
                """
                SELECT title
                FROM report_versions
                WHERE generation_id=%s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (gen_id,),
            )
            ver = cursor.fetchone()
            title = (ver or {}).get("title") or "Report"

            file_url = f"report://generation/{gen_id}"
            cursor.execute(
                """
                INSERT INTO materials (course_id, name, file_url, file_type, source_type, doc_type, uploaded_by)
                VALUES (%s, %s, %s, 'json', 'generated', 'report', %s)
                RETURNING id
                """,
                (gen["course_id"], title, file_url, user["id"]),
            )
            material_id = cursor.fetchone()["id"]
            cursor.execute(
                "UPDATE report_generations SET artifact_material_id=%s WHERE id=%s",
                (material_id, gen_id),
            )
            cursor.close()
            Course.add_material(gen["course_id"], material_id)

        send_json(self, 200, {"artifact_material_id": material_id, "generation_id": gen_id})

    def _resolve_regeneration(self, body: dict, user: dict):
        generation_id = _as_int(body.get("generation_id"))
        parent_generation_id = _as_int(body.get("parent_generation_id"))
        resolution = body.get("resolution")

        if generation_id is None or resolution is None:
            send_json(self, 400, {"error": "generation_id and resolution required"})
            return
        if resolution not in ("save_both", "replace", "revert"):
            send_json(
                self,
                400,
                {"error": "resolution must be save_both, replace, or revert"},
            )
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, parent_generation_id, artifact_material_id, course_id
                FROM report_generations
                WHERE id=%s AND generated_by=%s
                """,
                (generation_id, user["id"]),
            )
            current_generation = cursor.fetchone()
            if not current_generation:
                cursor.close()
                send_json(self, 404, {"error": "Generation not found"})
                return

            if resolution == "revert" and parent_generation_id is not None:
                if current_generation.get("parent_generation_id") != parent_generation_id:
                    cursor.close()
                    send_json(self, 400, {"error": "generation_id does not match parent_generation_id"})
                    return
                cursor.execute(
                    "DELETE FROM report_generations WHERE id=%s AND generated_by=%s",
                    (generation_id, user["id"]),
                )
                artifact_material_id = current_generation.get("artifact_material_id")
                generation_course_id = current_generation.get("course_id")
                if artifact_material_id:
                    cursor.execute("DELETE FROM materials WHERE id=%s", (artifact_material_id,))
                    _remove_material_from_course(cursor, generation_course_id, artifact_material_id)
                cursor.close()
                parent_payload = _load_generation_from_db(conn, parent_generation_id)
                if not parent_payload:
                    send_json(self, 404, {"error": "Parent generation not found after revert"})
                    return
                send_json(self, 200, {"resolution": "revert", "generation": parent_payload})
                return
            elif resolution == "replace" and parent_generation_id is not None:
                if current_generation.get("parent_generation_id") != parent_generation_id:
                    cursor.close()
                    send_json(self, 400, {"error": "generation_id does not match parent_generation_id"})
                    return
                cursor.execute(
                    "SELECT artifact_material_id, course_id FROM report_generations WHERE id=%s AND generated_by=%s",
                    (parent_generation_id, user["id"]),
                )
                parent_generation = cursor.fetchone()
                if not parent_generation:
                    cursor.close()
                    send_json(self, 404, {"error": "Parent generation not found"})
                    return
                parent_artifact_material_id = (parent_generation or {}).get("artifact_material_id")
                parent_course_id = (parent_generation or {}).get("course_id")
                if parent_artifact_material_id:
                    cursor.execute("DELETE FROM materials WHERE id=%s", (parent_artifact_material_id,))
                    _remove_material_from_course(cursor, parent_course_id, parent_artifact_material_id)
                cursor.execute(
                    "DELETE FROM report_generations WHERE id=%s AND generated_by=%s",
                    (parent_generation_id, user["id"]),
                )
                cursor.execute(
                    "UPDATE report_generations SET parent_generation_id=NULL WHERE id=%s",
                    (generation_id,),
                )
            elif resolution in ("replace", "revert"):
                cursor.close()
                send_json(self, 400, {"error": "parent_generation_id required for replace/revert"})
                return
            cursor.close()
        send_json(self, 200, {"resolution": resolution, "generation_id": generation_id})
