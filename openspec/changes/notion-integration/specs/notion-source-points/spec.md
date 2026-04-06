## ADDED Requirements

### Requirement: User can add a Notion database as a course source point
`POST /api/notion?action=add_source_point` SHALL insert a row into `integration_source_points` for (user_id, course_id, provider='notion', external_id). The user must be connected to Notion and a member or owner of the course. Each user may have multiple source points per course, and multiple users may independently watch the same or different databases within the same course.

#### Scenario: Adding a new source point
- **WHEN** an authenticated connected user calls `POST /api/notion?action=add_source_point` with `{ course_id: 3, database_id: 'abc123', database_title: 'Lecture Notes' }`
- **THEN** a row is inserted into `integration_source_points` with `provider='notion'`, `external_id='abc123'`, `last_synced_at=NULL`
- **AND** the response returns `{ id, external_id, external_title, last_synced_at, is_active }`

#### Scenario: Adding a duplicate source point
- **WHEN** the user adds a source point for a (course, database) they already watch
- **THEN** the endpoint returns 409 Conflict with `{ "error": "Source point already exists" }`

#### Scenario: Adding source point while disconnected
- **WHEN** the user has no stored Notion token
- **THEN** the endpoint returns 403 Forbidden with `{ "error": "Notion not connected" }`

### Requirement: User can list and remove source points per course
`GET /api/notion?action=list_source_points&course_id=<id>` SHALL return all of the current user's active source points for that course. `DELETE /api/notion?action=remove_source_point&id=<id>` SHALL set `is_active=false` (soft delete) for the given source point owned by the requesting user.

#### Scenario: Listing source points
- **WHEN** `GET /api/notion?action=list_source_points&course_id=3`
- **THEN** the response returns an array of the user's source points: `[{ id, external_id, external_title, last_synced_at, is_active }]`
- **AND** only the requesting user's source points are returned (not other collaborators')

#### Scenario: Removing a source point
- **WHEN** `DELETE /api/notion?action=remove_source_point&id=7`
- **THEN** `integration_source_points.is_active` is set to `false` for row 7
- **AND** existing materials ingested from that source point are NOT deleted (they remain as course materials)
- **AND** the poller will no longer process that source point

### Requirement: New Notion pages are automatically ingested as course materials
When the integration poller runs, for each active `integration_source_points` row with `provider='notion'`, it SHALL query the Notion database for pages with `last_edited_time >= last_synced_at` (or all pages if `last_synced_at` is NULL). New pages (no matching `materials.external_id`) SHALL be converted to PDF and ingested.

Ingestion steps:
1. Fetch all blocks for the page via `GET /v1/blocks/{page_id}/children` (paginated)
2. Download image block files from Notion CDN
3. Render blocks + images to PDF using `reportlab`
4. Upload PDF to S3 at key `notion/{page_id}.pdf`
5. Insert row into `materials` with `source_type='notion'`, `external_id=page_id`, `external_last_edited=last_edited_time`, `visibility='private'`, `uploaded_by=source_point.user_id`, `course_id=source_point.course_id`
6. Start `embed_materials` Step Function execution with `{ s3_key: 'notion/{page_id}.pdf', cursor: 0 }`
7. Update `integration_source_points.last_synced_at` to current timestamp

#### Scenario: New page detected in watched database
- **WHEN** the poller runs and finds a Notion page with no corresponding `materials.external_id`
- **THEN** the page is converted to PDF, uploaded to S3, and `embed_materials` Step Function is triggered
- **AND** a new `materials` row is created with `source_type='notion'`, `visibility='private'`
- **AND** the material is owned by the user who owns the source point

#### Scenario: First sync (last_synced_at is NULL)
- **WHEN** a source point has never been synced
- **THEN** all pages in the database are fetched and ingested
- **AND** `last_synced_at` is updated after processing

### Requirement: Updated Notion pages are re-ingested
When the poller detects a page whose `last_edited_time` is newer than its corresponding `materials.external_last_edited`, it SHALL re-ingest the page.

Re-ingestion steps:
1. Delete the existing S3 PDF at `notion/{page_id}.pdf`
2. Delete all `chunks` rows WHERE `material_id = <existing material id>`
3. Regenerate PDF from current Notion blocks (same as new-page ingestion steps 1–4)
4. Update the existing `materials` row: `external_last_edited`, `file_url` if key changed
5. Trigger `embed_materials` Step Function (same as new-page step 6)

#### Scenario: Updated page detected
- **WHEN** the poller finds a page whose Notion `last_edited_time` is newer than `materials.external_last_edited`
- **THEN** the old S3 PDF is deleted, old chunks are cleared, and a fresh PDF is generated and re-ingested
- **AND** the existing `materials` row is updated (not replaced)

#### Scenario: Page with no text or image content
- **WHEN** a Notion page contains only unsupported block types (e.g. empty page)
- **THEN** the poller skips the page and logs a warning; no material row is created

### Requirement: Polling runs every ~2 hours via EventBridge Scheduler
An AWS EventBridge Scheduler rule SHALL invoke the `integration_poller` Lambda on a fixed rate schedule (every 2 hours). The Lambda SHALL process all active source points across all users and providers within a single invocation.

#### Scenario: Poller processes multiple source points
- **WHEN** EventBridge triggers the `integration_poller` Lambda
- **THEN** all rows in `integration_source_points` WHERE `is_active=true` are processed in sequence
- **AND** each source point's `last_synced_at` is updated after successful processing
- **AND** failures on one source point do not abort processing of others (continue-on-error)

### Requirement: User can trigger an immediate manual sync
`POST /api/notion?action=sync&course_id=<id>` SHALL directly invoke the `integration_poller` Lambda (AWS SDK `invoke` with `InvocationType=Event`) filtered to the requesting user's source points for that course. The response SHALL return 202 Accepted immediately; sync runs asynchronously.

#### Scenario: Manual sync triggered
- **WHEN** the user clicks "Sync Now" for a course
- **THEN** `POST /api/notion?action=sync&course_id=3` returns 202 immediately
- **AND** the poller Lambda is invoked asynchronously for only this user's source points in course 3
- **AND** the UI shows a "Syncing…" indicator; on next page load the updated `last_synced_at` is visible

### Requirement: Ingested Notion materials are private by default
Materials created by the poller SHALL be inserted with `visibility='private'`. They are visible only to the owning user until explicitly set to public.

#### Scenario: Notion material not visible to collaborators by default
- **WHEN** collaborator A's poller ingests pages from their source point into a shared course
- **THEN** those materials do NOT appear in collaborator B's "available collaborator materials" pool
- **UNTIL** collaborator A sets `visibility='public'` on those materials
