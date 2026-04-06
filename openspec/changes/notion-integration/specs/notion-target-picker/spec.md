## ADDED Requirements

### Requirement: User can search Notion pages and databases
`GET /api/notion?action=search&q=<query>` SHALL call Notion's `/search` API using the user's stored access token and return a filtered list of pages and databases matching the query. Results SHALL include `id`, `title`, `type` ('page' | 'database'), and `icon` for display. The endpoint SHALL return a maximum of 20 results. An optional `filter_type` query param (`page` | `database`) SHALL restrict results to that type only.

#### Scenario: Search returns matching results
- **WHEN** an authenticated connected user calls `GET /api/notion?action=search&q=robotics`
- **THEN** the response includes a list of Notion pages and databases whose titles contain "robotics"
- **AND** each result has `id`, `title`, `type`, and `icon`

#### Scenario: Empty query returns recent pages
- **WHEN** `q` is empty or omitted
- **THEN** the endpoint returns up to 20 recently edited pages/databases from the workspace

#### Scenario: Search while disconnected
- **WHEN** the user has no stored Notion token
- **THEN** the endpoint returns 403 Forbidden with `{ "error": "Notion not connected" }`

### Requirement: Sticky target is saved per user/course/generation_type
`POST /api/notion?action=set_target` SHALL upsert a row in `course_export_targets` with `provider='notion'`, the chosen `external_target_id`, `external_target_title`, `external_target_type`, `course_id`, and `generation_type`. On subsequent export actions for the same (user, course, generation_type), this target SHALL be used as the default without re-prompting the user.

#### Scenario: First-time target selection
- **WHEN** the user selects a Notion destination for a flashcard generation from course 5
- **THEN** a row is inserted into `course_export_targets` with generation_type='flashcards', course_id=5
- **AND** subsequent flashcard exports from course 5 default to that destination

#### Scenario: Re-selecting a different target
- **WHEN** the user selects a different Notion destination for the same (course, generation_type)
- **THEN** the existing row in `course_export_targets` is updated (upsert)

### Requirement: Picker accepts an allowedTypes constraint
`NotionTargetPicker` SHALL accept an `allowedTypes` prop (array of `'page'` | `'database'`). When set, the picker SHALL only display and allow selection of results matching those types. Search results SHALL be filtered client-side after the API call (or by passing `filter_type` to the search endpoint). The `+ Create new` sub-form SHALL only offer type options present in `allowedTypes`.

#### Scenario: Picker restricted to pages only
- **WHEN** `NotionTargetPicker` is opened with `allowedTypes: ['page']`
- **THEN** search results show only Notion pages (databases are hidden)
- **AND** the `+ Create new` sub-form shows only "Page" as a type option

#### Scenario: Picker with no allowedTypes (default)
- **WHEN** `allowedTypes` is not passed or is `['page', 'database']`
- **THEN** both pages and databases appear in search results and create-new options

### Requirement: Export UI shows current sticky target
In the export picker UI, if a sticky target already exists for the (course, generation_type), the picker SHALL pre-select that target. The user MAY change it before exporting, which SHALL update the sticky target.

#### Scenario: Returning user sees remembered target
- **WHEN** the user opens "Export to Notion" for a course where a target was previously saved
- **THEN** the picker shows the saved target pre-selected
- **AND** the user can export immediately without re-selecting

#### Scenario: New user or new course/type has no default
- **WHEN** no sticky target exists for the (user, course, generation_type)
- **THEN** the picker opens with no pre-selection and prompts the user to search

### Requirement: User can create a new Notion page from the picker
The picker SHALL include a `+ Create new` button. When clicked, a sub-form SHALL appear allowing the user to: enter a name and search for a parent page to nest under. If `allowedTypes` includes `'database'`, the sub-form SHALL also offer a type selector (Page or Database). On confirmation, the backend SHALL call `POST /v1/pages` and auto-select the created resource as the sticky target.

#### Scenario: Creating a new page as export destination
- **WHEN** the user clicks `+ Create new`, enters name "Quiz Answers", picks parent "Study Vault"
- **THEN** `POST /api/notion?action=create_target` is called with `{ type: 'page', name: 'Quiz Answers', parent_id: '<Study Vault id>' }`
- **AND** the backend creates the page via Notion API and upserts it into `course_export_targets`
- **AND** the picker closes with the new page pre-selected

#### Scenario: Parent page search in create-new sub-form
- **WHEN** the user types in the parent page search field
- **THEN** `GET /api/notion?action=search` is called with `filter_type=page`
- **AND** results appear as a list to select from
