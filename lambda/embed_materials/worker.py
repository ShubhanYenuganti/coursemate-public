"""
Async ingestion worker for the embed_materials Lambda.

Uses asyncpg connection pool so concurrent gather() tasks each get their
own connection — a single asyncpg connection cannot handle concurrent queries.
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

DPI = 150
MAX_DIM = 2048

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
                          s3_key: str, doc_type: str, file_bytes: bytes) -> int:
    pdf_path = _write_tmp(file_bytes, s3_key)
    database_url = os.environ['DATABASE_URL']

    # Pool size: enough for concurrent child inserts (semaphore caps at 5 concurrent)
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)

    try:
        # 1. Insert documents record
        async with pool.acquire() as conn:
            doc_id = await conn.fetchval("""
                INSERT INTO documents (source_uri, modality, source_type, material_id)
                VALUES ($1, 'pdf', $2, $3)
                RETURNING id::text
            """, s3_key, doc_type, material_id)

        # 2. Extract full markdown
        full_md = pymupdf4llm.to_markdown(pdf_path)
        pdf_doc = fitz.open(pdf_path)

        # 3. Create parent chunk (sequential — no concurrency needed here)
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

        # 4. Doc-type-aware chunking
        chunk_specs = route_chunker(doc_type, pdf_path, full_md)

        # 5. Embed + insert child chunks concurrently (semaphore caps Voyage API calls)
        sem = asyncio.Semaphore(5)
        tasks = [
            _embed_and_insert_child(pool, doc_id, parent_id, spec,
                                    doc_type, course_id, sem, pdf_doc)
            for spec in chunk_specs
        ]
        await asyncio.gather(*tasks)

        pdf_doc.close()

        total = len(chunk_specs) + 1  # +1 for parent
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE material_embed_jobs SET chunks_created = $1 WHERE material_id = $2",
                total, material_id
            )
        return total

    finally:
        await pool.close()
        _cleanup_tmp(pdf_path)
