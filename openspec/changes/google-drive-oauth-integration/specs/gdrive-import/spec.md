## ADDED Requirements

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
The system SHALL poll active Drive folder source points, list all files within each folder, and convert each file to PDF for ingestion as course materials. Files larger than 50 MB SHALL be skipped with an error status.

#### Scenario: New Drive folder ingested
- **WHEN** the integration Lambda polls an active `gdrive` source point for the first time
- **THEN** the system lists all files in the folder, exports each file as PDF (using Drive export API for Google Docs/Sheets/Slides, or downloads directly for native PDFs), uploads each to S3, creates a materials record per file, and enqueues an embed job per file

#### Scenario: Changed file in folder re-ingested
- **WHEN** the integration Lambda polls a folder and a file's `modifiedTime` is newer than its corresponding material's `external_last_edited`
- **THEN** the system re-exports that file as PDF, replaces the S3 object, updates the materials record, deletes old embedding chunks, and enqueues a fresh embed job

#### Scenario: New file added to folder
- **WHEN** the integration Lambda polls a folder and finds a file with no corresponding material record (by `external_id`)
- **THEN** the system ingests it as a new material following the same flow as initial ingestion

#### Scenario: Unchanged file skipped
- **WHEN** the integration Lambda polls a folder and a file's `modifiedTime` matches its material's `external_last_edited`
- **THEN** the system SHALL skip re-ingestion for that file

#### Scenario: File removed from folder
- **WHEN** the integration Lambda polls a folder and a previously ingested file is no longer present
- **THEN** the system SHALL mark the corresponding material as inactive (do NOT delete it or its embeddings)

#### Scenario: File exceeds size limit
- **WHEN** a Drive file export results in a file larger than 50 MB
- **THEN** the system SHALL skip ingestion for that file and mark the material with an error status; other files in the folder continue processing

### Requirement: User can list and manage Drive folder source points
The system SHALL allow users to list, enable/disable, and remove Drive folder source points for a course, identical in behavior to the Notion source point management endpoints.

#### Scenario: Listing source points
- **WHEN** user requests the list of source points for a course
- **THEN** the system returns all `integration_source_points` records for that course including `gdrive` folder entries

#### Scenario: Toggling a source point
- **WHEN** user toggles a Drive folder source point off
- **THEN** the system updates `is_active = false` and the Lambda poller skips all files in that folder on the next run

#### Scenario: Removing a source point
- **WHEN** user removes a Drive folder source point
- **THEN** the system deletes the `integration_source_points` record; previously ingested materials from that folder are NOT automatically deleted
