# Richer Ingestion (YouTube / URL / LMS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let students ingest YouTube lectures and web articles as course materials through the existing material→S3→embed pipeline; document Canvas/LMS as phase 2.

**Architecture:** A pure URL classifier + an `ingest_url` endpoint that creates a placeholder material and enqueues an ingestion job; a new `url_ingest` Lambda fetches transcript/article text, renders to PDF (reusing the Notion ReportLab builder), uploads to S3, and triggers indexing. The materials UI gains an "Add from URL" input.

**Tech Stack:** Python serverless + Lambda, SQS, S3, ReportLab, yt-dlp, Neon Postgres, pytest, React.

**Spec:** `docs/superpowers/specs/2026-06-10-richer-ingestion-design.md`

---

### Task 1: Pure URL classifier

**Files:**
- Create: `api/services/ingest_url.py`
- Test: `tests/test_ingest_url.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_url.py
from api.services.ingest_url import classify_source_url

def test_youtube_variants():
    assert classify_source_url('https://www.youtube.com/watch?v=abc') == 'youtube'
    assert classify_source_url('https://youtu.be/abc') == 'youtube'
    assert classify_source_url('https://youtube.com/shorts/abc') == 'youtube'

def test_web():
    assert classify_source_url('https://example.com/article') == 'web'

def test_unsupported():
    assert classify_source_url('ftp://x') == 'unsupported'
    assert classify_source_url('') == 'unsupported'
    assert classify_source_url('not a url') == 'unsupported'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_url.py -v` — FAIL.

- [ ] **Step 3: Implement** (function from the spec into `api/services/ingest_url.py`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_url.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/ingest_url.py tests/test_ingest_url.py
git commit -m "feat: add pure source-URL classifier"
```

---

### Task 2: `ingest_url` endpoint — validate, placeholder, enqueue

**Files:**
- Modify: `api/material.py` (POST dispatch; reuse the placeholder-material flow ~line 261 and the SQS enqueue pattern used by other async work)
- Test: `tests/test_material_ingest_url.py`

- [ ] **Step 1: Write the failing test (pure decision helper)**

```python
# tests/test_material_ingest_url.py
from api.material import plan_url_ingest

def test_rejects_unsupported():
    status, payload = plan_url_ingest(course_id=7, url='ftp://x', has_access=True)
    assert status == 400

def test_denies_without_access():
    status, payload = plan_url_ingest(course_id=7, url='https://youtu.be/x', has_access=False)
    assert status == 403

def test_accepts_youtube():
    status, payload = plan_url_ingest(course_id=7, url='https://youtu.be/x', has_access=True)
    assert status == 202 and payload['kind'] == 'youtube'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_material_ingest_url.py -v` — FAIL.

- [ ] **Step 3: Implement helper + POST branch**

```python
from .services.ingest_url import classify_source_url   # + import branch

def plan_url_ingest(course_id, url, has_access):
    kind = classify_source_url(url)
    if kind == 'unsupported':
        return 400, {"error": "Unsupported URL"}
    if not has_access:
        return 403, {"error": "Access denied"}
    return 202, {"kind": kind}
```

Wire `action == 'ingest_url'` into `do_POST`:
- compute `has_access` via `Course.verify_access(course_id, user['id'])`,
- `status, payload = plan_url_ingest(course_id, url, has_access)`,
- on `202`: create a placeholder `materials` row (reuse the existing placeholder-URL insert near
  line 261, marked pending) to get a `material_id`, enqueue an ingestion SQS job
  `{material_id, url, kind, doc_type}` using the same SQS-send helper other handlers use, and return
  `{material_id, **payload}`,
- otherwise `send_json(self, status, payload)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_material_ingest_url.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/material.py tests/test_material_ingest_url.py
git commit -m "feat: add ingest_url endpoint to enqueue URL/YouTube ingestion"
```

---

### Task 3: `url_ingest` Lambda worker

**Files:**
- Create: `lambda/url_ingest/handler.py`, `lambda/url_ingest/requirements.txt`
- Test: `tests/test_url_ingest_worker.py`

- [ ] **Step 1: Write the failing test for text→PDF + dispatch**

```python
# tests/test_url_ingest_worker.py
import sys, types

def test_fetch_text_dispatches_by_kind(monkeypatch):
    sys.path.insert(0, 'lambda/url_ingest')
    import handler
    monkeypatch.setattr(handler, 'fetch_youtube_transcript', lambda url: 'YT TEXT')
    monkeypatch.setattr(handler, 'fetch_web_article', lambda url: 'WEB TEXT')
    assert handler.fetch_text('youtube', 'u') == 'YT TEXT'
    assert handler.fetch_text('web', 'u') == 'WEB TEXT'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_url_ingest_worker.py -v` — FAIL.

- [ ] **Step 3: Implement the worker**

`lambda/url_ingest/handler.py`:
- `fetch_text(kind, url)` dispatches to `fetch_youtube_transcript` (yt-dlp subtitle extraction) or
  `fetch_web_article` (requests + readability/html2text).
- Render the text to a PDF using ReportLab — reuse the Notion PDF rendering approach
  (`api/services/providers/notion.py`). Factor the text→PDF step so both Notion and url_ingest share
  it, or copy the minimal ReportLab block into the Lambda bundle.
- Upload the PDF to S3 at the material's key; update the `materials` row (file_url, title, set
  synced); enqueue the embed/index job (the same path "reset poller embed jobs on reingest" uses).
- On any failure, set the material's sync status to `failed` with the error (consumed by the
  sync-transparency UI).

`lambda/url_ingest/requirements.txt`: `yt-dlp`, `requests`, `readability-lxml` (or `html2text`),
`reportlab`, `psycopg[binary]`, `boto3`, `awslambdaric` (mirror sibling Lambda requirement files).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_url_ingest_worker.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add lambda/url_ingest tests/test_url_ingest_worker.py
git commit -m "feat: url_ingest Lambda for YouTube/web ingestion to PDF"
```

> Deployment note: wire the new SQS queue + Lambda trigger in the same infra the other workers use
> (this repo deploys Lambdas outside the request path). Document the queue name/env in the worker.

---

### Task 4: "Add from URL" in MaterialsPage

**Files:**
- Modify: `src/MaterialsPage.jsx`

- [ ] **Step 1: Add the URL input + doc_type and submit**

Near the existing upload/connect controls, add:

```jsx
<div className="flex gap-2">
  <input value={ingestUrl} onChange={(e) => setIngestUrl(e.target.value)}
         placeholder="Paste a YouTube or article URL…"
         className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm" />
  <button onClick={submitIngestUrl} className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm">Add</button>
</div>
```

```jsx
async function submitIngestUrl() {
  const res = await fetch('/api/material', {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ action: 'ingest_url', course_id: courseId, url: ingestUrl, doc_type: 'Reading' }),
  });
  if (res.ok) { setIngestUrl(''); /* refresh materials list */ }
}
```

The new material appears with a `pending` status pill (from the sync-transparency item; if that item
isn't shipped, it simply appears once synced).

- [ ] **Step 2: Manually verify**

Run: `npm run dev`. Paste a YouTube lecture URL → material appears and reaches `synced`; ask a chat
question answered from its transcript. Repeat with a web article URL.

- [ ] **Step 3: Commit**

```bash
git add src/MaterialsPage.jsx
git commit -m "feat: add-from-URL ingestion entry in MaterialsPage"
```

---

### Task 5 (Phase 2, documented): Canvas/LMS provider

**Files:** (not built in v1 — scoped for a future change)
- `api/services/providers/canvas.py` (OAuth + token storage mirroring Notion/Drive)
- `lambda/integration_poller/` (list + ingest changed Canvas files/pages)

- [ ] **Step 1: Spike only** — confirm Canvas API auth model and that the same artifact contract
  (PDF/text → S3 → materials → embed) holds. Do **not** build in this plan; open a follow-on change
  using the Notion/Drive provider + poller as the template.

---

## Self-Review

- **Spec coverage:** classifier (T1), endpoint enqueue (T2), worker fetch→PDF→S3→index (T3), UI
  entry (T4), Canvas scoped as phase-2 spike (T5). ✓
- **Reuse over rebuild:** every source produces the existing pipeline's artifact (PDF→S3→materials→
  embed); only fetchers are new. ✓
- **Honest scoping:** the heavy/uncertain parts (Lambda deploy wiring, yt-dlp specifics, Canvas auth)
  are called out as their own steps/spike rather than pretended-complete. ✓
