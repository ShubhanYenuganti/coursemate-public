## ADDED Requirements

### Requirement: Quiz exports as a structured Notion page
`POST /api/notion?action=export` with `generation_type='quiz'` SHALL create a child Notion page under the user's selected target page. The page SHALL be titled with the quiz title. Content SHALL use: `heading_2` blocks for each question text, `bulleted_list_item` blocks for each answer option (prefixed with a letter A/B/C/D), and a `toggle` block labeled "Answer" containing the correct option and explanation if available.

#### Scenario: Successful quiz export
- **WHEN** the user has a connected Notion account and a ready quiz generation
- **AND** calls `POST /api/notion?action=export` with `generation_type='quiz'`
- **THEN** a Notion page is created under the target
- **AND** each question becomes a `heading_2` block
- **AND** options become `bulleted_list_item` blocks
- **AND** the correct answer is inside a `toggle` block
- **AND** the response includes `{ "exported": <question_count>, "notion_url": "<page url>" }`

#### Scenario: Export when target is a database (not a page)
- **WHEN** the user's sticky target is a Notion database
- **THEN** the system returns 422 with `{ "error": "Quiz export requires a Notion page target, not a database" }`

#### Scenario: Export of non-ready quiz generation
- **WHEN** the quiz generation status is not 'ready'
- **THEN** the endpoint returns 409 Conflict

### Requirement: Export result shown in Quiz viewer
After a successful export, the Quiz viewer SHALL display a success banner with a link to the created Notion page.

#### Scenario: Post-export success state
- **WHEN** the export completes
- **THEN** a "Exported to Notion ✓" banner appears with a clickable link to the page
