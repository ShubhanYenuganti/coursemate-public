"""
Notion source point handler for integration_poller.

sync_source_point(source_point, token):
  - Queries the Notion database for pages edited since last_synced_at
  - Converts each page to PDF via reportlab
  - Uploads to S3 and upserts into `materials`
  - Triggers the embed_materials Step Function
  - Updates last_synced_at on success
"""

import html
import io
import json
import os
import traceback
from datetime import datetime, timezone

import boto3
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from db import get_db
from .utils import _needs_ingest

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"

s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
sfn = boto3.client(
    "stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1")
)

BUCKET = os.environ.get("AWS_S3_BUCKET_NAME", "")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")


# ─── Notion API helpers ──────────────────────────────────────────────────────


def _notion_get(path, token, params=None):
    resp = requests.get(
        f"{NOTION_API_BASE}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
        },
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _notion_post(path, token, body):
    resp = requests.post(
        f"{NOTION_API_BASE}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if not resp.ok:
        print(f"[notion] {resp.status_code} on {path}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


def _list_all_database_pages(database_id: str, token: str) -> list[dict]:
    """
    Return all pages in a Notion database.
    Each entry is the raw Notion page object (id, last_edited_time, properties, url).
    Paginates automatically via has_more / next_cursor.
    """
    pages = []
    start_cursor = None
    while True:
        body: dict = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        try:
            data = _notion_post(f"databases/{database_id}/query", token, body)
        except Exception as exc:
            print(f"[notion_handler] _list_all_database_pages error: {exc}")
            break
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
    return pages


def _fetch_all_blocks(page_id, token):
    """Fetch all blocks for a page, following pagination."""
    blocks = []
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        data = _notion_get(f"blocks/{page_id}/children", token, params)
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def _plain_text(rich_text_arr):
    """Extract plain text from a Notion rich text array."""
    return "".join(t.get("plain_text", "") for t in (rich_text_arr or []))


def _safe_text(text: str) -> str:
    """
    Sanitize text for ReportLab Paragraph parsing.
    Removes control characters that can break PDF generation.
    """
    cleaned = "".join(ch for ch in (text or "") if ch in ("\n", "\t") or ord(ch) >= 32)
    return html.escape(cleaned)


# ─── PDF generation ──────────────────────────────────────────────────────────


def _notion_page_to_pdf(page_id, blocks, token):
    """
    Render Notion page blocks to PDF bytes using reportlab.
    Downloads image CDN URLs so the PDF is self-contained.
    """
    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle(
        "H1", parent=styles["Heading1"], fontSize=18, spaceAfter=12
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=14, spaceAfter=8
    )
    h3_style = ParagraphStyle(
        "H3", parent=styles["Heading3"], fontSize=12, spaceAfter=6
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=10, spaceAfter=6
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        leftIndent=20,
        bulletIndent=10,
    )

    story = []
    skipped_blocks = 0

    def _append_paragraph(text, style, block):
        nonlocal skipped_blocks
        try:
            story.append(Paragraph(text, style))
        except Exception as exc:
            skipped_blocks += 1
            print(
                f"[notion_handler] Failed to render paragraph "
                f"page={page_id} block={block.get('id')} type={block.get('type')} "
                f"error={exc}"
            )

    def _add_block(block, depth=0):
        nonlocal skipped_blocks
        btype = block.get("type", "")
        bdata = block.get(btype, {})

        if btype in ("heading_1", "heading_2", "heading_3"):
            text = _plain_text(bdata.get("rich_text", []))
            if not text:
                return
            style = (
                h1_style
                if btype == "heading_1"
                else (h2_style if btype == "heading_2" else h3_style)
            )
            _append_paragraph(_safe_text(text), style, block)

        elif btype == "paragraph":
            text = _plain_text(bdata.get("rich_text", []))
            if text:
                _append_paragraph(_safe_text(text), body_style, block)

        elif btype in ("bulleted_list_item", "numbered_list_item", "to_do"):
            text = _plain_text(bdata.get("rich_text", []))
            if text:
                prefix = "• " if btype == "bulleted_list_item" else "– "
                _append_paragraph(f"{prefix}{_safe_text(text)}", bullet_style, block)

        elif btype == "toggle":
            text = _plain_text(bdata.get("rich_text", []))
            if text:
                _append_paragraph(f"▸ {_safe_text(text)}", body_style, block)

        elif btype == "quote":
            text = _plain_text(bdata.get("rich_text", []))
            if text:
                quote_style = ParagraphStyle(
                    "Quote",
                    parent=body_style,
                    leftIndent=30,
                    textColor="#555555",
                    fontName="Helvetica-Oblique",
                )
                _append_paragraph(_safe_text(text), quote_style, block)

        elif btype == "code":
            text = _plain_text(bdata.get("rich_text", []))
            if text:
                code_style = ParagraphStyle(
                    "Code",
                    parent=body_style,
                    fontName="Courier",
                    fontSize=9,
                    backColor="#f5f5f5",
                    leftIndent=10,
                )
                _append_paragraph(
                    _safe_text(text).replace("\n", "<br/>"), code_style, block
                )

        elif btype == "image":
            img_data = bdata
            url = None
            img_type = img_data.get("type")
            if img_type == "external":
                url = img_data.get("external", {}).get("url")
            elif img_type == "file":
                url = img_data.get("file", {}).get("url")

            if url:
                try:
                    img_resp = requests.get(url, timeout=20)
                    img_resp.raise_for_status()
                    img_bytes = io.BytesIO(img_resp.content)
                    rl_img = RLImage(
                        img_bytes, width=14 * cm, height=10 * cm, kind="proportional"
                    )
                    story.append(rl_img)
                    story.append(Spacer(1, 6))
                except Exception as e:
                    print(f"[notion_handler] Failed to download image {url}: {e}")

        elif btype == "divider":
            story.append(Spacer(1, 12))

        # Recurse into children for toggle, column, etc.
        if block.get("has_children"):
            try:
                child_blocks = _fetch_all_blocks(block["id"], token)
                for child in child_blocks:
                    _add_block(child, depth + 1)
            except Exception as e:
                skipped_blocks += 1
                print(
                    f"[notion_handler] Failed to fetch children "
                    f"page={page_id} block={block['id']}: {e}"
                )

    for block in blocks:
        _add_block(block)

    if not story:
        story.append(Paragraph("(empty page)", body_style))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    try:
        doc.build(story)
    except Exception as exc:
        print(
            f"[notion_handler] PDF build failed page={page_id} "
            f"block_count={len(blocks)} story_len={len(story)} skipped={skipped_blocks}: {exc}"
        )
        raise
    buf.seek(0)
    print(
        f"[notion_handler] PDF built page={page_id} bytes={buf.getbuffer().nbytes} "
        f"block_count={len(blocks)} skipped_blocks={skipped_blocks}"
    )
    return buf.read()


# ─── Ingestion helpers ───────────────────────────────────────────────────────


def _register_new_material(
    user_id, course_id, source_point_id, page_id, page_title, outsourced_url=None
) -> int | None:
    """
    INSERT a newly discovered Notion page into materials with sync=TRUE.
    Uses ON CONFLICT DO NOTHING so a race with bulk_upsert_sync is safe.
    Returns the new material_id, or None if the row already existed.
    """
    placeholder_url = f'notion/{page_id}.pdf'
    with get_db() as db:
        row = db.execute(
            """
            INSERT INTO materials
                (course_id, name, file_url, uploaded_by, file_type, source_type,
                 external_id, integration_source_point_id, sync, doc_type, outsourced_url)
            VALUES (%s, %s, %s, %s, 'application/pdf', 'notion', %s, %s, TRUE, 'general', %s)
            ON CONFLICT (external_id, course_id) DO NOTHING
            RETURNING id
            """,
            (course_id, page_title or page_id, placeholder_url, user_id,
             page_id, source_point_id, outsourced_url),
        ).fetchone()
    if row:
        print(f'[notion_handler] Discovered new page page_id={page_id} title={page_title!r} → material_id={row["id"]}')
        return row['id']
    return None


def _upsert_material(
    user_id,
    course_id,
    source_point_id,
    page_id,
    page_title,
    last_edited_time,
    outsourced_url=None,
):
    """
    Return (material_id, needs_ingest).
    All materials are pre-registered via bulk_upsert_sync before the poller runs.
    Returns (id, False) if last_edited_time is unchanged — caller should check doc_type drift then skip.
    Returns (id, True) if last_edited_time has advanced since last ingest.
    Returns (None, False) if no materials row exists (should not happen in normal flow).
    """
    with get_db() as db:
        existing = db.execute(
            "SELECT id, file_type, external_last_edited FROM materials WHERE external_id = %s AND source_type = 'notion'",
            (page_id,),
        ).fetchone()

        if not existing:
            print(f"[notion_handler] No material row for page_id={page_id} — skipping")
            return None, False

        if existing.get("file_type") != "application/pdf":
            db.execute(
                "UPDATE materials SET file_type = 'application/pdf' WHERE id = %s",
                (existing["id"],),
            )
        db.execute(
            "UPDATE materials SET integration_source_point_id = %s WHERE id = %s",
            (source_point_id, existing["id"]),
        )
        if outsourced_url:
            db.execute(
                "UPDATE materials SET outsourced_url = %s WHERE id = %s",
                (outsourced_url, existing["id"]),
            )
        if not _needs_ingest(last_edited_time, existing.get("external_last_edited")):
            return existing["id"], False
        return existing["id"], True


def _doc_type_changed(material_id: int) -> bool:
    """Return True if materials.doc_type differs from the doc_type used in the last ingest.

    Compares materials.doc_type (current user setting) against documents.source_type
    (the doc_type that was active when chunks were last generated). Returns False if
    no documents row exists — no prior ingest means no drift to detect.
    """
    with get_db() as db:
        row = db.execute(
            """
            SELECT m.doc_type, d.source_type AS last_doc_type
            FROM materials m
            LEFT JOIN documents d ON d.material_id = m.id
            WHERE m.id = %s
            ORDER BY d.ingested_at DESC NULLS LAST
            LIMIT 1
            """,
            (material_id,),
        ).fetchone()
    if not row or not row.get("last_doc_type"):
        return False
    return row["doc_type"] != row["last_doc_type"]


def _delete_old_chunks(material_id):
    """Delete all embedding chunks for a material before re-ingestion."""
    with get_db() as db:
        db.execute(
            """
            DELETE FROM chunks
            WHERE document_id IN (
                SELECT id FROM documents WHERE material_id = %s
            )
        """,
            (material_id,),
        )
        db.execute("DELETE FROM documents WHERE material_id = %s", (material_id,))


def _upload_pdf_to_s3(page_id, pdf_bytes):
    """Upload PDF bytes to S3 and return the S3 key."""
    if not BUCKET:
        raise ValueError("AWS_S3_BUCKET_NAME is not set")
    s3_key = f"notion/{page_id}.pdf"
    print(
        f"[notion_handler] Uploading PDF to S3 bucket={BUCKET} key={s3_key} bytes={len(pdf_bytes)}"
    )
    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )
    return s3_key


def _update_material_after_upload(material_id, s3_key, last_edited_time):
    bucket = BUCKET
    region = os.environ.get("AWS_REGION", "us-east-1")
    file_url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    with get_db() as db:
        db.execute(
            """
            UPDATE materials
            SET file_url = %s, external_last_edited = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """,
            (file_url, last_edited_time, material_id),
        )
    print(
        f"[notion_handler] Updated material after upload material_id={material_id} file_url={file_url}"
    )


def _enqueue_embed_job(material_id):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO material_embed_jobs (material_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (material_id,),
        )
    inserted = cur.rowcount == 1
    print(
        f"[notion_handler] material_embed_jobs upsert material_id={material_id} "
        f"inserted={inserted}"
    )


def _trigger_embed(s3_key):
    if not STATE_MACHINE_ARN:
        print(
            f"[notion_handler] STATE_MACHINE_ARN not set, skipping embed trigger for key={s3_key}"
        )
        return
    print(
        f"[notion_handler] Triggering embed Step Function arn={STATE_MACHINE_ARN} key={s3_key}"
    )
    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps({"s3_key": s3_key, "cursor": 0}),
    )


# ─── Main entry point ────────────────────────────────────────────────────────


def sync_source_point(source_point: dict, token: str, force_full_sync: bool = False, external_ids: list | None = None):
    """
    Sync Notion pages described by source_point.

    When external_ids is provided (Sync Now path), only those page IDs are processed.
    When external_ids is None (background sweep), all sync=TRUE materials for this
    source point are fetched from the DB and processed.
    """
    user_id = source_point["user_id"]
    course_id = source_point["course_id"]
    source_point_id = source_point["id"]
    print(
        f"[notion_handler] Starting sync source_point_id={source_point_id} "
        f"course_id={course_id} user_id={user_id} "
        f"force_full_sync={force_full_sync} external_ids={external_ids} "
        f"bucket={BUCKET!r} has_state_machine={bool(STATE_MACHINE_ARN)}"
    )

    # Determine which page IDs to process
    if external_ids is not None:
        # Sync Now path: caller already knows which pages to process
        work_ids = external_ids
        print(f"[notion_handler] Sync Now path: processing {len(work_ids)} targeted page(s)")
    else:
        # ── Discovery sweep: find pages in the database not yet in the DB ─────
        database_id = source_point["external_id"]
        print(f"[notion_handler] Discovery sweep: listing database_id={database_id}")
        remote_pages = _list_all_database_pages(database_id, token)
        remote_ids = {p["id"] for p in remote_pages}

        with get_db() as db:
            known_rows = db.execute(
                "SELECT external_id FROM materials WHERE integration_source_point_id = %s",
                (source_point_id,),
            ).fetchall()
        known_ids = {r["external_id"] for r in known_rows}

        new_page_ids = remote_ids - known_ids
        if new_page_ids:
            print(f"[notion_handler] Discovery: found {len(new_page_ids)} new page(s)")
            remote_by_id = {p["id"]: p for p in remote_pages}
            for pid in new_page_ids:
                p = remote_by_id[pid]
                title = ""
                for prop in p.get("properties", {}).values():
                    if prop.get("type") == "title":
                        title = _plain_text(prop.get("title", []))
                        break
                _register_new_material(
                    user_id, course_id, source_point_id, pid, title,
                    outsourced_url=p.get("url")
                )
        else:
            print(f"[notion_handler] Discovery: no new pages found")
        # ── End discovery sweep ────────────────────────────────────────────────

        # Background sweep path: query DB for all sync=TRUE materials for this source point
        with get_db() as db:
            rows = db.execute(
                """
                SELECT external_id FROM materials
                WHERE integration_source_point_id = %s
                  AND sync = TRUE
                """,
                (source_point_id,)
            ).fetchall()
        work_ids = [r["external_id"] for r in rows]
        print(f"[notion_handler] Background sweep path: processing {len(work_ids)} sync=TRUE page(s) (includes {len(new_page_ids)} newly discovered)")

    # Process each page by fetching its metadata individually
    pages_processed = 0
    for page_id in work_ids:
        try:
            page = _notion_get(f"pages/{page_id}", token)
        except Exception as exc:
            print(f"[notion_handler] Skipping page_id={page_id}: fetch failed: {exc}")
            continue

        last_edited_time = page.get("last_edited_time", "")

        # Determine title from page properties
        title = ""
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title = _plain_text(prop.get("title", []))
                break

        try:
            material_id, needs_ingest = _upsert_material(
                user_id,
                course_id,
                source_point_id,
                page_id,
                title,
                last_edited_time,
                outsourced_url=page.get("url"),
            )

            if material_id is None:
                continue

            doc_type_drifted = (not needs_ingest and not force_full_sync
                                and _doc_type_changed(material_id))

            if not needs_ingest and not force_full_sync and not doc_type_drifted:
                print(f"[notion_handler] Skipping unchanged page={page_id} title={title!r}")
                if external_ids is not None:
                    with get_db() as db:
                        db.execute(
                            "UPDATE material_embed_jobs SET status = 'up_to_date' WHERE material_id = %s",
                            (material_id,)
                        )
                        db.execute(
                            "UPDATE materials SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (material_id,)
                        )
                continue

            if doc_type_drifted:
                print(f"[notion_handler] doc_type changed for page={page_id} title={title!r} — re-ingesting")

            print(f"[notion_handler] Ingesting page={page_id} title={title!r}")

            # Fetch all blocks for this page
            blocks = _fetch_all_blocks(page_id, token)

            if not needs_ingest:
                # force_full_sync or doc_type changed: clear stale embeddings before re-ingest
                _delete_old_chunks(material_id)
                try:
                    s3.delete_object(Bucket=BUCKET, Key=f"notion/{page_id}.pdf")
                except Exception:
                    pass

            pdf_bytes = _notion_page_to_pdf(page_id, blocks, token)
            s3_key = _upload_pdf_to_s3(page_id, pdf_bytes)
            _update_material_after_upload(material_id, s3_key, last_edited_time)
            _enqueue_embed_job(material_id)
            _trigger_embed(s3_key)
            pages_processed += 1

        except Exception as exc:
            print(f"[notion_handler] Failed to ingest page={page_id}: {exc}")
            print(traceback.format_exc())
            # Continue with remaining pages

    # Update last_synced_at for this source point
    with get_db() as db:
        db.execute(
            "UPDATE integration_source_points SET last_synced_at = CURRENT_TIMESTAMP WHERE id = %s",
            (source_point_id,),
        )
    print(
        f"[notion_handler] Sync complete source_point_id={source_point_id} "
        f"pages_in_work_list={len(work_ids)} pages_ingested={pages_processed}"
    )
