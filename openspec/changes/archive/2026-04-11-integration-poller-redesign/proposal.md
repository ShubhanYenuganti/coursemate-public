## Why

The integration pollers (GDrive and Notion) currently discover files by querying the external API broadly (all files in a folder / all pages in a database), then post-filter against the materials table — discarding the explicit file selection made by the user at sync time. Additionally, GDrive uses an equality check (`==`) to detect changes while Notion uses URL shape rather than timestamps, making re-sync on "Sync Now" silent no-ops for already-ingested files.

## What Changes

- Both pollers abandon broad external API listing in favour of a DB-driven work list: query `materials` WHERE `integration_source_point_id` matches AND `sync = TRUE`, then fetch fresh metadata per-ID from the external API
- When `external_ids` are passed in the Lambda event (triggered by "Sync Now"), use that list directly instead of querying the DB
- GDrive staleness check changes from `external_last_edited == modifiedTime` to `modifiedTime > external_last_edited`
- Notion replaces the placeholder-URL staleness check with `last_edited_time > external_last_edited`, using the `2026-03-11` API version already in use
- A shared `_needs_ingest(api_time, db_time)` helper replaces both ad-hoc checks
- When `_needs_ingest` returns False for a file in the sync list, the poller writes `embed_status = 'up_to_date'` to `material_embed_jobs` to signal "checked, no changes"
- `_trigger_poller` in `api/material.py` includes `external_ids` (sync=True files only) in the Lambda payload when called from `bulk_upsert_sync`
- Stuck-pages recovery block in Notion's `sync_source_point` is removed — NULL `external_last_edited` naturally triggers re-ingest via `_needs_ingest`
- `sync_lookup` batch-SELECT (built in both handlers to gate on `sync` flag) is removed — the work list is already filtered to `sync = TRUE`

## Capabilities

### New Capabilities
- `poller-db-driven-work-list`: Pollers derive their per-run file list from the materials table (filtered to `sync=TRUE` for the source point) rather than broad external API queries, with `external_ids` override for explicit "Sync Now" invocations
- `poller-timestamp-staleness`: Unified `_needs_ingest(api_time, db_time)` datetime comparison (`>`) replaces GDrive equality check and Notion URL-shape check; writes `embed_status = 'up_to_date'` when no changes detected

### Modified Capabilities
- `gdrive-import`: Staleness detection changes from `==` to `>` timestamp comparison; file listing changes from folder-scan to per-ID fetch
- `gdrive-export`: No change

## Impact

- `api/material.py`: `_trigger_poller` includes `external_ids` in Lambda payload
- `lambda/integration_poller/handler.py`: Forwards `external_ids` from event to `sync_source_point`
- `lambda/integration_poller/handlers/gdrive.py`: Removes `_list_folder_files` call from sync path; adds `_fetch_file_metadata`; replaces `_upsert_material` staleness logic; adds `_needs_ingest` helper
- `lambda/integration_poller/handlers/notion.py`: Removes `data_sources/{id}/query` call from sync path; removes stuck-pages block; replaces `_upsert_material` staleness logic; adds `_needs_ingest` helper
- No schema changes required — `external_last_edited` already stored; `'up_to_date'` is a new string value for the existing `material_embed_jobs.status` text column
