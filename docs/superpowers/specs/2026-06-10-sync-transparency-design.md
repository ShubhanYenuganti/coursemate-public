# Sync Transparency + Freshness — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 2.6
**Scope:** Per-file sync status + retry in `src/MaterialsPage.jsx` and a status API; push-based freshness (Drive Changes API / Notion) is a phase 2 within this item.

## Problem

The last five commits before the roadmap were all sync-robustness fixes; users clearly hit confusing
sync states. Today a material can be mid-sync, failed, or stale with no per-file signal in the UI,
and the EventBridge poller runs only ~every 2 hours, so edits feel stale.

## Goal

**Phase 1 (transparency):** every synced material shows a clear per-file status — `synced` /
`syncing` / `failed (reason)` / `unsupported` — with a per-file **Retry** button when failed.
**Phase 2 (freshness):** move from pure 2-hour polling toward push (Drive Changes watch channels,
Notion change detection) so edits propagate in minutes.

## Decisions

1. **Surface existing state first.** The poller already tracks job/material state (the recent fixes
   added cancel + reconcile + failure paths). Phase 1 is mostly *exposing* a `sync_status` +
   `sync_error` per material via the materials list API and rendering it — minimal new backend logic.
2. **Status is a small enum** computed from existing columns/job rows:
   `synced | syncing | failed | unsupported | pending`. A pure `derive_sync_status(material, job)`
   function is the TDD core.
3. **Retry re-enqueues the existing poller path** for that one `external_id` (the same invoked-sync
   route the "Sync Now" flow already uses), scoped to a single file.
4. **Phase 2 is additive and gated.** Drive watch channels / Notion polling-interval reduction land
   behind their own tasks; they do not change the Phase 1 contract. Keep the 2-hour EventBridge job
   as the backstop even after push lands.
5. **No schema change in Phase 1 if columns exist.** If `materials` already has a status/error
   column, reuse it; only add `sync_status`/`sync_error` columns if missing (verify first).

## Phase 1 — status derivation

`api/material.py` (or a small helper module):

```python
def derive_sync_status(material: dict, latest_job: dict | None) -> dict:
    if material.get("unsupported"):
        return {"status": "unsupported", "error": material.get("sync_error")}
    if latest_job and latest_job.get("status") in ("queued", "running"):
        return {"status": "syncing", "error": None}
    if latest_job and latest_job.get("status") == "failed":
        return {"status": "failed", "error": latest_job.get("error")}
    if material.get("last_synced_at"):
        return {"status": "synced", "error": None}
    return {"status": "pending", "error": None}
```

The materials list endpoint includes `sync` (status+error) per material.

## Frontend — `src/MaterialsPage.jsx`

- Render a status pill per material (color by status) and the error text on hover/expand for failed.
- A **Retry** button on `failed` materials calls a `POST /api/material action=retry_sync` with the
  `material_id`/`external_id`, which re-invokes the poller for just that file.

## Phase 2 — push freshness (separate tasks)

- **Drive:** register a Changes watch channel per connected folder; on webhook, enqueue the poller
  for changed files. Store channel id/expiry; renew before expiry.
- **Notion:** Notion has no per-page webhook; reduce the effective staleness by shortening the poll
  cadence for recently-active sources (adaptive interval) rather than a flat 2 hours.

## Verification

- pytest: `derive_sync_status` table (each enum branch); `retry_sync` re-invokes the poller for one
  file only.
- Manual: force a sync failure (e.g. unsupported file) → status pill shows `failed` with reason and a
  Retry button; retry transitions to `syncing` then `synced`.
- Phase 2 manual: edit a Drive doc → it re-syncs within minutes via the watch channel, not after 2h.
