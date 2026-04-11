## ADDED Requirements

### Requirement: ProgressPanel displays all active and completed jobs inline
The system SHALL render a `ProgressPanel` component between the upload section and the materials grid whenever any sync job or upload item exists. The panel SHALL show sync jobs grouped by source point and upload items grouped under an "Uploads" section. The panel SHALL NOT render when `syncJobs` and `uploadItems` are both empty.

#### Scenario: Panel appears on sync confirm
- **WHEN** user confirms a sync via the SyncModal
- **THEN** the ProgressPanel SHALL appear below the upload section showing the synced files with a "Processing…" status for each item

#### Scenario: Panel appears on upload start
- **WHEN** user triggers an upload from the staging queue
- **THEN** the ProgressPanel SHALL appear with the uploading file as a row showing an in-progress indicator

#### Scenario: Panel hidden when no jobs exist
- **WHEN** no sync jobs and no upload items are present
- **THEN** the ProgressPanel SHALL not be rendered in the DOM

### Requirement: ProgressPanel derives per-item status from polled materials
For sync job items, the system SHALL derive display status by matching `external_id` against the polled `materials` array. The terminal condition SHALL be `embed_status === 'done'`. No intermediate status SHALL be stored in React state.

#### Scenario: Item shows processing during Lambda execution
- **WHEN** a sync job item's `external_id` does not yet match any material in the polled array
- **THEN** the item SHALL display "Syncing…" status

#### Scenario: Item shows queued when embed pending
- **WHEN** a material with matching `external_id` exists and `embed_status === 'pending'`
- **THEN** the item SHALL display "Queued" status

#### Scenario: Item shows indexing when embed processing
- **WHEN** a material with matching `external_id` exists and `embed_status === 'processing'`
- **THEN** the item SHALL display "Indexing…" status

#### Scenario: Item shows done when embed complete
- **WHEN** a material with matching `external_id` exists and `embed_status === 'done'`
- **THEN** the item SHALL display a "Done" indicator

#### Scenario: Item shows failed on embed failure
- **WHEN** a material with matching `external_id` exists and `embed_status === 'failed'`
- **THEN** the item SHALL display a "Failed" error indicator

### Requirement: Polling accelerates to 2 s during active jobs
The system SHALL poll `/api/material` every 2 seconds while any sync job item is non-terminal or any upload item is in `uploading` or `confirming` state. Polling SHALL stop when all items are terminal.

#### Scenario: Polling active during sync
- **WHEN** a sync job has one or more items not yet in `done` state
- **THEN** `fetchMaterials` SHALL be called every 2 seconds

#### Scenario: Polling stops when all done
- **WHEN** all sync job items have `embed_status === 'done'` and all upload items are in `done` or `error` state
- **THEN** no further polling timer SHALL be scheduled

### Requirement: ProgressPanel is dismissible with localStorage persistence
The system SHALL allow users to dismiss the ProgressPanel via a "Clear done" action. Dismissal SHALL be persisted to `localStorage` under the key `coursemate_progress_dismissed`. The panel SHALL automatically reappear when a new upload or sync job is added, regardless of the stored dismissal flag.

#### Scenario: User clears completed items
- **WHEN** user clicks "Clear done" and no active items remain
- **THEN** completed items are removed from state, `localStorage` flag is set, and the panel disappears

#### Scenario: Panel reopens on new activity
- **WHEN** a new upload or sync job is added after the panel was dismissed
- **THEN** the `localStorage` flag SHALL be cleared and the panel SHALL reappear

#### Scenario: Active items block full dismissal
- **WHEN** user clicks "Clear done" but active items are still in progress
- **THEN** only terminal items (done/error/skipped) are removed; the panel remains visible with the active items

### Requirement: SyncModal is staging-only
The `SyncModal` component SHALL only support file selection (staging mode). It SHALL NOT render a progress view or accept `pendingRows`-style props. On sync confirm, the modal SHALL close and hand off to the ProgressPanel for progress display.

#### Scenario: Modal closes immediately on confirm
- **WHEN** user clicks "Sync" in SyncModal
- **THEN** the modal closes and a new sync job entry appears in ProgressPanel

#### Scenario: Modal has no progress mode
- **WHEN** a sync is in progress
- **THEN** the SyncModal SHALL not be shown; the ProgressPanel is the only progress surface

### Requirement: EmbedStatusBadge is removed from MaterialCard
The `MaterialCard` component SHALL NOT render an `EmbedStatusBadge`. Embedding status SHALL be surfaced exclusively in the ProgressPanel during active processing. Once complete, material cards show no embed status indicator.

#### Scenario: Completed material card shows no status badge
- **WHEN** a material has `embed_status === 'done'`
- **THEN** the MaterialCard SHALL render with no embed status indicator

#### Scenario: In-progress material not shown in card
- **WHEN** a material is actively being embedded
- **THEN** its card in the grid MAY still render but SHALL show no embed status badge
