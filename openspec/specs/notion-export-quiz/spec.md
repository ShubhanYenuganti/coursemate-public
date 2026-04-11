# notion-export-quiz Specification

## Purpose
TBD - created by archiving change notion-integration. Update Purpose after archive.
## Requirements
### Requirement: Quiz exports as a structured Notion page
`POST /api/notion?action=export` with `generation_type='quiz'` SHALL create a child Notion page under the user's selected target page. The page SHALL be titled with the quiz title. Content SHALL use: `heading_2` blocks for each question text, `bulleted_list_item` blocks for each answer option (prefixed with a letter A/B/C/D), and a `toggle` block labeled "Answer" containing the correct option and explanation if available.

#### Scenario: Successful quiz export
- **WHEN** the user has a connected Notion account and a ready quiz generation
- **AND** calls `POST /api/notion?action=export` with `{ exports: [{ generation_id, generation_type: 'quiz', targets: [{ provider: 'notion', target_id }] }] }`
- **THEN** a Notion page is created under the target
- **AND** each question becomes a `heading_2` block
- **AND** options become `bulleted_list_item` blocks
- **AND** the correct answer is inside a `toggle` block
- **AND** the result entry includes `{ status: 'success', exported_count: <question_count>, url: '<page url>' }`

#### Scenario: Export when target is not a page
- **WHEN** the `target_id` resolves to a Notion database or other non-page type
- **THEN** the endpoint returns 422 with `{ "error": "Quiz export requires a Notion page target, not a database" }`

#### Scenario: Export of non-ready quiz generation
- **WHEN** the quiz generation status is not 'ready'
- **THEN** the result entry has `status: 'error'` and `error: 'Generation not ready'`

### Requirement: Export modal filters target picker to pages only
The Quiz export modal SHALL open `NotionTargetPicker` with `allowedTypes: ['page']`. The picker SHALL only show and allow selection of Notion pages. The `+ Create new` sub-form SHALL only offer "Page" as a type option when `allowedTypes` excludes databases.

### Requirement: Invalid sticky target shown with warning in Quiz modal
If the saved sticky target for (user, course, 'quiz') has `external_target_type = 'database'`, the export modal SHALL render the target with a warning icon (⚠). On hover, the tooltip SHALL read: "This target is invalid for quiz exports. Select a Notion page." The export button SHALL be disabled until the user selects a valid page target.

#### Scenario: Sticky target is a database
- **WHEN** the user opens the quiz export modal
- **AND** the saved sticky target is a Notion database
- **THEN** the target is shown with a warning icon
- **AND** the export button is disabled
- **AND** clicking the target opens the picker filtered to pages only
- **AND** selecting a valid page clears the warning and enables export

### Requirement: Export result shown in Quiz viewer
After a successful export, the Quiz viewer SHALL display a success banner with a link to the created Notion page.

#### Scenario: Post-export success state
- **WHEN** the export completes
- **THEN** a "Exported to Notion ✓" banner appears with a clickable link to the page

