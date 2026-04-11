## ADDED Requirements

### Requirement: Unified timestamp staleness check across providers
Both GDrive and Notion pollers SHALL use a shared `_needs_ingest(api_time_str, db_time) -> bool` helper to determine whether a file requires re-ingestion. The helper SHALL return `True` if `api_time > db_time` (parsed as timezone-aware datetimes), `True` if `db_time` is absent or empty, and `True` on parse failure (safe default). The helper SHALL return `False` only when `api_time <= db_time`.

#### Scenario: File modified since last ingest
- **WHEN** the external API returns a timestamp newer than `external_last_edited` in the DB
- **THEN** `_needs_ingest` returns `True` and the poller re-ingests the file

#### Scenario: File unchanged since last ingest
- **WHEN** the external API returns a timestamp equal to or older than `external_last_edited` in the DB
- **THEN** `_needs_ingest` returns `False` and the poller skips re-ingestion

#### Scenario: No prior ingest record
- **WHEN** `external_last_edited` is NULL or empty in the DB (file never successfully ingested)
- **THEN** `_needs_ingest` returns `True` and the poller ingests the file

#### Scenario: Unparseable timestamp
- **WHEN** either timestamp string cannot be parsed as ISO 8601
- **THEN** `_needs_ingest` returns `True` and the poller re-ingests to be safe

### Requirement: Notion staleness uses last_edited_time from pages API
The Notion poller SHALL determine staleness by comparing `last_edited_time` returned by `GET /pages/{page_id}` (using `Notion-Version: 2026-03-11`) against `external_last_edited` stored in the materials row. The placeholder URL check (`file_url LIKE 'notion/%.pdf'`) SHALL be removed from `_upsert_material` and SHALL NOT be used for staleness detection.

#### Scenario: Notion page edited since last ingest
- **WHEN** the Notion pages API returns `last_edited_time` newer than the material's `external_last_edited`
- **THEN** `_needs_ingest` returns `True` and the poller re-converts and re-embeds the page

#### Scenario: Notion page unchanged
- **WHEN** `last_edited_time` is equal to or older than `external_last_edited`
- **THEN** `_needs_ingest` returns `False` and the file is skipped

### Requirement: Poller writes up_to_date status when no changes detected on targeted sync
When processing a file from the `external_ids` list (i.e., a "Sync Now" run) and `_needs_ingest` returns `False`, the poller SHALL update `material_embed_jobs SET status = 'up_to_date' WHERE material_id = {id}`. This SHALL NOT be written during background EventBridge sweeps.

#### Scenario: Sync Now finds no changes
- **WHEN** the user clicks "Sync Now" for a file and the external API timestamp is not newer than `external_last_edited`
- **THEN** the poller writes `embed_status = 'up_to_date'` to `material_embed_jobs` for that material

#### Scenario: Background sweep skips unchanged file
- **WHEN** the EventBridge scheduler triggers a sweep and a file has no changes
- **THEN** the poller skips the file silently and does NOT write `'up_to_date'` to `material_embed_jobs`

### Requirement: Stuck-pages recovery is removed from Notion poller
The Notion `sync_source_point` SHALL NOT contain a secondary DB query to find materials with placeholder `file_url` and retry them. Files that previously failed mid-upload will have `external_last_edited = NULL`, causing `_needs_ingest` to return `True` on the next sweep, providing equivalent retry behaviour without the separate query.

#### Scenario: Previously failed upload retried automatically
- **WHEN** a Notion page previously failed mid-upload (S3 upload error) and has `external_last_edited = NULL`
- **THEN** on the next poller run, `_needs_ingest(api_time, NULL)` returns `True` and the page is retried
