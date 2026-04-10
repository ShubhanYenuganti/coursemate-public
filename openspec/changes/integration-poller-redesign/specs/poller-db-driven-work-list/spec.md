## ADDED Requirements

### Requirement: Poller derives work list from materials table
When invoked without explicit `external_ids`, the poller SHALL query `materials WHERE integration_source_point_id = {sp_id} AND sync = TRUE AND tombstoned IS DISTINCT FROM TRUE` to build the list of files to process. The poller SHALL NOT query the external API broadly (folder listing / database query) for this purpose.

#### Scenario: Background sweep processes only sync=TRUE materials
- **WHEN** the EventBridge scheduler triggers the integration poller with no `external_ids` in the event
- **THEN** the poller queries the materials table for each active source point, retrieves only rows where `sync = TRUE`, fetches fresh metadata per external_id from the external API, and processes each

#### Scenario: No sync=TRUE materials skips external API calls entirely
- **WHEN** the poller runs for a source point that has no materials with `sync = TRUE`
- **THEN** the poller SHALL make no calls to the external API and exit cleanly for that source point

### Requirement: Sync Now passes explicit external_ids to the poller
When `bulk_upsert_sync` triggers the integration poller, the API SHALL include `external_ids` (the list of `external_id` values from the payload where `sync = TRUE`) in the Lambda invocation event. The poller SHALL use this list directly as the work list, bypassing the DB query.

#### Scenario: Sync Now targets only selected files
- **WHEN** the user clicks "Sync Now" selecting 3 files from a 20-file source point
- **THEN** `_trigger_poller` includes only those 3 `external_id` values in the event payload, and the poller processes only those 3 files

#### Scenario: external_ids fallback when absent
- **WHEN** the Lambda event does not contain `external_ids` (EventBridge path)
- **THEN** the poller falls back to the DB work list query and processes all `sync=TRUE` materials for the source point

### Requirement: sync_lookup batch-SELECT is removed
The poller SHALL NOT perform a separate batch-SELECT to build a `sync_lookup` dict for filtering. The work list itself is already filtered to `sync = TRUE`, making the lookup redundant.

#### Scenario: No redundant DB query for sync flags
- **WHEN** the poller builds its work list from the materials table
- **THEN** no additional query is issued to check `sync` values — the initial work list query already enforces this constraint
