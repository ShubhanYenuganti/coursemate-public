## MODIFIED Requirements

### Requirement: Lambda poller ingests all files in a Drive folder as course materials
The system SHALL poll active Drive folder source points, list all files within each folder, and for each file consult the `sync` field in the materials table before any PDF conversion work begins. Files with `sync = false` SHALL be skipped. Files with `sync = true` or no existing row SHALL proceed with the existing embed pipeline. Files larger than 50 MB SHALL be skipped with an error status.

#### Scenario: New Drive folder ingested
- **WHEN** the integration Lambda polls an active `gdrive` source point for the first time
- **THEN** the system lists all files in the folder, exports each file as PDF (using Drive export API for Google Docs/Sheets/Slides, or downloads directly for native PDFs), uploads each to S3, creates a materials record per file with `sync = true`, and enqueues an embed job per file

#### Scenario: Changed file in folder re-ingested
- **WHEN** the integration Lambda polls a folder and a file's `modifiedTime` is newer than its corresponding material's `external_last_edited`
- **THEN** the system re-exports that file as PDF, replaces the S3 object, updates the materials record, deletes old embedding chunks, and enqueues a fresh embed job

#### Scenario: New file added to folder
- **WHEN** the integration Lambda polls a folder and finds a file with no corresponding material record (by `external_id`)
- **THEN** the system ingests it as a new material following the same flow as initial ingestion and inserts with `sync = true`

#### Scenario: Unchanged file skipped
- **WHEN** the integration Lambda polls a folder and a file's `modifiedTime` matches its material's `external_last_edited`
- **THEN** the system SHALL skip re-ingestion for that file

#### Scenario: File removed from folder
- **WHEN** the integration Lambda polls a folder and a previously ingested file is no longer present
- **THEN** the system SHALL mark the corresponding material as inactive (do NOT delete it or its embeddings)

#### Scenario: File exceeds size limit
- **WHEN** a Drive file export results in a file larger than 50 MB
- **THEN** the system SHALL skip ingestion for that file and mark the material with an error status; other files in the folder continue processing

#### Scenario: File with sync = false is skipped by poller
- **WHEN** the integration Lambda polls a folder and a file's corresponding materials row has `sync = false`
- **THEN** the poller SHALL skip that file before performing any PDF conversion or S3 upload, and SHALL NOT enqueue an embed job

#### Scenario: Sync check precedes all conversion work
- **WHEN** the poller processes a batch of files from a source point
- **THEN** the system SHALL look up each file's `sync` value (batch query by `external_id`) before initiating any Drive export or download call
