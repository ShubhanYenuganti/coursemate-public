# Richer Ingestion (YouTube / URL / LMS) — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 3.3
**Scope:** Add new content sources beyond Notion/Drive. v1: YouTube lectures + arbitrary web URLs. Canvas/LMS is a documented phase 2. Reuses the existing material→S3→embed pipeline.

## Problem

Ingestion today is limited to Notion and Google Drive. Students also learn from YouTube lectures,
web articles, and their LMS (Canvas). The provider abstraction (`api/services/providers/`,
`lambda/integration_poller`) and the material pipeline (fetch → PDF → S3 → materials row → embed job)
make new sources a natural extension — but none exist.

## Goal

A student can paste a **YouTube URL** or a **web article URL** and have it ingested as a course
material: transcript/article text → PDF → S3 → indexed exactly like a Drive/Notion file, so chat,
flashcards, quizzes, and reports work over it. Canvas sync is scoped as phase 2.

## Decisions

1. **Reuse the material pipeline; add fetchers, not a new pipeline.** Each new source produces the
   same artifact the existing pipeline expects: a PDF in S3 + a `materials` row that triggers an
   embed/index job. We add *fetchers*, not a parallel ingestion stack.
2. **One new endpoint `action=ingest_url`** on `api/material.py` that dispatches by URL type
   (YouTube vs generic web), mirroring how `graphify add` / the README's ingestion classifies URLs.
3. **YouTube = captions/transcript → PDF.** Pull the transcript (captions API / `yt-dlp` subtitle
   extraction in a Lambda that already has heavier deps; the Vercel function stays light and enqueues
   the work). Render the transcript to a PDF with ReportLab — the same builder Notion already uses
   (`api/services/providers/notion.py` → ReportLab path).
4. **Web URL = readable text → PDF.** Fetch + extract main content (readability/html2text) → PDF.
5. **Pure URL classifier** `classify_source_url(url)` → `youtube | web | unsupported` is the TDD core.
6. **Heavy fetching runs in a Lambda**, not the Vercel request, to keep request latency and bundle
   size bounded (consistent with how embedding/poller work is offloaded). The endpoint validates +
   enqueues; a worker fetches, builds the PDF, uploads, and inserts the material.
7. **Canvas/LMS is phase 2** as a full provider under `api/services/providers/canvas.py` +
   OAuth/token like Notion/Drive, plus poller integration — too large for v1, documented here.

## URL classifier — `api/services/ingest_url.py`

```python
import re

_YT = re.compile(r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)", re.I)

def classify_source_url(url: str) -> str:
    if not url or not re.match(r"^https?://", url, re.I):
        return "unsupported"
    if _YT.search(url):
        return "youtube"
    return "web"
```

## API — `api/material.py` (`action=ingest_url`)

`POST /api/material` body `{ action: "ingest_url", course_id, url, doc_type }`:
- auth + access check on the course,
- `kind = classify_source_url(url)`; `unsupported` → 400,
- create a placeholder `materials` row (like the existing placeholder-URL flow at
  `api/material.py:261`) marked `pending`,
- enqueue an ingestion job (SQS, same shape as other async work) carrying `{material_id, url, kind}`,
- return `202` with the material id; the existing sync-status UI (sync-transparency item) shows
  `pending → syncing → synced`.

## Worker — `lambda/url_ingest/` (new)

Consumes the ingestion job:
1. `youtube`: fetch transcript (yt-dlp subtitles); join into text.
2. `web`: fetch + extract readable text.
3. Render text → PDF (ReportLab; reuse the Notion PDF builder).
4. Upload PDF to S3 at the material's key; update the `materials` row (file_url, title, synced).
5. Enqueue the embed/index job (same path reingest uses).
On failure, set the material's sync status to `failed` with the reason (consumed by the
sync-transparency UI).

## Frontend — `src/MaterialsPage.jsx`

- Add an "Add from URL" input alongside the existing upload/connect options: paste a YouTube or
  article URL, pick a `doc_type`, submit → POST `ingest_url`. The material appears immediately with a
  `pending` status pill (from the sync-transparency item).

## Phase 2 — Canvas/LMS (documented, not built in v1)

- New provider `api/services/providers/canvas.py` with OAuth + token storage (mirror Notion/Drive).
- Poller integration to list course files/pages and ingest changed items.
- Same artifact contract (PDF/text → S3 → materials → embed).

## Verification

- pytest: `classify_source_url` (youtube variants, web, unsupported, non-http); `ingest_url` endpoint
  validates access + classifies + enqueues (mock the queue).
- Manual: paste a YouTube lecture URL → material appears `pending`, then `synced`; chat answers cite
  its transcript pages. Repeat with a web article URL.
