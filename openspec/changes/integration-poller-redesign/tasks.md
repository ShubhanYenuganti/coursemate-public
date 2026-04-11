## 1. API — Thread external_ids through to Lambda

- [x] 1.1 In `api/material.py` `_bulk_upsert_sync`, after the upsert loop, collect `external_ids = [f['external_id'] for f in files if f.get('sync')]` and pass it to `_trigger_poller`
- [x] 1.2 In `api/material.py` `_trigger_poller`, add `external_ids: list | None = None` parameter and include it in the Lambda invocation JSON payload
- [x] 1.3 In `lambda/integration_poller/handler.py` `lambda_handler`, extract `external_ids` from the event (default `None`) and pass it as a keyword argument to `notion_sync` and `gdrive_sync` calls

## 2. Shared staleness helper

- [x] 2.1 In `lambda/integration_poller/handlers/utils.py`, add `_needs_ingest(api_time_str: str, db_time) -> bool` that parses both values as timezone-aware datetimes, returns `True` if `api_time > db_time` or `db_time` is falsy or parse fails
- [x] 2.2 Create `lambda/integration_poller/handlers/utils.py` with `_needs_ingest`, and import it in both `gdrive.py` and `notion.py` (replacing the inline copy in `gdrive.py` from 2.1)

## 3. GDrive poller — DB-driven work list and per-ID fetch

- [x] 3.1 Add `_fetch_file_metadata(file_id: str, token: str) -> dict | None` to `gdrive.py` that calls `GET /drive/v3/files/{file_id}?fields=id,name,mimeType,modifiedTime` and returns the parsed JSON (returns `None` on error)
- [x] 3.2 Update `sync_source_point` signature to accept `external_ids: list | None = None`
- [x] 3.3 In `sync_source_point` (Sync Now path): when `external_ids` is provided, assign it directly as `work_ids` — no DB query
- [x] 3.4 In `sync_source_point` (background sweep path): when `external_ids` is `None`, query `materials WHERE integration_source_point_id = {sp_id} AND sync = TRUE AND tombstoned IS DISTINCT FROM TRUE` and collect `external_id` values as `work_ids`
- [x] 3.5 Replace the `_list_folder_files` loop with a loop over `work_ids`, calling `_fetch_file_metadata` for each; skip the item if metadata returns `None`
- [x] 3.6 Remove the `sync_lookup` batch-SELECT and all `sync_lookup.get(file_id) is False` guard logic
- [x] 3.7 In `_upsert_material`, replace `if existing_edited == modified_time: return existing['id'], False` with `if not _needs_ingest(modified_time, existing.get('external_last_edited')): return existing['id'], False`

## 4. Notion poller — DB-driven work list and per-ID fetch

- [x] 4.1 Update `sync_source_point` signature to accept `external_ids: list | None = None`
- [x] 4.2 In `sync_source_point` (Sync Now path): when `external_ids` is provided, assign it directly as `work_ids` — no DB query
- [x] 4.3 In `sync_source_point` (background sweep path): when `external_ids` is `None`, query `materials WHERE integration_source_point_id = {sp_id} AND sync = TRUE AND tombstoned IS DISTINCT FROM TRUE` and collect `external_id` values as `work_ids`
- [x] 4.4 Replace the `data_sources/{id}/query` pagination block with a loop over `work_ids`, fetching each page via `_notion_get(f"pages/{page_id}", token)`; skip items that raise an error
- [x] 4.5 Remove the stuck-pages recovery block (secondary DB query for placeholder `file_url` rows) entirely
- [x] 4.6 Remove the `sync_lookup` batch-SELECT and all `sync_lookup.get(page_id) is False` guard logic
- [x] 4.7 In `_upsert_material`, remove the `needs_reingest` placeholder URL block and replace with `if not _needs_ingest(last_edited_time, existing.get('external_last_edited')): return existing['id'], False`

## 5. Write up_to_date status on targeted no-change skips

- [x] 5.1 In `gdrive.py` `sync_source_point`, when `_needs_ingest` returns `False` AND `external_ids` was provided (targeted run), issue `UPDATE material_embed_jobs SET status = 'up_to_date' WHERE material_id = {id}` before continuing to the next file
- [x] 5.2 Apply the same `'up_to_date'` write in `notion.py` `sync_source_point` under the same condition

## 6. Verification

- [x] 6.1 Trigger a "Sync Now" on a GDrive file that has not changed — confirm `embed_status` becomes `'up_to_date'` in the DB and no S3/embed work runs
- [x] 6.2 Trigger a "Sync Now" on a GDrive file that has changed — confirm full re-ingest pipeline runs and `embed_status` reaches `'done'`
- [x] 6.3 Trigger a "Sync Now" on a Notion page that has not changed — confirm `embed_status = 'up_to_date'` and no re-conversion
- [x] 6.4 Trigger a "Sync Now" on a Notion page that has changed — confirm re-conversion, S3 re-upload, and fresh embed job
- [x] 6.5 Confirm EventBridge background sweep still processes all `sync=TRUE` materials correctly without `external_ids` in the event
- [ ] 6.6 Confirm a file with `external_last_edited = NULL` (failed prior upload) is retried automatically by both pollers on the next sweep
