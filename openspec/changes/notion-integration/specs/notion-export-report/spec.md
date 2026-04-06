## ADDED Requirements

### Requirement: Report exports as a structured Notion page
`POST /api/notion?action=export` with `generation_type='report'` SHALL create a child Notion page under the user's selected target page. The page title SHALL be the report's `title` field. The subtitle SHALL be a `paragraph` block with italic formatting. Each entry in `sections[]` SHALL become a `heading_2` block followed by `paragraph` blocks for its content. If a section has sub-sections, those SHALL use `heading_3` blocks.

#### Scenario: Successful report export
- **WHEN** the user has a connected Notion account and a ready report generation
- **AND** calls `POST /api/notion?action=export` with `generation_type='report'`
- **THEN** a Notion page is created under the target
- **AND** the page title matches the report title
- **AND** each section maps to a heading_2 + paragraphs
- **AND** the response includes `{ "exported": <section_count>, "notion_url": "<page url>" }`

#### Scenario: Export when target is a database
- **WHEN** the user's sticky target is a Notion database
- **THEN** the system returns 422 with `{ "error": "Report export requires a Notion page target, not a database" }`

#### Scenario: Export of non-ready report generation
- **WHEN** the report generation status is not 'ready'
- **THEN** the endpoint returns 409 Conflict

### Requirement: Export result shown in Reports viewer
After a successful export, the Reports viewer SHALL display a success banner with a link to the created Notion page.

#### Scenario: Post-export success state
- **WHEN** the export completes
- **THEN** a "Exported to Notion ✓" banner appears with a clickable link to the Notion page
