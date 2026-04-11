## Context

Both integration pollers (GDrive and Notion) follow the same flawed pattern: they query the external API broadly (all files in a folder / all pages in a database) and then post-filter against the materials table. The file selection the user made in the sync modal is discarded after `bulk_upsert_sync` writes to the DB. Two additional bugs compound this: GDrive compares `external_last_edited == modifiedTime` (equality, misses forced re-syncs) and Notion uses URL shape rather than timestamps to detect staleness, making "Sync Now" a silent no-op for already-ingested files.

## Goals / Non-Goals

**Goals:**
- Pollers derive their work list from the materials table (filtered to `sync=TRUE`) rather than broad external API scans
- "Sync Now" passes `external_ids` through the Lambda event so the poller processes only the explicitly selected files
- Both providers use the same `>` timestamp comparison for staleness detection
- Notion's staleness check uses `last_edited_time` (from `Notion-Version: 2026-03-11`) not URL shape
- When `_needs_ingest → False`, poller writes `embed_status = 'up_to_date'` to signal no changes to the frontend
- Background (EventBridge) sweeps continue to work without any event payload changes

**Non-Goals:**
- Automatic discovery of new files added to Drive/Notion after initial setup (user must explicitly add files via sync modal)
- Changing the embed pipeline, chunking, or S3 upload logic
- Schema changes to the materials table

## Decisions

### Decision: DB-driven work list, not external API listing

**Chosen**: Query `materials WHERE integration_source_point_id = {sp_id} AND sync = TRUE` to build the work list; then fetch fresh metadata per-ID from the external API.

**Alternative considered**: Keep external API listing, filter post-hoc. Rejected: wastes API quota on files the user deselected; requires an extra `sync_lookup` batch-SELECT to gate files; fundamentally ignores user intent.

**Why now**: This also removes `_list_folder_files` from the GDrive poller hot path and the `data_sources/{id}/query` call from the Notion poller, reducing external API surface.

---

### Decision: `external_ids` override in Lambda event for "Sync Now"

**Chosen**: `_trigger_poller` in `api/material.py` includes `external_ids` (sync=True files only) in the Lambda payload. When present, `sync_source_point` uses this list directly and skips the DB query.

**Alternative considered**: Always use the DB work list. Rejected: there is a race window between `bulk_upsert_sync` writing rows and the poller reading them. Passing `external_ids` explicitly closes this window and makes the causal link explicit.

---

### Decision: Unified `_needs_ingest(api_time, db_time) → bool` helper

**Chosen**: Parse both timestamps as timezone-aware `datetime` objects and return `api_time > db_time`. `None` / empty `db_time` → `True` (always ingest new files). Parse failure → `True` (safe default).

**Alternative considered**: Keep per-provider ad-hoc checks. Rejected: GDrive `==` misses forced re-syncs; Notion URL check is orthogonal to actual content freshness. A shared helper makes the behavior identical and testable.

Both providers already store `external_last_edited` in the materials row after upload. Both providers return ISO 8601 timestamps (`Z`-suffixed) from their APIs. `datetime.fromisoformat` after replacing `Z` → `+00:00` handles this correctly.

---

### Decision: Write `embed_status = 'up_to_date'` when no changes detected

**Chosen**: When `_needs_ingest → False` for a file in the sync list, issue `UPDATE material_embed_jobs SET status = 'up_to_date' WHERE material_id = {id}`. This gives the frontend a clear signal without a schema change.

**Alternative considered**: Frontend-only detection (infer "no changes" if status stays `'done'` quickly). Rejected: fragile; race between polling interval and sync latency makes this unreliable.

Only applies to files already in the sync list (i.e., triggered by "Sync Now" or a targeted background sweep). Background sweeps that skip a file for no-change will NOT write `'up_to_date'` — only those where the poller was explicitly asked to re-check a file.

---

### Decision: Remove Notion stuck-pages recovery block

**Chosen**: Delete the query that finds materials with placeholder `file_url` and retries them.

**Reason**: This block existed because the URL was the sole staleness signal — a placeholder meant "upload failed, retry." With `_needs_ingest`, a file whose upload failed has `external_last_edited = NULL`, so `_needs_ingest` returns `True` and it retries automatically on every sweep. The stuck-pages block is redundant.

---

### Decision: `_list_folder_files` stays in gdrive.py but is no longer called from the poller

The function is used by `api/gdrive.py` (sync modal file browser). It is not deleted — just removed from `sync_source_point`.

## Risks / Trade-offs

**New files added to Drive/Notion are not auto-discovered** → User must add them explicitly via the sync modal. This is acceptable given the selective ingestion model — files not in `materials` with `sync=TRUE` are intentionally excluded.

**Per-ID API calls increase request count for large source points** → Each file in the work list generates one API call (Drive `files.get` or Notion `pages.get`). For a source point with 50 files, this is 50 calls per sweep. Drive's rate limit is 1,000 req/100s per user; Notion is 3 req/s. At typical source point sizes (10–30 files) this is well within limits. Mitigated by the fact that the work list is bounded to `sync=TRUE` files only.

**`'up_to_date'` as embed_status requires frontend coordination** → The frontend must map `'up_to_date'` → no badge on page load (covered in the companion frontend change). If the frontend change is not deployed simultaneously, users see no badge where they previously saw nothing — no regression, just no new feature.

## Migration Plan

1. Deploy `api/material.py` change (`_trigger_poller` with `external_ids`) — backward compatible, handler ignores unknown event fields
2. Deploy updated Lambda (`integration_poller`) — the new `sync_source_point` signature accepts `external_ids=None` and falls back to DB query when absent, so EventBridge sweeps continue unaffected
3. No DB migration required
4. Rollback: redeploy previous Lambda version; revert `api/material.py`

## Open Questions

- Should background EventBridge sweeps also write `'up_to_date'` when a file is skipped, or only "Sync Now"–triggered runs? Current decision: only "Sync Now" (targeted runs), to avoid noise on materials that have never changed and never need to.
