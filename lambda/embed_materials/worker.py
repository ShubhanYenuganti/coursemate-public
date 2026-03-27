"""
Async ingestion worker for the embed_materials Lambda.

Uses asyncpg connection pool so concurrent gather() tasks each get their
own connection — a single asyncpg connection cannot handle concurrent queries.

Supports resumable processing via `cursor` (chunk index to start from) and
`lambda_context` (used to check remaining execution time before each batch).
"""
import asyncio
import json
import os
import tempfile

import asyncpg
import fitz  # PyMuPDF
import pymupdf4llm

from embedder import embed_visual, embed_text, embed_visual_text
from chunkers import route_chunker
from chunkers.base import ChunkSpec
from db import get_job_state, save_first_run_state, advance_cursor

DPI = 150
MAX_DIM = 2048
BATCH_SIZE = 5
SAFETY_MARGIN_MS = 90_000  # bail if < 90 s remain in Lambda

import re
_IMG_PLACEHOLDER_RE = re.compile(r'\*\*==> picture \[\d+ x \d+\] intentionally omitted <==\*\*\n?')


def _strip_img_placeholders(text: str) -> str:
    """Remove pymupdf4llm image placeholders before text embedding."""
    return _IMG_PLACEHOLDER_RE.sub('', text).strip()


def _vec_str(emb: list) -> str:
    return '[' + ','.join(str(x) for x in emb) + ']'


def _render_page_png(doc: fitz.Document, page_idx: int) -> bytes:
    page = doc[page_idx]
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat)
    if max(pix.width, pix.height) > MAX_DIM:
        scale = MAX_DIM / max(pix.width, pix.height)
        mat2 = fitz.Matrix(scale * DPI / 72, scale * DPI / 72)
        pix = page.get_pixmap(matrix=mat2)
    return pix.tobytes("png")


def _write_tmp(file_bytes: bytes, s3_key: str) -> str:
    suffix = "." + s3_key.split(".")[-1] if "." in s3_key else ".pdf"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(file_bytes)
    return path


def _cleanup_tmp(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


async def _insert_chunk(pool: asyncpg.Pool, doc_id: str, parent_id: str | None,
                        spec: ChunkSpec, visual_emb: list, text_emb: list | None,
                        doc_type: str, course_id: str | None) -> None:
    """Acquire a fresh connection from the pool and insert visual + text chunk rows."""
    vis_vec = _vec_str(visual_emb)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO chunks
                (document_id, content, retrieval_type, embedding, chunk_index,
                 modal_meta, parent_id, is_parent, source_type, course_id, problem_id)
            VALUES ($1, $2, 'visual', $3::vector, $4, $5, $6, false, $7, $8, $9)
        """, doc_id, spec.text, vis_vec, spec.chunk_index,
            json.dumps(spec.modal_meta), parent_id, doc_type, course_id, spec.problem_id)

        if text_emb:
            txt_vec = _vec_str(text_emb)
            await conn.execute("""
                INSERT INTO chunks
                    (document_id, content, retrieval_type, embedding, chunk_index,
                     modal_meta, parent_id, is_parent, source_type, course_id, problem_id)
                VALUES ($1, $2, 'text', $3::vector, $4, $5, $6, false, $7, $8, $9)
            """, doc_id, spec.text, txt_vec, spec.chunk_index,
                json.dumps(spec.modal_meta), parent_id, doc_type, course_id, spec.problem_id)


async def _embed_and_insert_child(pool: asyncpg.Pool, doc_id: str, parent_id: str,
                                   spec: ChunkSpec, doc_type: str,
                                   course_id: str | None,
                                   sem: asyncio.Semaphore,
                                   pdf_doc: fitz.Document) -> None:
    async with sem:
        try:
            png = _render_page_png(pdf_doc, spec.visual_page)
            visual_emb = await embed_visual(png)
        except Exception:
            visual_emb = await embed_visual_text(spec.text)

        text_emb = await embed_text(_strip_img_placeholders(spec.text))

        await _insert_chunk(pool, doc_id, parent_id, spec, visual_emb, text_emb,
                            doc_type, course_id)


async def ingest_document(material_id: int, course_id: str | None,
                          s3_key: str, doc_type: str, file_bytes: bytes,
                          cursor: int = 0, lambda_context=None) -> dict:
    """
    Embed document chunks starting from `cursor`.

    Returns:
        {"needs_continuation": True,  "next_cursor": N, "chunks_done": N}  — timed out, resume from N
        {"needs_continuation": False, "next_cursor": N, "chunks_done": N}  — fully complete
    """
    pdf_path = _write_tmp(file_bytes, s3_key)
    database_url = os.environ['DATABASE_URL']
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)

    try:
        # Always extract markdown + open PDF (fast, CPU-bound, ~seconds even for 700 pages)
        full_md = pymupdf4llm.to_markdown(pdf_path)
        pdf_doc = fitz.open(pdf_path)

        if cursor == 0:
            # ── First run: create document row ───────────────────────────
            async with pool.acquire() as conn:
                doc_id = await conn.fetchval("""
                    INSERT INTO documents (source_uri, modality, source_type, material_id)
                    VALUES ($1, 'pdf', $2, $3)
                    RETURNING id::text
                """, s3_key, doc_type, material_id)

            # ── Parent chunk (document-level summary) ────────────────────
            first_page_png = _render_page_png(pdf_doc, 0)
            parent_visual_emb = await embed_visual(first_page_png)
            parent_text_emb   = await embed_text(_strip_img_placeholders(full_md)[:8000])

            parent_vis_vec = _vec_str(parent_visual_emb)
            async with pool.acquire() as conn:
                parent_id = await conn.fetchval("""
                    INSERT INTO chunks
                        (document_id, content, retrieval_type, embedding, chunk_index,
                         modal_meta, is_parent, source_type, course_id)
                    VALUES ($1, $2, 'visual', $3::vector, -1, '{}', true, $4, $5)
                    RETURNING id::text
                """, doc_id, full_md[:8000], parent_vis_vec, doc_type, course_id)

                if parent_text_emb:
                    parent_txt_vec = _vec_str(parent_text_emb)
                    await conn.execute("""
                        INSERT INTO chunks
                            (document_id, content, retrieval_type, embedding, chunk_index,
                             modal_meta, is_parent, source_type, course_id)
                        VALUES ($1, $2, 'text', $3::vector, -1, '{}', true, $4, $5)
                    """, doc_id, full_md[:8000], parent_txt_vec, doc_type, course_id)

            # ── Chunk specs + persist state for resumptions ──────────────
            chunk_specs = route_chunker(doc_type, pdf_path, full_md)
            save_first_run_state(material_id, doc_id, len(chunk_specs))

        else:
            # ── Resumption: retrieve doc_id + parent_id from DB ─────────
            state = get_job_state(material_id)
            doc_id = state["document_id"]  # str UUID

            async with pool.acquire() as conn:
                parent_id = await conn.fetchval("""
                    SELECT id::text FROM chunks
                    WHERE document_id = $1 AND is_parent = true AND retrieval_type = 'visual'
                    LIMIT 1
                """, doc_id)

            chunk_specs = route_chunker(doc_type, pdf_path, full_md)

        # ── Batch embedding loop ─────────────────────────────────────────
        sem = asyncio.Semaphore(BATCH_SIZE)
        completed = 0
        next_cursor = len(chunk_specs)  # default: assume all done

        for batch_start in range(cursor, len(chunk_specs), BATCH_SIZE):
            # Time guard: stop before Lambda hard-kills us
            if lambda_context is not None:
                remaining = lambda_context.get_remaining_time_in_millis()
                if remaining < SAFETY_MARGIN_MS:
                    advance_cursor(material_id, batch_start)
                    next_cursor = batch_start
                    pdf_doc.close()
                    return {"needs_continuation": True, "next_cursor": next_cursor,
                            "chunks_done": completed}

            batch = chunk_specs[batch_start : batch_start + BATCH_SIZE]
            await asyncio.gather(*[
                _embed_and_insert_child(pool, doc_id, parent_id, spec,
                                        doc_type, course_id, sem, pdf_doc)
                for spec in batch
            ])
            completed += len(batch)
            advance_cursor(material_id, batch_start + len(batch))

        pdf_doc.close()

        # All chunks done — write final counts
        total = len(chunk_specs) + 1  # +1 for parent
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE material_embed_jobs SET chunks_created = $1 WHERE material_id = $2",
                total, material_id
            )

        return {"needs_continuation": False, "next_cursor": next_cursor,
                "chunks_done": completed}

    finally:
        await pool.close()
        _cleanup_tmp(pdf_path)
