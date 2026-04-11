## ADDED Requirements

### Requirement: Flashcards export as toggle blocks on a Notion page
`POST /api/notion?action=export` with `generation_type='flashcards'` SHALL export all cards from a ready flashcard generation as toggle blocks appended to the user's selected Notion page. Each card SHALL become a toggle block: the toggle heading = card `front`, the expanded content = card `back` and card `hint` (if present). The exporter SHALL call Notion's `POST /v1/blocks/{page_id}/children` once with all toggle blocks in a single request.

#### Scenario: Successful flashcard export to page
- **WHEN** the user has a connected Notion account
- **AND** the user selects a Notion page as the target
- **AND** calls `POST /api/notion?action=export` with `{ exports: [{ generation_id, generation_type: 'flashcards', targets: [{ provider: 'notion', target_id }] }] }`
- **THEN** toggle blocks are appended to the target page — one per card
- **AND** each toggle heading = card front, body = back + hint
- **AND** the response includes `{ total: 1, succeeded: 1, failed: 0, results: [{ generation_id, provider: 'notion', status: 'success', exported_count: <count>, url: '<page url>' }] }`

#### Scenario: Export denied for non-owner/non-collaborator
- **WHEN** the authenticated user does not have access to the flashcard generation
- **THEN** the result entry has `status: 'error'` and `error: 'Forbidden'`

#### Scenario: Export of non-ready generation
- **WHEN** `generation_id` refers to a generation with status != 'ready'
- **THEN** the result entry has `status: 'error'` and `error: 'Generation not ready'`

#### Scenario: Target is not a page
- **WHEN** the `target_id` resolves to a Notion database or other non-page type
- **THEN** the endpoint returns 422 Unprocessable Entity with `{ "error": "Flashcard export requires a Notion page target, not a database" }`

### Requirement: Export modal filters target picker to pages only
The Flashcards export modal SHALL open `NotionTargetPicker` with `allowedTypes: ['page']`. The picker SHALL only show and allow selection of Notion pages. The `+ Create new` sub-form SHALL only offer "Page" as a type option when `allowedTypes` excludes databases.

### Requirement: Invalid sticky target shown with warning in Flashcards modal
If the saved sticky target for (user, course, 'flashcards') has `external_target_type = 'database'`, the export modal SHALL render the target with a warning icon (⚠). On hover, the tooltip SHALL read: "This target is invalid for flashcard exports. Select a Notion page." The export button SHALL be disabled until the user selects a valid page target.

#### Scenario: Sticky target is a database
- **WHEN** the user opens the flashcards export modal
- **AND** the saved sticky target is a Notion database
- **THEN** the target is shown with a warning icon
- **AND** the export button is disabled
- **AND** clicking the target opens the picker filtered to pages only
- **AND** selecting a valid page clears the warning and enables export

### Requirement: Export result shown in viewer UI
After a successful export, the Flashcards viewer SHALL display a success banner with a link to the Notion page. The "Export to Notion" button SHALL remain available for re-exporting.

#### Scenario: Post-export success state
- **WHEN** the export API returns success
- **THEN** the viewer shows a "Exported to Notion ✓" banner with a clickable Notion URL
- **AND** the button remains enabled (re-export is allowed)
