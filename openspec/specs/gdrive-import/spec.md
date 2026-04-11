## Purpose

Define Google Drive import behavior for course source points, including folder source management and Lambda-driven ingestion into course materials.
## Requirements
### Requirement: User can add a Drive folder as a course source point
The system SHALL allow users to add a Google Drive folder as a source point for a course. The source point SHALL be stored in `integration_source_points` with `provider = "gdrive"` and `external_id` set to the Drive folder ID.

#### Scenario: Adding a Drive folder source point
- **WHEN** user provides a Google Drive folder URL or ID when adding a source point
- **THEN** the system verifies the folder is accessible, creates an `integration_source_points` record, and returns the new source point

#### Scenario: Duplicate source point
- **WHEN** user attempts to add a Drive folder that is already a source point for that course
- **THEN** the system SHALL return a 409 error with a message indicating the folder is already connected

#### Scenario: Folder not accessible
- **WHEN** the provided Drive folder ID is not accessible with the user's stored token
- **THEN** the system SHALL return a 403 error prompting the user to verify folder permissions or reconnect

### Requirement: Lambda poller ingests all files in a Drive folder as course materials
The system SHALL poll active Drive folder source points, derive a work list of files from the materials table (filtered to `sync = TRUE` for the source point), fetch fresh metadata per file ID from the Drive API, and re-ingest files whose `modifiedTime > external_last_edited`. Files larger than 50 MB SHALL be skipped with an error status.

#### Scenario: New Drive folder ingested
- **WHEN** the integration Lambda polls an active `gdrive` source point for the first time
- **THEN** the system fetches metadata for each external_id in the work list, exports each file as PDF (using Drive export API for Google Docs/Sheets/Slides, or downloads directly for native PDFs), uploads each to S3, creates a materials record per file, and enqueues an embed job per file

#### Scenario: Changed file re-ingested
- **WHEN** the integration Lambda polls a source point and a file's `modifiedTime` is strictly greater than its material's `external_last_edited`
- **THEN** the system re-exports that file as PDF, replaces the S3 object, updates the materials record, deletes old embedding chunks, and enqueues a fresh embed job

#### Scenario: New file added to source point
- **WHEN** the integration Lambda polls a source point and finds an external_id with no corresponding material record
- **THEN** the system ingests it as a new material following the same flow as initial ingestion

#### Scenario: Unchanged file skipped
- **WHEN** the integration Lambda polls a source point and a file's `modifiedTime` is equal to or older than its material's `external_last_edited`
- **THEN** the system SHALL skip re-ingestion for that file

#### Scenario: File exceeds size limit
- **WHEN** a Drive file export results in a file larger than 50 MB
- **THEN** the system SHALL skip ingestion for that file and mark the material with an error status; other files in the source point continue processing

### Requirement: User can list and manage Drive folder source points
The system SHALL allow users to list, enable/disable, and remove Drive folder source points for a course. The `list_source_point_files` response SHALL include `doc_type` for each file alongside `sync`, populated from the `materials` table when a record exists. Files with no materials record SHALL return `doc_type = null`.

#### Scenario: Listing source points
- **WHEN** user requests the list of source points for a course
- **THEN** the system returns all `integration_source_points` records for that course including `gdrive` folder entries

#### Scenario: Toggling a source point
- **WHEN** user toggles a Drive folder source point off
- **THEN** the system updates `is_active = false` and the Lambda poller skips all files in that folder on the next run

#### Scenario: Removing a source point
- **WHEN** user removes a Drive folder source point
- **THEN** the system deletes the `integration_source_points` record; previously ingested materials from that folder are NOT automatically deleted

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

