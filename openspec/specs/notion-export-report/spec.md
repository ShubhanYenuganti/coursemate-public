# notion-export-report Specification

## Purpose
TBD - created by archiving change notion-integration. Update Purpose after archive.
## Requirements
### Requirement: Report exports as a structured Notion page
`POST /api/notion?action=export` with `generation_type='report'` SHALL create a child Notion page under the user's selected target page. The page title SHALL be the report's `title` field. The subtitle SHALL be a `paragraph` block with italic formatting. Each entry in `sections[]` SHALL become a `heading_2` block followed by `paragraph` blocks for its content. If a section has sub-sections, those SHALL use `heading_3` blocks.

#### Scenario: Successful report export
- **WHEN** the user has a connected Notion account and a ready report generation
- **AND** calls `POST /api/notion?action=export` with `{ exports: [{ generation_id, generation_type: 'report', targets: [{ provider: 'notion', target_id }] }] }`
- **THEN** a Notion page is created under the target
- **AND** the page title matches the report title
- **AND** each section maps to a heading_2 + paragraphs
- **AND** the result entry includes `{ status: 'success', exported_count: <section_count>, url: '<page url>' }`

#### Scenario: Export when target is not a page
- **WHEN** the `target_id` resolves to a Notion database or other non-page type
- **THEN** the endpoint returns 422 with `{ "error": "Report export requires a Notion page target, not a database" }`

#### Scenario: Export of non-ready report generation
- **WHEN** the report generation status is not 'ready'
- **THEN** the result entry has `status: 'error'` and `error: 'Generation not ready'`

### Requirement: Export modal filters target picker to pages only
The Reports export modal SHALL open `NotionTargetPicker` with `allowedTypes: ['page']`. The picker SHALL only show and allow selection of Notion pages. The `+ Create new` sub-form SHALL only offer "Page" as a type option when `allowedTypes` excludes databases.

### Requirement: Invalid sticky target shown with warning in Reports modal
If the saved sticky target for (user, course, 'report') has `external_target_type = 'database'`, the export modal SHALL render the target with a warning icon (⚠). On hover, the tooltip SHALL read: "This target is invalid for report exports. Select a Notion page." The export button SHALL be disabled until the user selects a valid page target.

#### Scenario: Sticky target is a database
- **WHEN** the user opens the reports export modal
- **AND** the saved sticky target is a Notion database
- **THEN** the target is shown with a warning icon
- **AND** the export button is disabled
- **AND** clicking the target opens the picker filtered to pages only
- **AND** selecting a valid page clears the warning and enables export

### Requirement: Export result shown in Reports viewer
After a successful export, the Reports viewer SHALL display a success banner with a link to the created Notion page.

#### Scenario: Post-export success state
- **WHEN** the export completes
- **THEN** a "Exported to Notion ✓" banner appears with a clickable link to the Notion page

