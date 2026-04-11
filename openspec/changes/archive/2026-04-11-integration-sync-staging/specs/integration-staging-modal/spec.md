## ADDED Requirements

### Requirement: Initial source point selection opens standalone Sync Modal in MaterialsPage
When a user selects a source point for the first time, the system SHALL fetch all files from that source point and display them in a standalone Sync Modal in MaterialsPage. Each file SHALL be shown with a sync toggle defaulting to ON. No database writes SHALL occur until the user clicks Sync.
While the Sync Modal is active, the Upload Modal SHALL be hidden.

#### Scenario: Modal populates on first source point selection
- **WHEN** a user selects a new integration source point for the first time
- **THEN** the Sync Modal opens listing all files from that source point, each with a toggle set to ON, and the Upload Modal is hidden

#### Scenario: User toggles off a file
- **WHEN** the user flips a file's toggle to OFF in the Sync Modal
- **THEN** the toggle state updates locally and no database write occurs at that moment

#### Scenario: User clicks Sync with mixed toggles
- **WHEN** the user clicks Sync with some files toggled ON and some OFF
- **THEN** the system writes one materials row per file: `sync = true` for ON files, `sync = false` for OFF files, and no embed job is enqueued for OFF files

#### Scenario: User clicks Sync with all files ON
- **WHEN** the user clicks Sync with all file toggles in the ON position
- **THEN** all files are written with `sync = true` and enqueued for ingestion normally

#### Scenario: Source point exceeds 20 files
- **WHEN** a source point contains more than 20 files
- **THEN** the Sync Modal SHALL display files in pages of 20 with a paginator; the user stages and syncs each page independently

#### Scenario: User closes modal without clicking Sync
- **WHEN** the user dismisses the Sync Modal without clicking Sync
- **THEN** no database writes occur and the source point is not added
- **AND** the Upload Modal is shown again

### Requirement: Sync Now opens Sync Modal pre-populated with current sync state
When a user triggers Sync Now in MaterialsPage on a connected source point, the system SHALL fetch all current files from the source point, cross-reference each file against the materials table, and open the Sync Modal with toggles initialized from the stored sync state. The user may flip any toggle before clicking Sync.

#### Scenario: Sync Now with previously excluded files
- **WHEN** the user clicks Sync Now on a source point that has files with `sync = false`
- **THEN** the Sync Modal opens with those files showing toggle OFF and all other files showing toggle ON
- **AND** the Upload Modal is hidden

#### Scenario: Sync Now with new files not yet in the materials table
- **WHEN** the user clicks Sync Now and the source point contains files with no corresponding materials row
- **THEN** those files appear in the Sync Modal with toggle ON by default

#### Scenario: Sync Now click updates existing rows and inserts new rows
- **WHEN** the user clicks Sync in the Sync Modal
- **THEN** the system updates `sync` on pre-existing materials rows and inserts new rows for files that had no row, with `sync` set per the toggle state

### Requirement: Sync Modal remains visible after confirmation until poller handoff completes
After the user clicks Sync, the Sync Modal SHALL remain visible and the Upload Modal SHALL remain hidden while selected files are handed off into poller/embed processing. The modal SHALL show a pending-files dropdown that shrinks as selected files are observed entering the indexing pipeline.

#### Scenario: Pending dropdown shrinks during sync lifecycle
- **WHEN** the Sync Modal is in post-confirmation progress mode
- **THEN** the pending-files dropdown initially contains all selected files with `sync = true`
- **AND** files are removed from the dropdown as they pass poller handoff and transition into embed processing

#### Scenario: Sync workflow ends and Upload Modal is restored
- **WHEN** all selected files have passed poller handoff
- **THEN** the Sync Modal closes automatically
- **AND** the Upload Modal is shown again

### Requirement: Sync Modal normalizes provider-specific list payloads in frontend
The system SHALL keep provider-specific file-list APIs for source points and SHALL normalize their responses in `MaterialsPage` before rendering Sync Modal rows.

#### Scenario: GDrive list response maps to shared row model
- **WHEN** `MaterialsPage` fetches `/api/gdrive?action=list_source_point_files`
- **THEN** each item is normalized to the shared Sync Modal row model with `source_type = 'gdrive'`

#### Scenario: Notion list response maps to shared row model
- **WHEN** `MaterialsPage` fetches `/api/notion?action=list_source_point_files`
- **THEN** each item is normalized to the shared Sync Modal row model with `source_type = 'notion'`
