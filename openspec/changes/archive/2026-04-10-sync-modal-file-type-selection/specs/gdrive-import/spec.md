## MODIFIED Requirements

### Requirement: User can list and manage Drive folder source points
The system SHALL allow users to list, enable/disable, and remove Drive folder source points for a course. The `list_source_point_files` response SHALL include `doc_type` for each file alongside `sync`, populated from the `materials` table when a record exists. Files with no materials record SHALL return `doc_type = null`.

#### Scenario: Listing source points
- **WHEN** user requests the list of source points for a course
- **THEN** the system returns all `integration_source_points` records for that course including `gdrive` folder entries

#### Scenario: Toggling a source point
- **WHEN** user toggles a Drive folder source point off
- **THEN** the system updates `is_active = false` and the Lambda poller skips all files in that folder on the next run

#### Scenario: list_source_point_files includes doc_type
- **WHEN** user requests files for a source point
- **THEN** each file in the response SHALL include a `doc_type` field: the stored value if a materials record exists, or `null` if no record exists

### Requirement: bulk_upsert_sync persists per-file doc_type
The `bulk_upsert_sync` endpoint SHALL accept an optional `doc_type` field per file entry in the `files` array. When present and valid, the value SHALL be stored in `materials.doc_type`. When absent or invalid, the system SHALL default to `'general'`.

#### Scenario: Per-file doc_type stored on sync
- **WHEN** user confirms sync with a specific `doc_type` selected for a file
- **THEN** the materials record for that file SHALL have `doc_type` set to the selected value

#### Scenario: Missing doc_type defaults to general
- **WHEN** a file entry in `bulk_upsert_sync` payload omits the `doc_type` field
- **THEN** the materials record SHALL be upserted with `doc_type = 'general'`

#### Scenario: Invalid doc_type defaults to general
- **WHEN** a file entry in `bulk_upsert_sync` payload contains an unrecognised `doc_type` value
- **THEN** the materials record SHALL be upserted with `doc_type = 'general'`
