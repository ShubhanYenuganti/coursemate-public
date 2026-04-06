## ADDED Requirements

### Requirement: Flashcards export to Notion Database
`POST /api/notion?action=export` with `generation_type='flashcards'` SHALL export all cards from a ready flashcard generation as rows in the user's selected Notion database. Each row SHALL have three properties: `Name` (title, maps to card `front`), `Back` (rich text, maps to card `back`), and `Hint` (rich text, maps to card `hint`). The exporter SHALL call Notion's `POST /v1/pages` once per card.

#### Scenario: Successful flashcard export to database
- **WHEN** the user has a connected Notion account
- **AND** the user selects a Notion database as the target
- **AND** calls `POST /api/notion?action=export` with `generation_id` and `generation_type='flashcards'`
- **THEN** one Notion page (database row) is created per card
- **AND** each row has `Name` = front text, `Back` = back text, `Hint` = hint text
- **AND** the response includes `{ "exported": <count>, "notion_url": "<database url>" }`

#### Scenario: Fallback to toggle blocks when target is a page
- **WHEN** the user selected a Notion page (not a database) as the target
- **THEN** cards are exported as toggle blocks: each toggle heading = front, expanded content = back + hint
- **AND** the response includes `{ "exported": <count>, "notion_url": "<page url>", "format": "toggle_blocks" }`

#### Scenario: Export denied for non-owner/non-collaborator
- **WHEN** the authenticated user does not have access to the flashcard generation
- **THEN** the endpoint returns 403 Forbidden

#### Scenario: Export of non-ready generation
- **WHEN** `generation_id` refers to a generation with status != 'ready'
- **THEN** the endpoint returns 409 Conflict with `{ "error": "Generation not ready" }`

### Requirement: Flashcards export validates database schema
Before exporting, the system SHALL retrieve the target database's property schema from Notion. If the database does not have a title property and at least one text property, the system SHALL return a descriptive error rather than silently creating malformed rows.

#### Scenario: Database missing required properties
- **WHEN** the target Notion database has no text properties available
- **THEN** the system returns 422 Unprocessable Entity with `{ "error": "Target database must have text properties for Back and Hint" }`

### Requirement: Export result shown in viewer UI
After a successful export, the Flashcards viewer SHALL display a success banner with a link to the Notion database/page. The "Export to Notion" button SHALL remain available for re-exporting.

#### Scenario: Post-export success state
- **WHEN** the export API returns success
- **THEN** the viewer shows a "Exported to Notion ✓" banner with a clickable Notion URL
- **AND** the button remains enabled (re-export is allowed)
