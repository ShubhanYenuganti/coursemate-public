import asyncio
import logging
import os
import re
import tempfile

import asyncpg
import fitz
import pymupdf4llm

from builders import route_builder
from db import (
    store_course_index,
    store_metadata_tags,
    store_page_index,
    store_page_texts,
)
from llm_client import (
    build_doc_summary_prompt,
    build_metadata_tags_prompt,
    build_node_keywords_prompt,
    build_node_summary_prompt,
    extract_keywords,
    extract_tags,
    get_api_key,
    summarize,
)
from relation_builder import build_course_relations

logger = logging.getLogger(__name__)
SUMMARY_CONCURRENCY = 4
_KEYWORD_STOPWORDS = {
    "and",
    "for",
    "from",
    "into",
    "the",
    "this",
    "with",
}


def _has_images(page: fitz.Page) -> bool:
    return bool(page.get_images(full=False))


def _resolve_section_names(page_rows: list[dict], material_index) -> list[dict]:
    """Stamp each page row with nearest section title and full breadcrumb path."""

    routing_node_types = {"section", "slide", "problem", "solution", "question"}

    def _walk(nodes, page_num: int, ancestors: list[str] | None = None) -> tuple[str, list[str]] | None:
        ancestors = ancestors or []
        for node in nodes:
            if node.start_page <= page_num <= node.end_page:
                node_type = getattr(node, "node_type", "section")
                if node_type in routing_node_types:
                    path = (node.parent_path or ancestors) + [node.title]
                    current = (node.title, path)
                else:
                    path = node.parent_path or ancestors
                    current = (path[-1], path) if path else None
                child_hit = _walk(node.nodes, page_num, path)
                return child_hit if child_hit else current
        return None

    result = []
    for row in page_rows:
        section = _walk(material_index.nodes, row["page_number"])
        if section:
            section_name, section_path = section
        else:
            section_name, section_path = None, []
        result.append({**row, "section_name": section_name, "section_path": section_path})
    return result


def _extract_pages(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    try:
        pages = []
        for i in range(len(doc)):
            page = doc[i]
            md = pymupdf4llm.to_markdown(doc, pages=[i]).strip()
            pages.append(
                {
                    "page_number": i + 1,
                    "text_content": md or None,
                    "has_images": _has_images(page),
                }
            )
        return pages
    finally:
        doc.close()


def _node_page_text(node, page_rows: dict) -> str:
    page_texts = []
    for page_num in range(node.start_page, node.end_page + 1):
        row = page_rows.get(page_num)
        if row and row["text_content"]:
            page_texts.append(row["text_content"])
    return "\n\n".join(page_texts)


def _fallback_node_keywords(title: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", title.lower())
    return [word for word in words if word not in _KEYWORD_STOPWORDS][:15]


async def _summarize_node(
    node,
    page_rows: dict,
    doc_type: str,
    api_key: str,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        combined = _node_page_text(node, page_rows)
        if not combined.strip():
            node.summary = ""
            return
        prompt = build_node_summary_prompt(doc_type, combined)
        try:
            node.summary = await asyncio.to_thread(summarize, prompt, api_key)
        except Exception as exc:
            logger.warning("Node summarization failed: %s", exc)
            node.summary = ""


async def _assign_node_keywords(
    node,
    page_rows: dict,
    doc_type: str,
    api_key: str,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        combined = _node_page_text(node, page_rows).strip()
        section_text = combined or node.title
        prompt = build_node_keywords_prompt(doc_type, section_text)
        try:
            keywords = await asyncio.to_thread(extract_keywords, prompt, api_key)
        except Exception as exc:
            logger.warning("Node keyword extraction failed: %s", exc)
            keywords = []
        node.keywords = keywords[:15] if keywords else _fallback_node_keywords(node.title)


async def _summarize_all_nodes(nodes, page_rows: dict, doc_type: str, api_key: str) -> None:
    sem = asyncio.Semaphore(SUMMARY_CONCURRENCY)
    tasks = []

    def _collect(current_nodes):
        for node in current_nodes:
            tasks.append(_summarize_node(node, page_rows, doc_type, api_key, sem))
            _collect(node.nodes)

    _collect(nodes)
    if tasks:
        await asyncio.gather(*tasks)


async def _assign_keywords_all_nodes(nodes, page_rows: dict, doc_type: str, api_key: str) -> None:
    sem = asyncio.Semaphore(SUMMARY_CONCURRENCY)
    tasks = []

    def _collect(current_nodes):
        for node in current_nodes:
            tasks.append(_assign_node_keywords(node, page_rows, doc_type, api_key, sem))
            _collect(node.nodes)

    _collect(nodes)
    if tasks:
        await asyncio.gather(*tasks)


async def index_document(
    material_id: int,
    course_id: int | None,
    s3_key: str,
    doc_type: str,
    material_title: str,
    file_bytes: bytes,
) -> None:
    db_url = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(db_url)
    pdf_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            pdf_path = tmp.name

        page_rows_list = _extract_pages(pdf_path)
        page_rows = {row["page_number"]: row for row in page_rows_list}

        build_fn = route_builder(doc_type)
        full_md = "\n\n---\n\n".join(row["text_content"] or "" for row in page_rows_list)
        material_index = build_fn(pdf_path, full_md)

        page_rows_list = _resolve_section_names(page_rows_list, material_index)
        page_rows = {row["page_number"]: row for row in page_rows_list}

        api_key = get_api_key()
        await _summarize_all_nodes(material_index.nodes, page_rows, doc_type, api_key)
        await _assign_keywords_all_nodes(material_index.nodes, page_rows, doc_type, api_key)

        node_titles = [node.title for node in material_index.nodes]
        doc_summary_prompt = build_doc_summary_prompt(material_title, doc_type, node_titles)
        try:
            doc_summary = await asyncio.to_thread(summarize, doc_summary_prompt, api_key)
        except Exception as exc:
            logger.warning("Doc summary failed: %s", exc)
            doc_summary = ""

        tags_prompt = build_metadata_tags_prompt(
            material_title, doc_type, doc_summary, node_titles
        )
        try:
            metadata_tags = await asyncio.to_thread(extract_tags, tags_prompt, api_key)
        except Exception as exc:
            logger.warning("Tag extraction failed: %s", exc)
            metadata_tags = []

        async with pool.acquire() as conn:
            await asyncio.to_thread(
                _sync_store,
                conn,
                material_id,
                course_id,
                material_title,
                doc_type,
                material_index,
                page_rows_list,
                doc_summary,
                metadata_tags,
            )

        if course_id:
            try:
                await build_course_relations(
                    db_url=os.environ["DATABASE_URL"],
                    course_id=course_id,
                    updated_material_id=material_id,
                    api_key=api_key,
                )
            except Exception as exc:
                logger.warning("Relation building failed: %s", exc)
    finally:
        await pool.close()
        if pdf_path:
            try:
                os.unlink(pdf_path)
            except FileNotFoundError:
                pass


def _sync_store(
    _async_conn,
    material_id,
    course_id,
    material_title,
    doc_type,
    material_index,
    page_rows_list,
    doc_summary,
    metadata_tags,
) -> None:
    import psycopg

    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as sync_conn:
        store_page_texts(sync_conn, material_id, page_rows_list)
        store_page_index(sync_conn, material_id, material_index.to_dict())
        if course_id:
            store_course_index(
                sync_conn,
                material_id,
                course_id,
                material_title,
                doc_type,
                material_index.page_count,
                doc_summary,
            )
            if metadata_tags:
                store_metadata_tags(sync_conn, course_id, material_id, metadata_tags)
        sync_conn.commit()
