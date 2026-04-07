"""
Notion source point handler for integration_poller.

sync_source_point(source_point, token):
  - Queries the Notion database for pages edited since last_synced_at
  - Converts each page to PDF via reportlab
  - Uploads to S3 and upserts into `materials`
  - Triggers the embed_materials Step Function
  - Updates last_synced_at on success
"""
import io
import json
import os
from datetime import datetime, timezone

import boto3
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage, Paragraph, SimpleDocTemplate, Spacer,
)

from db import get_db

NOTION_API_BASE = 'https://api.notion.com/v1'
NOTION_VERSION = '2022-06-28'

s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sfn = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

BUCKET = os.environ.get('AWS_S3_BUCKET_NAME', '')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', '')


# ─── Notion API helpers ──────────────────────────────────────────────────────

def _notion_get(path, token, params=None):
    resp = requests.get(
        f'{NOTION_API_BASE}/{path}',
        headers={
            'Authorization': f'Bearer {token}',
            'Notion-Version': NOTION_VERSION,
        },
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _notion_post(path, token, body):
    resp = requests.post(
        f'{NOTION_API_BASE}/{path}',
        headers={
            'Authorization': f'Bearer {token}',
            'Notion-Version': NOTION_VERSION,
            'Content-Type': 'application/json',
        },
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_all_blocks(page_id, token):
    """Fetch all blocks for a page, following pagination."""
    blocks = []
    cursor = None
    while True:
        params = {'page_size': 100}
        if cursor:
            params['start_cursor'] = cursor
        data = _notion_get(f'blocks/{page_id}/children', token, params)
        blocks.extend(data.get('results', []))
        if not data.get('has_more'):
            break
        cursor = data.get('next_cursor')
    return blocks


def _plain_text(rich_text_arr):
    """Extract plain text from a Notion rich text array."""
    return ''.join(t.get('plain_text', '') for t in (rich_text_arr or []))


# ─── PDF generation ──────────────────────────────────────────────────────────

def _notion_page_to_pdf(page_id, blocks, token):
    """
    Render Notion page blocks to PDF bytes using reportlab.
    Downloads image CDN URLs so the PDF is self-contained.
    """
    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, spaceAfter=12)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, spaceAfter=8)
    h3_style = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=12, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, spaceAfter=6)
    bullet_style = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10,
                                  spaceAfter=4, leftIndent=20, bulletIndent=10)

    story = []

    def _add_block(block, depth=0):
        btype = block.get('type', '')
        bdata = block.get(btype, {})

        if btype in ('heading_1', 'heading_2', 'heading_3'):
            text = _plain_text(bdata.get('rich_text', []))
            if not text:
                return
            style = h1_style if btype == 'heading_1' else (h2_style if btype == 'heading_2' else h3_style)
            story.append(Paragraph(text, style))

        elif btype == 'paragraph':
            text = _plain_text(bdata.get('rich_text', []))
            if text:
                story.append(Paragraph(text, body_style))

        elif btype in ('bulleted_list_item', 'numbered_list_item', 'to_do'):
            text = _plain_text(bdata.get('rich_text', []))
            if text:
                prefix = '• ' if btype == 'bulleted_list_item' else '– '
                story.append(Paragraph(f'{prefix}{text}', bullet_style))

        elif btype == 'toggle':
            text = _plain_text(bdata.get('rich_text', []))
            if text:
                story.append(Paragraph(f'▸ {text}', body_style))

        elif btype == 'quote':
            text = _plain_text(bdata.get('rich_text', []))
            if text:
                quote_style = ParagraphStyle('Quote', parent=body_style, leftIndent=30,
                                             textColor='#555555', fontName='Helvetica-Oblique')
                story.append(Paragraph(text, quote_style))

        elif btype == 'code':
            text = _plain_text(bdata.get('rich_text', []))
            if text:
                code_style = ParagraphStyle('Code', parent=body_style, fontName='Courier',
                                            fontSize=9, backColor='#f5f5f5', leftIndent=10)
                story.append(Paragraph(text.replace('\n', '<br/>'), code_style))

        elif btype == 'image':
            img_data = bdata
            url = None
            img_type = img_data.get('type')
            if img_type == 'external':
                url = img_data.get('external', {}).get('url')
            elif img_type == 'file':
                url = img_data.get('file', {}).get('url')

            if url:
                try:
                    img_resp = requests.get(url, timeout=20)
                    img_resp.raise_for_status()
                    img_bytes = io.BytesIO(img_resp.content)
                    rl_img = RLImage(img_bytes, width=14 * cm, height=10 * cm,
                                     kind='proportional')
                    story.append(rl_img)
                    story.append(Spacer(1, 6))
                except Exception as e:
                    print(f'[notion_handler] Failed to download image {url}: {e}')

        elif btype == 'divider':
            story.append(Spacer(1, 12))

        # Recurse into children for toggle, column, etc.
        if block.get('has_children'):
            try:
                child_blocks = _fetch_all_blocks(block['id'], token)
                for child in child_blocks:
                    _add_block(child, depth + 1)
            except Exception as e:
                print(f'[notion_handler] Failed to fetch children for block {block["id"]}: {e}')

    for block in blocks:
        _add_block(block)

    if not story:
        story.append(Paragraph('(empty page)', body_style))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─── Ingestion helpers ───────────────────────────────────────────────────────

def _upsert_material(user_id, course_id, page_id, page_title, last_edited_time):
    """
    Return (material_id, is_new). Creates or finds the materials row.
    Does NOT upload to S3 or trigger Step Function.
    """
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM materials WHERE external_id = %s AND source_type = 'notion'",
            (page_id,)
        ).fetchone()

        if existing:
            return existing['id'], False

        row = db.execute("""
            INSERT INTO materials (
                course_id, name, file_url, uploaded_by, file_type,
                visibility, source_type, external_id, external_last_edited
            )
            VALUES (%s, %s, %s, %s, 'application/pdf', 'private', 'notion', %s, %s)
            RETURNING id
        """, (
            course_id,
            page_title or f'Notion page {page_id}',
            f'notion/{page_id}.pdf',  # placeholder; updated after S3 upload
            user_id,
            page_id,
            last_edited_time,
        )).fetchone()
        material_id = row['id']

        # Link material to course
        db.execute(
            "INSERT INTO course_materials (course_id, material_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (course_id, material_id)
        )
        db.execute(
            "INSERT INTO material_embed_jobs (material_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (material_id,)
        )
    return material_id, True


def _delete_old_chunks(material_id):
    """Delete all embedding chunks for a material before re-ingestion."""
    with get_db() as db:
        db.execute("""
            DELETE FROM chunks
            WHERE document_id IN (
                SELECT id FROM documents WHERE material_id = %s
            )
        """, (material_id,))
        db.execute("DELETE FROM documents WHERE material_id = %s", (material_id,))


def _upload_pdf_to_s3(page_id, pdf_bytes):
    """Upload PDF bytes to S3 and return the S3 key."""
    s3_key = f'notion/{page_id}.pdf'
    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType='application/pdf',
    )
    return s3_key


def _update_material_after_upload(material_id, s3_key, last_edited_time):
    bucket = BUCKET
    region = os.environ.get('AWS_REGION', 'us-east-1')
    file_url = f'https://{bucket}.s3.{region}.amazonaws.com/{s3_key}'
    with get_db() as db:
        db.execute("""
            UPDATE materials
            SET file_url = %s, external_last_edited = %s
            WHERE id = %s
        """, (file_url, last_edited_time, material_id))


def _trigger_embed(s3_key):
    if STATE_MACHINE_ARN:
        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps({'s3_key': s3_key, 'cursor': 0}),
        )


# ─── Main entry point ────────────────────────────────────────────────────────

def sync_source_point(source_point: dict, token: str):
    """
    Sync all new/updated pages from the Notion database described by source_point.
    Updates last_synced_at on the source_point row after completion.
    """
    db_id = source_point['external_id']
    user_id = source_point['user_id']
    course_id = source_point['course_id']
    last_synced = source_point.get('last_synced_at')

    # Query Notion database for recently edited pages
    filter_body = {}
    if last_synced:
        if isinstance(last_synced, datetime):
            last_synced_str = last_synced.replace(tzinfo=timezone.utc).isoformat()
        else:
            last_synced_str = str(last_synced)
        filter_body = {
            'filter': {
                'timestamp': 'last_edited_time',
                'last_edited_time': {'on_or_after': last_synced_str},
            }
        }

    all_pages = []
    cursor = None
    while True:
        body = {**filter_body, 'page_size': 100}
        if cursor:
            body['start_cursor'] = cursor
        data = _notion_post(f'databases/{db_id}/query', token, body)
        all_pages.extend(data.get('results', []))
        if not data.get('has_more'):
            break
        cursor = data.get('next_cursor')

    for page in all_pages:
        page_id = page['id']
        last_edited_time = page.get('last_edited_time', '')

        # Determine title from page properties
        title = ''
        props = page.get('properties', {})
        for prop in props.values():
            if prop.get('type') == 'title':
                title = _plain_text(prop.get('title', []))
                break

        try:
            material_id, is_new = _upsert_material(
                user_id, course_id, page_id, title, last_edited_time
            )

            # Fetch all blocks for this page
            blocks = _fetch_all_blocks(page_id, token)

            if not is_new:
                # Updated page: clear stale embeddings before re-ingestion
                _delete_old_chunks(material_id)
                # Remove old S3 PDF
                try:
                    s3.delete_object(Bucket=BUCKET, Key=f'notion/{page_id}.pdf')
                except Exception:
                    pass  # File may not exist yet

            pdf_bytes = _notion_page_to_pdf(page_id, blocks, token)
            s3_key = _upload_pdf_to_s3(page_id, pdf_bytes)
            _update_material_after_upload(material_id, s3_key, last_edited_time)
            _trigger_embed(s3_key)

        except Exception as exc:
            print(f'[notion_handler] Failed to ingest page {page_id}: {exc}')
            # Continue with remaining pages

    # Update last_synced_at for this source point
    with get_db() as db:
        db.execute(
            "UPDATE integration_source_points SET last_synced_at = CURRENT_TIMESTAMP WHERE id = %s",
            (source_point['id'],)
        )
