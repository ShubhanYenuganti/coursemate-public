# Citation Jump-to-Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chat citations clickable, opening the source PDF at the cited page in the sources side panel via a short-lived presigned URL + `#page=N`.

**Architecture:** A new access-checked `action=page_link` on `api/material.py` returns a presigned PDF URL + resolved page; `ChatTab` makes citations clickable and renders the PDF in the existing `sourcesPanel` iframe.

**Tech Stack:** Python serverless, S3 presigned URLs, React.

**Spec:** `docs/superpowers/specs/2026-06-10-citation-jump-to-page-design.md`

---

### Task 1: `page_link` endpoint with access check

**Files:**
- Modify: `api/material.py` (GET dispatch; uses existing `_s3_key_from_url`, `generate_download_presigned_url`, `Course.verify_access`)
- Test: `tests/test_material_page_link.py`

- [ ] **Step 1: Write the failing test (pure access/resolve helper)**

Extract the decision into a testable `resolve_page_link(material, user_id, page, verify_access, presign)`:

```python
# tests/test_material_page_link.py
from api.material import resolve_page_link

def test_denies_without_access():
    status, payload = resolve_page_link(
        material={'id': 1, 'course_id': 7, 'file_url': 's3://b/k.pdf'},
        user_id=9, page=14,
        verify_access=lambda c, u: False, presign=lambda key: 'URL')
    assert status == 403

def test_returns_presigned_url_and_page():
    status, payload = resolve_page_link(
        material={'id': 1, 'course_id': 7, 'file_url': 's3://b/k.pdf'},
        user_id=9, page=14,
        verify_access=lambda c, u: True, presign=lambda key: 'https://signed')
    assert status == 200 and payload['url'] == 'https://signed' and payload['page'] == 14

def test_rejects_generated_artifact():
    status, payload = resolve_page_link(
        material={'id': 1, 'course_id': 7, 'file_url': 'report://generation/42'},
        user_id=9, page=1,
        verify_access=lambda c, u: True, presign=lambda key: 'X')
    assert status == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_material_page_link.py -v` — FAIL.

- [ ] **Step 3: Implement helper + GET branch**

```python
def resolve_page_link(material, user_id, page, verify_access, presign):
    if not material:
        return 404, {"error": "Material not found"}
    file_url = material.get("file_url", "")
    if "://" in file_url and not file_url.lower().endswith(".pdf") and file_url.split("://", 1)[0] not in ("s3", "https", "http"):
        return 400, {"error": "Material has no viewable PDF"}
    if not verify_access(material["course_id"], user_id):
        return 403, {"error": "Access denied"}
    key = _s3_key_from_url(file_url)
    url = presign(key)
    return 200, {"url": url, "page": page, "expires_in": 300}
```

Wire `action == 'page_link'` into the GET dispatch:

```python
material = Material.get_by_id(int(params_get('material_id')))
status, payload = resolve_page_link(
    material, user["id"], int(params_get('page') or 1),
    Course.verify_access, generate_download_presigned_url)
send_json(self, status, payload)
```

Match `params_get` and `generate_download_presigned_url`'s signature to this file's existing usage
(it's already imported at the top per `api/material.py:28`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_material_page_link.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/material.py tests/test_material_page_link.py
git commit -m "feat: add access-checked material page_link presigned endpoint"
```

---

### Task 2: Clickable citations open the PDF in the sources panel

**Files:**
- Modify: `src/ChatTab.jsx` (citation markers + `sourcesPanel`)

- [ ] **Step 1: Map a citation click to {material_id, page}**

Where citations/sources are rendered (search `sourcesPanel` and the citation marker rendering), give
each citation an onClick that resolves its `material_id` and first cited `page` from the message's
grounding/sources object.

- [ ] **Step 2: Fetch the link and render the PDF**

```jsx
async function openCitation(materialId, page) {
  const res = await fetch(`/api/material?action=page_link&material_id=${materialId}&page=${page}`, { credentials: 'include' });
  const data = await res.json();
  if (!res.ok) return;
  setSourcesPanel({ open: true, pdfUrl: `${data.url}#page=${data.page}`, page: data.page });
}
```

In the sources panel render, when `pdfUrl` is set:

```jsx
<div className="text-xs text-gray-500 mb-1">Source — page {sourcesPanel.page}
  <a href={sourcesPanel.pdfUrl} target="_blank" rel="noreferrer" className="ml-2 underline">Open in new tab</a>
</div>
<iframe src={sourcesPanel.pdfUrl} title="source page" className="w-full h-[70vh] rounded border border-gray-200" />
```

Extend the existing `sourcesPanel` state object with `pdfUrl`/`page` (it already carries `open`).

- [ ] **Step 3: Manually verify**

Run: `npm run dev`. Ask a grounded question, click a citation → the source PDF opens at the cited page
in the side panel; "Open in new tab" works; a non-PDF (generated) material citation degrades
gracefully (no broken panel).

- [ ] **Step 4: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat: clickable citations open source PDF at the cited page"
```

---

## Self-Review

- **Spec coverage:** access-checked presigned `page_link` (T1), clickable citations + iframe panel +
  new-tab fallback (T2). ✓
- **Security:** `resolve_page_link` denies without `verify_access` and refuses generated-artifact
  URLs — citations cannot become an open file proxy. ✓
- **Reuse:** uses the already-imported `_s3_key_from_url` / `generate_download_presigned_url` and the
  existing `sourcesPanel` state rather than new infra. ✓
