## Purpose

Define the document type selection behavior in the integration sync modal, including per-file dropdown display, default values, and pre-fill from stored data.

## Requirements

### Requirement: User can select document type per file in the sync modal
The sync modal's staging view SHALL include a `doc_type` dropdown for each file row, using the same `DOCUMENT_TYPES` list as the upload staging area. The selected value SHALL default to `'general'` for files that have not yet been synced.

#### Scenario: Doc type dropdown appears for each file
- **WHEN** the sync modal opens in staging mode and files are loaded
- **THEN** each file row SHALL display a `doc_type` dropdown populated with all values from `DOCUMENT_TYPES`

#### Scenario: Default doc type for new files
- **WHEN** a file appears in the sync modal and has no prior sync record (`sync = null`)
- **THEN** the dropdown SHALL default to `'general'`

#### Scenario: User changes doc type before syncing
- **WHEN** user selects a different value from the dropdown for a file
- **THEN** the selected value SHALL be sent as `doc_type` for that file in the `bulk_upsert_sync` payload

### Requirement: Sync modal pre-fills doc type from last stored value
When a file has been previously synced, the sync modal SHALL pre-fill the `doc_type` dropdown with the value stored in the `materials` table for that file.

#### Scenario: Pre-fill on re-open for previously synced file
- **WHEN** the sync modal opens for a source point that contains a file with `sync = true` in the materials table
- **THEN** the `doc_type` dropdown for that file SHALL be pre-filled with the stored `doc_type` value

#### Scenario: Pre-fill persists across page navigation within modal
- **WHEN** user navigates to a different page within the sync modal and returns to a page containing a previously synced file
- **THEN** the `doc_type` dropdown SHALL again reflect the stored value (loaded fresh from the server on each page load)

#### Scenario: Pre-fill absent for files never synced
- **WHEN** the sync modal opens for a file with no materials record (`sync = null`)
- **THEN** the `doc_type` dropdown SHALL show `'general'` as the default
