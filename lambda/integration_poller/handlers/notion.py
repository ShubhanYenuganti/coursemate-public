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
    Return (material_id, is_new). Creates or finds the materials row.
    Does NOT upload to S3 or trigger Step Function.
    """
    with get_db() as db:
        existing = db.execute(
            "SELECT id, file_url, file_type FROM materials WHERE external_id = %s AND source_type = 'notion'",
            (page_id,),
        ).fetchone()

        if existing:
            # If the S3 upload previously failed, file_url is still the placeholder path.
            # Treat as new so the caller re-runs the upload + embed.
            placeholder = f"notion/{page_id}.pdf"
            existing_url = existing.get("file_url") or ""
            existing_file_type = existing.get("file_type")
            needs_reingest = (
                not existing_url
                or existing_url == placeholder
                or existing_url.startswith("notion/")
                or not existing_url.startswith("https://")
            )
            if existing_file_type != "application/pdf":
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
            if needs_reingest:
                print(
                    f"[notion_handler] Existing material requires reingest "
                    f"page={page_id} material_id={existing['id']} file_url={existing_url!r}"
                )
                return existing["id"], True
            return existing["id"], False

        row = db.execute(
            """
            INSERT INTO materials (
                course_id, name, file_url, uploaded_by, file_type,
                visibility, source_type, external_id, external_last_edited,
                outsourced_url, sync, integration_source_point_id
            )
            VALUES (%s, %s, %s, %s, 'application/pdf', 'private', 'notion', %s, %s, %s, true, %s)
            RETURNING id
        """,
            (
                course_id,
                page_title or f"Notion page {page_id}",
                f"notion/{page_id}.pdf",  # placeholder; updated after S3 upload
                user_id,
                page_id,
                last_edited_time,
                outsourced_url,
                source_point_id,
            ),
        ).fetchone()
        material_id = row["id"]

        # Link material to course via the material_ids JSONB array on courses
        db.execute(
            """
            UPDATE courses
            SET material_ids = material_ids || %s::jsonb
            WHERE id = %s
              AND NOT material_ids @> %s::jsonb
            """,
            (json.dumps([material_id]), course_id, json.dumps([material_id])),
        )
    return material_id, True


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
            SET file_url = %s, external_last_edited = %s
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


def sync_source_point(source_point: dict, token: str, force_full_sync: bool = False):
    """
    Sync all new/updated pages from the Notion database described by source_point.
    Updates last_synced_at on the source_point row after completion.
    """
    data_source_id = source_point["external_id"]
    user_id = source_point["user_id"]
    course_id = source_point["course_id"]
    last_synced = source_point.get("last_synced_at")
    print(
        f"[notion_handler] Starting sync source_point_id={source_point.get('id')} "
        f"data_source_id={data_source_id} course_id={course_id} user_id={user_id} "
        f"last_synced_at={last_synced} force_full_sync={force_full_sync} "
        f"bucket={BUCKET!r} has_state_machine={bool(STATE_MACHINE_ARN)}"
    )

    # Query Notion data source for recently edited pages
    filter_body = {}
    if last_synced and not force_full_sync:
        if isinstance(last_synced, datetime):
            last_synced_str = last_synced.replace(tzinfo=timezone.utc).isoformat()
        else:
            last_synced_str = str(last_synced)
        filter_body = {
            "filter": {
                "timestamp": "last_edited_time",
                "last_edited_time": {"on_or_after": last_synced_str},
            }
        }

    all_pages = []
    cursor = None
    while True:
        body = {**filter_body, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _notion_post(f"data_sources/{data_source_id}/query", token, body)
        all_pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    if filter_body and not all_pages:
        print(
            f"[notion_handler] Filtered query returned 0 pages for source_point_id={source_point.get('id')}; "
            f"retrying with full sync to catch initial import gaps"
        )
        cursor = None
        while True:
            body = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            data = _notion_post(f"data_sources/{data_source_id}/query", token, body)
            all_pages.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    # Also retry any pages from this database whose S3 upload previously failed
    # (file_url still holds the placeholder path, meaning embed never ran).
    with get_db() as db:
        stuck = db.execute(
            """
            SELECT external_id FROM materials
            WHERE course_id = %s
              AND source_type = 'notion'
              AND sync IS DISTINCT FROM false
              AND (
                  file_url IS NULL
                  OR file_url = ''
                  OR file_url LIKE 'notion/%%.pdf'
                  OR file_url NOT LIKE 'https://%%'
              )
            """,
            (course_id,),
        ).fetchall()
    stuck_ids = {r["external_id"] for r in stuck}
    print(
        f"[notion_handler] Notion query complete source_point_id={source_point.get('id')} "
        f"pages={len(all_pages)} stuck_pages={len(stuck_ids)}"
    )

    # Batch-query sync state for all discovered pages before any conversion work.
    # sync=False → page is explicitly excluded; skip without touching Notion API.
    # Missing row → new page, treat as sync=True (proceed with ingestion).
    current_page_id_list = [p["id"] for p in all_pages]
    with get_db() as db:
        sync_rows = db.execute(
            """
            SELECT external_id, sync FROM materials
            WHERE external_id = ANY(%s) AND course_id = %s AND source_type = 'notion'
            """,
            (current_page_id_list, course_id),
        ).fetchall()
    sync_lookup = {r["external_id"]: r["sync"] for r in sync_rows}

    # If a stuck page isn't already in all_pages, fetch it from Notion and append it.
    seen_ids = {p["id"] for p in all_pages}
    for stuck_id in stuck_ids - seen_ids:
        try:
            page = _notion_get(f"pages/{stuck_id}", token)
            all_pages.append(page)
        except Exception as exc:
            print(f"[notion_handler] Could not re-fetch stuck page {stuck_id}: {exc}")

    for page in all_pages:
        page_id = page["id"]
        last_edited_time = page.get("last_edited_time", "")

        # Determine title from page properties
        title = ""
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title = _plain_text(prop.get("title", []))
                break

        # Sync gate: skip pages explicitly excluded by the user (sync=False).
        # Pages with no row yet (not in sync_lookup) are new and should proceed.
        if sync_lookup.get(page_id) is False:
            print(f"[notion_handler] Skipping sync=false page={page_id}")
            continue

        try:
            print(f"[notion_handler] Ingesting page={page_id} title={title!r}")
            material_id, is_new = _upsert_material(
                user_id,
                course_id,
                source_point["id"],
                page_id,
                title,
                last_edited_time,
                outsourced_url=page.get("url"),
            )

            # Fetch all blocks for this page
            blocks = _fetch_all_blocks(page_id, token)

            if not is_new:
                # Updated page: clear stale embeddings before re-ingestion
                _delete_old_chunks(material_id)
                # Remove old S3 PDF
                try:
                    s3.delete_object(Bucket=BUCKET, Key=f"notion/{page_id}.pdf")
                except Exception:
                    pass  # File may not exist yet

            pdf_bytes = _notion_page_to_pdf(page_id, blocks, token)
            s3_key = _upload_pdf_to_s3(page_id, pdf_bytes)
            _update_material_after_upload(material_id, s3_key, last_edited_time)
            _enqueue_embed_job(material_id)
            _trigger_embed(s3_key)

        except Exception as exc:
            print(f"[notion_handler] Failed to ingest page={page_id}: {exc}")
            print(traceback.format_exc())
            # Continue with remaining pages

    # Update last_synced_at for this source point
    with get_db() as db:
        db.execute(
            "UPDATE integration_source_points SET last_synced_at = CURRENT_TIMESTAMP WHERE id = %s",
            (source_point["id"],),
        )
    print(
        f"[notion_handler] Sync complete source_point_id={source_point.get('id')} pages_processed={len(all_pages)}"
    )
