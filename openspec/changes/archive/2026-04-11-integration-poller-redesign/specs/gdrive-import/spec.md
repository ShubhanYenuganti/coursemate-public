## MODIFIED Requirements

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
