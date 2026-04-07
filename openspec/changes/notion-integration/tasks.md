## 1. Database Migration

- [x] 1.1 Run `CREATE TABLE user_integrations` migration (schema per design.md D2)
- [x] 1.2 Run `CREATE TABLE course_export_targets` migration (schema per design.md D3 — replaces `notion_course_targets`)
- [x] 1.3 Run `CREATE TABLE integration_source_points` migration (schema per design.md D8)
- [x] 1.4 Run `CREATE TABLE material_selections` migration (schema per design.md D9)
- [x] 1.5 Run `ALTER TABLE materials ADD COLUMN external_id TEXT` migration
- [x] 1.6 Run `ALTER TABLE materials ADD COLUMN external_last_edited TEXT` migration

## 2. Backend — Export Block Builder Service

- [x] 2.1 Create `api/services/export_blocks.py` as provider-agnostic entry point (replaces `notion_blocks.py`)
- [x] 2.2 Create `api/services/providers/notion.py` with `rich_text()` helper that produces a Notion rich text array from a plain string
- [x] 2.3 Add `flashcard_to_toggle_block(card)` that returns a toggle block with front as heading, back+hint as children
- [x] 2.4 Add `quiz_to_blocks(questions)` that returns a list of Notion blocks: heading_2 per question, bulleted_list_item per option, toggle for correct answer
- [x] 2.5 Add `report_to_blocks(sections)` that returns a list of Notion blocks: heading_2 per section + paragraphs for content, heading_3 for sub-sections

## 3. Backend — `/api/notion.py` Core

- [x] 3.1 Create `api/notion.py` with `class handler(BaseHTTPRequestHandler)` routing `do_GET`, `do_POST`, `do_DELETE`, `do_PATCH` to action-based dispatch
- [x] 3.2 Add `_get_notion_token(user_id)` helper: fetches encrypted token from `user_integrations`, decrypts via `crypto_utils.decrypt_api_key`, returns plaintext or None
- [x] 3.3 Add `_notion_api(method, path, token, body=None)` helper: makes raw `requests` calls to `https://api.notion.com/v1/` with Bearer auth and `Notion-Version` header

## 4. Backend — OAuth Endpoints

- [x] 4.1 Implement `GET /api/notion?action=auth`: generate random state, set `notion_oauth_state` cookie (HttpOnly, Secure, 10-min expiry), redirect to Notion's OAuth URL with client_id, redirect_uri, response_type=code, state
- [x] 4.2 Implement `GET /api/notion?action=callback`: validate state cookie, exchange code via POST to Notion token endpoint, extract access_token + workspace metadata, upsert into `user_integrations`, redirect to `/profile?notion_connected=1`
- [x] 4.3 Implement `DELETE /api/notion?action=revoke`: delete row from `user_integrations` for user + provider='notion', delete all user rows from `course_export_targets`, return 200 or 404
- [x] 4.4 Implement `GET /api/notion?action=status`: return `{ connected, workspace_name, workspace_icon, workspace_id }` from `user_integrations` metadata (no token exposed)

## 5. Backend — Target Picker Endpoint

- [x] 5.1 Implement `GET /api/notion?action=search&q=<query>`: call Notion `/search` with `query` param, map results to `{ id, title, type, icon }`, return max 20 results; accept optional `filter_type=page|database` param to restrict result types
- [x] 5.2 Implement `POST /api/notion?action=set_target`: upsert row into `course_export_targets` for (user_id, course_id, generation_type) with target id/title/type
- [x] 5.3 Implement `GET /api/notion?action=get_target&course_id=<id>&generation_type=<type>`: return existing sticky target for (user, course, generation_type) or `{ target: null }`

## 6. Backend — Export Endpoint (Shape C Batch Envelope)

- [x] 6.1 Implement `POST /api/notion?action=export`: accept Shape C body `{ exports: [{ generation_id, generation_type, targets: [{ provider, target_id }] }] }`; dispatch each (generation, target) pair to the appropriate export handler; always return 207 Multi-Status with `{ total, succeeded, failed, results[] }`
- [x] 6.2 Implement flashcard export handler: load generation + cards from DB, verify ownership, call `flashcard_to_toggle_block` for all cards, call `POST /v1/blocks/{page_id}/children` once; return success result entry with `exported_count` and `url`; return error entry if target is not a page (422-class) or generation not ready
- [x] 6.3 Implement quiz export handler: load quiz generation, verify target is a page, call `quiz_to_blocks`, `POST /v1/blocks/{page_id}/children`; return result entry
- [x] 6.4 Implement report export handler: load report generation, verify target is a page, call `report_to_blocks`, append blocks to page; return result entry
- [x] 6.5 Add 401-token-revoked detection in `_notion_api`: if Notion returns 401, delete the stale row from `user_integrations` and return a specific error code `notion_token_revoked` so the frontend can prompt re-auth
- [x] 6.6 Add unknown-provider guard in the batch dispatcher: if `targets[n].provider` is not 'notion', return an error result entry with `error: 'Unsupported provider: <name>'`; do not abort remaining entries

## 7. Frontend — ProfilePage Connected Apps Section

- [x] 7.1 Add `NotionConnectionSection` component in `ProfilePage.jsx` that calls `GET /api/notion?action=status` on mount
- [x] 7.2 Render connected state: workspace icon + name, "Disconnect" button that calls `DELETE /api/notion?action=revoke` and resets state
- [x] 7.3 Render disconnected state: "Connect Notion" button that navigates to `GET /api/notion?action=auth`
- [x] 7.4 Handle `?notion_connected=1` query param on `/profile` route to show a success toast on arrival from callback

## 8. Frontend — Notion Target Picker Component

- [x] 8.1 Create `src/components/NotionTargetPicker.jsx`: a dropdown/modal that accepts `courseId`, `generationType`, `allowedTypes`, `onSelect(target)` props
- [x] 8.2 On open, call `GET /api/notion?action=get_target` to pre-populate with sticky target if one exists
- [x] 8.3 Add search input that calls `GET /api/notion?action=search&q=<input>` with 300ms debounce; filter displayed results client-side to match `allowedTypes` (e.g. hide databases when `allowedTypes=['page']`); display results as a list with type badges
- [x] 8.4 On selection, call `POST /api/notion?action=set_target` to persist the sticky target, then invoke `onSelect(target)`
- [x] 8.5 In `+ Create new` sub-form, only render type options that appear in `allowedTypes`; if `allowedTypes=['page']`, show only "Page" (no Database option)

## 9. Frontend — Export to Notion in Flashcards Viewer

- [x] 9.1 Add "Export to Notion" button in `FlashcardViewer.jsx` (visible only when generation status is 'ready' and Notion is connected)
- [x] 9.2 On click, open `NotionTargetPicker` with `allowedTypes: ['page']` if no sticky target exists; skip picker if a valid page sticky target is already set; if sticky target is a database, show warning icon (⚠) with tooltip "This target is invalid for flashcard exports. Select a Notion page." and disable the export button until user selects a valid page
- [x] 9.3 On target confirmed, call `POST /api/notion?action=export` with Shape C body: `{ exports: [{ generation_id, generation_type: 'flashcards', targets: [{ provider: 'notion', target_id }] }] }`
- [x] 9.4 Show success banner with Notion URL link on export completion; show error banner on failure; handle 207 partial failure by reading `results[0].status`

## 10. Frontend — Export to Notion in Quiz Viewer

- [x] 10.1 Add "Export to Notion" button in `QuizViewer.jsx` (visible only when ready and connected)
- [x] 10.2 Open `NotionTargetPicker` with `allowedTypes: ['page']`; apply same invalid-sticky-target guard as 9.2 (warning icon + disabled export if sticky is a database)
- [x] 10.3 Call `POST /api/notion?action=export` with Shape C body using `generation_type: 'quiz'`
- [x] 10.4 Show success/error banner with Notion URL; handle 207 result

## 11. Frontend — Export to Notion in Reports Viewer

- [x] 11.1 Add "Export to Notion" button in `ReportsViewer.jsx` (visible only when ready and connected)
- [x] 11.2 Open `NotionTargetPicker` with `allowedTypes: ['page']`; apply same invalid-sticky-target guard as 9.2
- [x] 11.3 Call `POST /api/notion?action=export` with Shape C body using `generation_type: 'report'`
- [x] 11.4 Show success/error banner with Notion URL; handle 207 result

## 12. Environment & Config

- [x] 12.1 Add `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI` to Vercel environment variables
- [x] 12.2 Register the `NOTION_REDIRECT_URI` in the Notion developer portal integration settings

## 13. Backend — Target Picker Create-New Endpoints

- [x] 13.1 Implement `POST /api/notion?action=create_target` with `type='page'`: call Notion `POST /v1/pages` with `parent.page_id` and title; upsert result into `course_export_targets`; return `{ id, title, type, notion_url }`

## 14. Backend — Source Point Endpoints

- [x] 14.1 Implement `POST /api/notion?action=add_source_point`: validate Notion token, insert into `integration_source_points` with `is_active=true`, return created row; return 409 on duplicate
- [x] 14.2 Implement `GET /api/notion?action=list_source_points&course_id=<id>`: return all of the user's source points for the course (both active and disabled — do not filter by `is_active`)
- [x] 14.3 Implement `PATCH /api/notion?action=toggle_source_point&id=<id>`: flip `is_active` for the source point owned by the requesting user; return updated row
- [x] 14.4 Implement `DELETE /api/notion?action=remove_source_point&id=<id>`: permanently delete the row from `integration_source_points` for the source point owned by the requesting user; return 204
- [x] 14.5 Implement `POST /api/notion?action=sync&course_id=<id>`: invoke `integration_poller` Lambda with `InvocationType='Event'` filtered to current user's **active** source points for the course; return 202

## 15. Backend — Materials Selections Endpoint

- [x] 15.1 Implement `GET /api/materials?action=selections&course_id=<id>&context=<context>`: return all accessible materials for the course with `selected` field derived from `material_selections` rows and ownership-based defaults; include `collaborator: { name, email }` for non-own materials
- [x] 15.2 Implement `POST /api/materials?action=set_selection`: upsert `material_selections` row with `{ material_id, course_id, context, selected, provider }`

## 16. Lambda — Integration Poller

- [x] 16.1 Create `lambda/integration_poller/` directory with `handler.py`, `requirements.txt`, `Dockerfile`, `build.sh`
- [x] 16.2 Implement dispatcher in `handler.py`: query `integration_source_points WHERE is_active=true`, dispatch per `provider`, catch per-source-point exceptions and continue
- [x] 16.3 Create `lambda/integration_poller/handlers/notion.py`: implement `sync_source_point(source_point, token)` — query Notion database for pages with `last_edited_time >= last_synced_at`, detect new vs updated pages
- [x] 16.4 Implement `_notion_page_to_pdf(page_id, blocks, token)` in `handlers/notion.py`: fetch blocks (paginated), download image CDN URLs, render to PDF with `reportlab`; return PDF bytes
- [x] 16.5 Implement new-page ingestion: upload PDF to S3 at `notion/{page_id}.pdf`, insert `materials` row (`source_type='notion'`, `visibility='private'`, `external_id`, `external_last_edited`), start `embed_materials` Step Function
- [x] 16.6 Implement updated-page re-ingestion: delete old S3 PDF, `DELETE FROM chunks WHERE material_id=<id>`, regenerate PDF, re-upload to S3, update `materials` row, start Step Function
- [x] 16.7 Update `integration_source_points.last_synced_at` after each successful source point sync
- [x] 16.8 Add EventBridge Scheduler rule (rate: 2 hours) targeting `integration_poller` Lambda ARN — documented in build.sh
- [x] 16.9 Verify `embed_materials` worker appends vs replaces chunks — confirmed APPENDS; explicit DELETE FROM chunks/documents in 16.6 is load-bearing

## 17. Frontend — Target Picker Create-New UI

- [x] 17.1 Add `+` button to `NotionTargetPicker.jsx` that toggles a create-new sub-form
- [x] 17.2 Sub-form: name input, parent page search (reuses search endpoint with `filter_type=page`); show type selector (Page / Database) only when `allowedTypes` includes both — for export contexts (`allowedTypes=['page']`) show only "Page"
- [x] 17.3 On confirm, call `POST /api/notion?action=create_target`; on success close sub-form and auto-select the new resource as sticky target

## 18. Frontend — Overview Tab Access (Prerequisite)

The Overview tab (`home`) in `CoursePage.jsx` is currently gated entirely behind `isOwner`. The Notion source points panel and per-user export target settings must live here, so the tab must be accessible to all course members (owners and collaborators alike). Owner-only sub-elements within the panel (description edit button, SharingAccessModal) keep their existing `isOwner` guards.

- [x] 18.1 Remove `isOwner` guard from the Overview toolbar item (lines ~256-261 in `CoursePage.jsx`) so the tab button is visible to all course members
- [x] 18.2 Remove `isOwner` guard from the `activeTab === 'home'` content block so the panel renders for all members
- [x] 18.3 Remove the collaborator default-tab redirect in the `useState` initializer (`saved === 'home' && !isOwner ? 'materials' : saved`) so collaborators can land on and return to the Overview tab

## 19. Frontend — Course Source Points Panel

- [x] 19.1 Add "Notion Sources" section to the Overview panel listing all of the user's source points (active and disabled) with `last_synced_at` timestamp and `is_active` state
- [x] 19.2 Add search-and-add flow: search Notion databases via `GET /api/notion?action=search&filter_type=database`, call `POST /api/notion?action=add_source_point` on selection
- [x] 19.3 Add disable/enable toggle per source point (calls `PATCH /api/notion?action=toggle_source_point`); disabled source points remain visible, greyed out, with an "Enable" affordance
- [x] 19.4 Add remove button per source point (calls `DELETE /api/notion?action=remove_source_point`); confirm before deleting as this action is permanent
- [x] 19.5 Add "Sync Now" button that calls `POST /api/notion?action=sync&course_id=<id>` and shows a "Syncing…" indicator

## 20. Frontend — Material Picker Refactor (ChatTab, Quiz, Flashcards, Reports)

- [x] 20.1 Replace localStorage-based selection with `GET /api/materials?action=selections` call on mount; populate picker from response
- [x] 20.2 Split picker into two sections: "My materials" (own, default selected) and "From collaborators" (public non-own, default unselected)
- [x] 20.3 On toggle, call `POST /api/materials?action=set_selection` to persist the change
- [x] 20.4 Add hover tooltip to collaborator material items: 3-line tooltip showing collaborator name, full material title, and email (see design.md D14)
- [x] 20.5 Apply refactor to all four components: `ChatTab.jsx`, `Quiz.jsx`, `Flashcards.jsx`, `Reports.jsx`

## 21. Documentation — README Update

- [x] 21.1 Add "Notion Integration" section to `README.md` covering: OAuth connection flow, sticky export targets, export capabilities (flashcards → toggle blocks on page, quiz → page, report → page), and create-new destination support
- [x] 21.2 Document Notion source points: how collaborators can each connect independent Notion databases to a shared course, disable/enable without losing data, and how the ~2-hour poller feeds pages into the embedding pipeline
- [x] 21.3 Document material selection persistence: per-user, per-context selections with collaborator material opt-in pool and hover metadata
- [x] 21.4 Document required environment variables: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI`, and where to register the redirect URI in the Notion developer portal
