"""
Async ingestion worker for the embed_materials Lambda.

Handles the full pipeline for a single PDF:
  1. Insert documents record
  2. Extract full markdown (pymupdf4llm)
  3. Create parent chunk (full-doc text + visual of first page)
  4. Route to doc-type-aware chunker → list[ChunkSpec]
  5. Embed + insert child chunks (visual + text for each)
"""
import asyncio
import io
import os
import tempfile

import asyncpg
import fitz  # PyMuPDF
import pymupdf4llm

from embedder import embed_visual, embed_text, embed_visual_text
from chunkers import route_chunker, ChunkSpec

DPI = 150
MAX_DIM = 2048


def _vec_str(emb: list) -> str:
    return '[' + ','.join(str(x) for x in emb) + ']'


def _render_page_png(doc: fitz.Document, page_idx: int) -> bytes:
    """Render a PDF page to PNG bytes at DPI, capping longest side at MAX_DIM."""
    page = doc[page_idx]
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat)

    # Downscale if needed
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


async def _insert_chunk(conn, doc_id: str, parent_id: str | None, spec: ChunkSpec,
                        visual_emb: list, text_emb: list | None,
                        doc_type: str, course_id: str | None, sem: asyncio.Semaphore) -> None:
    """Insert two chunk rows: one visual, one text (if text embedding available)."""
    problem_id = spec.problem_id or None
    modal_meta_json = spec.modal_meta

    vis_vec = _vec_str(visual_emb)

    await conn.execute("""
        INSERT INTO chunks
            (document_id, content, retrieval_type, embedding, chunk_index,
             modal_meta, parent_id, is_parent, source_type, course_id, problem_id)
        VALUES ($1, $2, 'visual', $3::vector, $4, $5, $6, false, $7, $8, $9)
    """, doc_id, spec.text, vis_vec, spec.chunk_index,
        str(modal_meta_json), parent_id, doc_type, course_id, problem_id)

    if text_emb:
        txt_vec = _vec_str(text_emb)
        await conn.execute("""
            INSERT INTO chunks
                (document_id, content, retrieval_type, embedding, chunk_index,
                 modal_meta, parent_id, is_parent, source_type, course_id, problem_id)
            VALUES ($1, $2, 'text', $3::vector, $4, $5, $6, false, $7, $8, $9)
        """, doc_id, spec.text, txt_vec, spec.chunk_index,
            str(modal_meta_json), parent_id, doc_type, course_id, problem_id)


async def _embed_and_insert_child(conn, doc_id: str, parent_id: str,
                                   spec: ChunkSpec, doc_type: str,
                                   course_id: str | None,
                                   sem: asyncio.Semaphore,
                                   pdf_doc: fitz.Document) -> None:
    async with sem:
        # Visual: render the page and embed as image
        try:
            png = _render_page_png(pdf_doc, spec.visual_page)
            visual_emb = await embed_visual(png)
        except Exception:
            # Fallback: embed text visually if image embedding fails
            visual_emb = await embed_visual_text(spec.text)

        # Text embedding
        text_emb = await embed_text(spec.text)

        await _insert_chunk(conn, doc_id, parent_id, spec, visual_emb, text_emb,
                            doc_type, course_id, sem)


async def ingest_document(material_id: int, course_id: str | None,
                          s3_key: str, doc_type: str, file_bytes: bytes) -> int:
    """
    Full async ingestion for one PDF.
    Returns total chunks inserted (parent + children).
    """
    pdf_path = _write_tmp(file_bytes, s3_key)
    database_url = os.environ['DATABASE_URL']
    conn = await asyncpg.connect(database_url)

    try:
        # 1. Insert documents record
        doc_id = await conn.fetchval("""
            INSERT INTO documents (source_uri, modality, source_type, material_id)
            VALUES ($1, 'pdf', $2, $3)
            RETURNING id::text
        """, s3_key, doc_type, material_id)

        # 2. Extract full markdown
        full_md = pymupdf4llm.to_markdown(pdf_path)
        pdf_doc = fitz.open(pdf_path)

        # 3. Create parent chunk
        first_page_png = _render_page_png(pdf_doc, 0)
        parent_visual_emb = await embed_visual(first_page_png)
        parent_text_emb   = await embed_text(full_md[:8000])  # Voyage-3.5 max input

        parent_vis_vec = _vec_str(parent_visual_emb)
        parent_id = await conn.fetchval("""
            INSERT INTO chunks
                (document_id, content, retrieval_type, embedding, chunk_index,
                 modal_meta, is_parent, source_type, course_id)
            VALUES ($1, $2, 'visual', $3::vector, -1, '{}', true, $4, $5)
            RETURNING id::text
        """, doc_id, full_md[:8000], parent_vis_vec, doc_type, course_id)

        # Also insert parent text embedding row
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

        # 5. Embed + insert child chunks (max 5 concurrent Voyage API calls)
        sem = asyncio.Semaphore(5)
        tasks = [
            _embed_and_insert_child(conn, doc_id, parent_id, spec,
                                    doc_type, course_id, sem, pdf_doc)
            for spec in chunk_specs
        ]
        await asyncio.gather(*tasks)

        pdf_doc.close()

        total = len(chunk_specs) + 1  # +1 for parent
        await conn.execute(
            "UPDATE material_embed_jobs SET chunks_created = $1 WHERE material_id = $2",
            total, material_id
        )
        return total

    finally:
        await conn.close()
        _cleanup_tmp(pdf_path)
