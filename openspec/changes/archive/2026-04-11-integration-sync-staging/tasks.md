## 2. API — Sync Field & Source Point Files Endpoint

- [x] 2.1 Update materials insert logic (in `api/materials.py` or equivalent) to accept and persist the `sync` field; default to `true` if not provided
- [x] 2.2 Add provider source-point files listing endpoints (`/api/gdrive?action=list_source_point_files` and `/api/notion?action=list_source_point_files`) that return files/pages cross-referenced with materials sync state, paginated at 20 per page (`?page=`), with each item including `sync` (`null` if no row exists)
- [x] 2.3 Add a bulk upsert endpoint (or extend the existing materials batch endpoint) that accepts a list of `{external_id, sync}` objects and performs `INSERT ... ON CONFLICT (external_id, course_id) DO UPDATE SET sync = excluded.sync`

## 3. Integration Poller — Sync Gate

- [x] 3.1 In `lambda/integration_poller/handlers/gdrive.py`, after listing files in the folder, batch-query `SELECT external_id, sync FROM materials WHERE external_id IN (...) AND course_id = ?`
- [x] 3.2 For each GDrive file: if `sync = false` → skip (no Drive export/download, no S3 upload, no embed enqueue); if row missing → treat as new, proceed with ingestion; if `sync = true` → proceed normally
- [x] 3.3 When inserting a new material row for a newly discovered GDrive file, set `sync = true`
- [x] 3.4 Verify the GDrive sync check executes before any Drive export or download call
- [x] 3.5 In `lambda/integration_poller/handlers/notion.py`, after querying the Notion database for pages, batch-query the same `sync` lookup before any block fetch or PDF generation
- [x] 3.6 For each Notion page: if `sync = false` → skip; if row missing → treat as new, proceed with ingestion; if `sync = true` (including placeholder `file_url` rows) → proceed with existing ingest/retry logic
- [x] 3.7 When inserting a new material row for a newly discovered Notion page, set `sync = true`

## 4. Frontend — Staging Modal in MaterialsPage

- [x] 4.1 Create a standalone Sync Modal in `MaterialsPage` (separate from Upload Modal) with per-file toggle controls defaulting to ON and paginated file browsing (20 per page)
- [x] 4.2 Add sync workflow view-state in `MaterialsPage` that hides Upload Modal and shows Sync Modal while sync workflow is active
- [x] 4.3 For initial source-point staging and Sync Now, fetch files from provider list endpoints (`/api/gdrive?action=list_source_point_files` or `/api/notion?action=list_source_point_files`) and initialize toggles from `sync` (`null`/`true` ON, `false` OFF)
- [x] 4.3.1 Add a frontend normalization adapter that maps provider-specific file list responses to a shared Sync Modal row shape (`external_id`, `name`, `mime_type`, `sync`, `source_type`)
- [x] 4.4 Hold toggle state only in local React state (no DB writes on toggle); on Sync click call `bulk_upsert_sync` with `{external_id, sync}` rows
- [x] 4.5 After Sync click, keep Sync Modal visible and keep Upload Modal hidden; switch modal to progress mode with a pending-files dropdown seeded from selected `sync=true` files
- [x] 4.6 Shrink the pending-files dropdown as files pass poller handoff and transition into embed processing (based on refreshed materials/sync polling state)
- [x] 4.7 Auto-close Sync Modal and restore Upload Modal when all pending files have completed poller handoff

## 5. Frontend — Conditional Delete Handler

- [x] 5.1 In MaterialsPage, update the delete handler to check whether the material has an `integration_source_point_id`
- [x] 5.2 If `integration_source_point_id` is non-null: call a new delete endpoint that removes the S3 object and sets `sync = false` (does NOT delete the row)
- [x] 5.3 If `integration_source_point_id` is null: use the existing delete handler (remove S3 + delete row)

## 6. API — Synced Material Delete Endpoint

- [x] 6.1 Add or extend the materials delete endpoint to accept an optional `tombstone` flag (or detect `integration_source_point_id` server-side) and perform S3 delete + `UPDATE materials SET sync = false` instead of row deletion
- [x] 6.2 Confirm the tombstoned row is not returned in the active materials list displayed to users
- [x] 6.3 Wire existing `Material.tombstone` into `api/material.py#do_DELETE` for synced rows (`integration_source_point_id` non-null); remove current always-hard-delete behavior for that path

## 7. CoursePage — Sync Entry Point Alignment

- [x] 7.1 Remove or repurpose source-panel Sync Now controls in `CoursePage` so sync entry routes through `MaterialsPage` Sync Modal
- [x] 7.2 Keep source-point management (add/remove/enable/disable) intact while delegating sync run UX to `MaterialsPage`
