# Citation Jump-to-Page — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 3.4
**Scope:** Make chat citations clickable to the exact source page — a presigned PDF deep-link rendered inline/side-panel. `api/material.py` (presigned URL), `src/ChatTab.jsx` sources panel.

## Problem

Citations already carry the material + page metadata (the PageIndex agent fetches via
`get_page_content(material_id, pages)` and the answer cites pages). But a citation is just text — the
student can't see the actual page. Groundedness is claimed, not shown. The infrastructure to show it
already exists: materials are PDFs in S3, and `api/material.py` has `generate_download_presigned_url`.

## Goal

Clicking a citation (or a sources-panel entry) opens the source PDF **at the cited page** — in a
side panel or new tab — so the student verifies the answer against the original.

## Decisions

1. **Presigned PDF + `#page=N` fragment.** Browsers' built-in PDF viewer honors the
   `...pdf#page=N` fragment. A new `action=page_link` on `api/material.py` returns a short-lived
   presigned URL for the material; the frontend appends `#page=<first cited page>`. Zero new
   rendering stack.
2. **Reuse existing grounding metadata.** The assistant message already exposes its sources (the
   sources panel — `sourcesPanel` state in `ChatTab.jsx`) with `material_id` + page(s). The citation
   click maps to `{material_id, page}` and requests the link.
3. **Access-checked.** `page_link` verifies the requesting user has access to the material's course
   (reuse `Course.verify_access`) before presigning — citations must not become an open file proxy.
4. **Side panel first, tab fallback.** Render the PDF in the existing sources side panel via an
   `<iframe>` to the presigned `#page=N` URL; provide an "Open in new tab" affordance for browsers
   that block PDF iframing.
5. **Page mapping caveat.** PageIndex page numbers must correspond to PDF page numbers. Where a
   material's stored pages already equal PDF pages, `#page=N` is exact; otherwise the link opens the
   PDF at the nearest mapped page. The endpoint returns the resolved page it used so the UI can label
   it.

## API — `api/material.py` (`action=page_link`)

`GET /api/material?action=page_link&material_id=88&page=14` →
```json
{ "url": "https://s3...presigned...pdf", "page": 14, "expires_in": 300 }
```
- Look up the material, `Course.verify_access(course_id, user_id)`.
- Build the S3 key via the existing `_s3_key_from_url(material.file_url)` and presign with
  `generate_download_presigned_url`.
- Return the URL + the resolved page; the frontend appends `#page=`.

Skip/clearly error for generated-artifact materials (e.g. `report://...` URLs) which have no PDF.

## Frontend — `src/ChatTab.jsx`

- Make inline citation markers and sources-panel rows clickable.
- On click: GET `page_link`, then set the sources panel to render
  `<iframe src={url + '#page=' + page} />` (the panel state `sourcesPanel` already exists), with an
  "Open in new tab" link.
- Show the resolved page number as a label.

## Verification

- pytest: `page_link` denies access when `verify_access` is false; returns a presigned URL + page for
  an accessible PDF material; rejects non-PDF (generated) materials.
- Manual: ask a question, click a citation → the source PDF opens at (or near) the cited page in the
  side panel; "Open in new tab" works.
