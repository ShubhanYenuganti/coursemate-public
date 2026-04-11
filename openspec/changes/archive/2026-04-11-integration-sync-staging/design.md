## Context

The integration poller (`lambda/integration_poller/`) currently detects files under a connected source point and immediately hands them off to the embed pipeline with no user gate. MaterialsPage has an upload modal used for manual uploads. The materials table has no sync-state column. Deletion of any material removes both the S3 object and the DB row unconditionally.

This change threads a user-controlled staging step into the integration flow: files are written to the DB with a `sync` flag before any embed work begins, giving users the ability to exclude specific files permanently without losing the record of them.
The staging UX is implemented as a standalone Sync Modal in `MaterialsPage` that temporarily replaces the Upload Modal during sync workflows.

## Goals / Non-Goals

**Goals:**
- Users can opt individual files out of ingestion at source-point connection time and again on any subsequent Sync Now.
- Opted-out files are never re-ingested on future poll cycles.
- Deleting a synced file tombstones it (sync = false) rather than removing the row, so the poller cannot re-discover it.
- Backward-compatible schema migration — existing material rows default to `sync = true`.

**Non-Goals:**
- Bulk enable/disable of an entire source point (existing `is_active` toggle covers that).
- Per-page staging for Notion export targets (export is push-only; no ingestion staging needed there).
- Offline/queued sync — the staging step is synchronous on Sync click.

## Decisions

### 1. Sync state is server-side, not client-side
**Decision**: `sync` is a boolean column on the `materials` table. Toggle state is local-only until Sync; then it is persisted per-row.

**Alternatives considered**:
- A separate `material_sync_overrides` table: more normalized but unnecessary complexity — the flag is a single scalar per material with no history requirement.
- `sync` on `integration_source_points`: would apply to all files in a folder at once, can't express per-file exclusions.

### 2. Sync uses a standalone modal in MaterialsPage and temporarily hides the Upload Modal
**Decision**: Introduce a dedicated Sync Modal in `MaterialsPage` for integration sync workflows. When sync starts (first-time source-point staging or Sync Now), the Upload Modal is hidden and replaced by the Sync Modal. Local React state holds toggles until the user clicks Sync.

**Rationale**: Sync workflows and manual uploads now have distinct UX contracts and progress semantics. A dedicated modal avoids overloading upload-specific controls and enables a sync-specific post-confirmation state (pending-files dropdown that shrinks as files pass poller handoff and enter embedding).

### 3. Poller sync check is a pre-ingestion DB lookup, applied to all provider handlers
**Decision**: Both `handlers/gdrive.py` and `handlers/notion.py` perform a batch `SELECT external_id, sync FROM materials WHERE external_id IN (...) AND course_id = ?` after listing files/pages but before any conversion work begins (Drive export/download for GDrive; block fetch and ReportLab PDF generation for Notion).

**Rationale**: Keeps the sync gate as early as possible — before the expensive provider API calls. Both handlers already operate file-by-file; a single batch lookup per poll cycle is a minimal addition to each.

**New-file rule**: If no row exists for a file or page, treat it as new and proceed with ingestion, inserting with `sync = true`. This preserves existing auto-ingest behavior for items added after initial staging.

**Notion placeholder edge case**: Notion creates a materials row with a placeholder `file_url` (`notion/<page_id>.pdf`) before S3 upload completes. The sync check must treat a placeholder row with `sync = true` as an incomplete ingest (retry), not as an opted-out file.

### 4. Delete behavior diverges on `integration_source_point_id` presence
**Decision**: The delete handler checks whether the material row has a non-null `integration_source_point_id`. If yes → tombstone (S3 delete + set `sync = false`). If no → full delete (existing behavior).

**Rationale**: Synced files need a tombstone so the poller's "new file" path doesn't re-ingest them on the next cycle. Normal materials have no such constraint.

### 5. Sync Now is launched from MaterialsPage and pre-populates toggles from provider list endpoints
**Decision**: Sync Now entrypoint lives in `MaterialsPage`. It calls provider list endpoints (`/api/gdrive?action=list_source_point_files` and `/api/notion?action=list_source_point_files`) that return each file with current `sync` (`null` if no row). The Sync Modal initializes toggles as: `null` or `true` → ON, `false` → OFF.

**Rationale**: Keeps sync controls colocated with material indexing/upload lifecycle UI. Reuses existing provider-specific file-list endpoints already implemented with pagination and sync cross-reference.

### 6. Post-confirmation sync state keeps Sync Modal visible until poller handoff completes
**Decision**: After user clicks Sync, the Sync Modal remains visible (Upload Modal remains hidden). The modal shows a pending-files dropdown initialized with selected `sync = true` files. As each file is observed to have passed poller handoff (material appears/updates in course materials and enters embed status progression), the dropdown list shrinks. When pending reaches zero, Sync Modal closes and Upload Modal is restored.

**Rationale**: Provides immediate, visible feedback that the selection has transitioned into backend processing and prevents UI mode ambiguity mid-sync.

### 7. API shape strategy: keep provider-specific endpoints; normalize in frontend
**Decision**: Do not introduce a unified `/api/integrations/source-points/<id>/files` endpoint in this change. Keep existing provider-specific endpoints:
- `/api/gdrive?action=list_source_point_files`
- `/api/notion?action=list_source_point_files`

Frontend (`MaterialsPage`) SHALL normalize both responses into a shared Sync Modal row model (at minimum: `external_id`, `name`, `mime_type`, `sync`, `source_type`) before rendering and before constructing bulk sync payloads.

**Rationale**: Existing provider endpoints are already deployed and paginated. Deferring backend unification avoids churn and risk in a partially completed change while still giving the UI a single internal contract.

## Risks / Trade-offs

- **Poll-cycle race**: A file toggled ON after the poller already scanned it in the current cycle won't be ingested until the next poll. Acceptable given typical poll intervals. → No mitigation needed.
- **Staging modal on very large folders**: Fetching 500+ files into the modal is plausible for large Drive folders. → Provider file-list endpoints SHALL return a maximum of 20 files per page. When a source point exceeds 20 files, the modal displays a paginator and the user stages files in pages of 20 before clicking Sync.
- **Sync Now partial update complexity**: Sync must upsert rows (update sync for existing rows, insert for new ones). A single bulk upsert query handles this cleanly with `ON CONFLICT (external_id, course_id) DO UPDATE SET sync = excluded.sync`.
- **Progress inference ambiguity**: Poller handoff completion is inferred from material list refreshes and embed status transitions rather than explicit poller acknowledgements. → Use deterministic pending-set logic keyed by `external_id` and remove items only after they appear in materials with matching source metadata.
- **Frontend normalization drift**: Provider-specific payloads may diverge over time. → Centralize mapping logic in a single frontend normalization adapter used by all Sync Modal entry paths.

## Migration Plan

1. ~~Run migration~~ — **done**. `sync BOOLEAN NOT NULL DEFAULT true` column exists; all existing rows verified as `sync = true`.
2. Deploy poller update (sync check gate in both `handlers/gdrive.py` and `handlers/notion.py`) — safe to deploy before the frontend; existing behavior is unchanged for all rows where `sync = true`.
3. Deploy frontend staging modal.
4. Rollback: if needed, drop the column and redeploy the poller without the sync check. No data integrity risk since `DEFAULT true` means everything was previously ingestible.

## Open Questions

- None outstanding.
