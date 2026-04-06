## 1. Database Migration

- [ ] 1.1 Run `CREATE TABLE user_integrations` migration (schema per design.md D2)
- [ ] 1.2 Run `CREATE TABLE course_export_targets` migration (schema per design.md D3 — replaces `notion_course_targets`)
- [ ] 1.3 Run `CREATE TABLE integration_source_points` migration (schema per design.md D8)
- [ ] 1.4 Run `CREATE TABLE material_selections` migration (schema per design.md D9)
- [ ] 1.5 Run `ALTER TABLE materials ADD COLUMN external_id TEXT` migration
- [ ] 1.6 Run `ALTER TABLE materials ADD COLUMN external_last_edited TEXT` migration

## 2. Backend — Export Block Builder Service

- [ ] 2.1 Create `api/services/export_blocks.py` as provider-agnostic entry point (replaces `notion_blocks.py`)
- [ ] 2.2 Create `api/services/providers/notion.py` with `rich_text()` helper that produces a Notion rich text array from a plain string
- [ ] 2.3 Add `flashcard_to_database_row(card, db_properties)` that returns a Notion page body with Name/Back/Hint properties mapped to card front/back/hint
- [ ] 2.4 Add `flashcard_to_toggle_block(card)` that returns a toggle block with front as heading, back+hint as children
- [ ] 2.5 Add `quiz_to_blocks(questions)` that returns a list of Notion blocks: heading_2 per question, bulleted_list_item per option, toggle for correct answer
- [ ] 2.6 Add `report_to_blocks(sections)` that returns a list of Notion blocks: heading_2 per section + paragraphs for content, heading_3 for sub-sections

## 3. Backend — `/api/notion.py` Core

- [ ] 3.1 Create `api/notion.py` with `class handler(BaseHTTPRequestHandler)` routing `do_GET`, `do_POST`, `do_DELETE` to action-based dispatch
- [ ] 3.2 Add `_get_notion_token(user_id)` helper: fetches encrypted token from `user_integrations`, decrypts via `crypto_utils.decrypt_api_key`, returns plaintext or None
- [ ] 3.3 Add `_notion_api(method, path, token, body=None)` helper: makes raw `requests` calls to `https://api.notion.com/v1/` with Bearer auth and `Notion-Version` header

## 4. Backend — OAuth Endpoints

- [ ] 4.1 Implement `GET /api/notion?action=auth`: generate random state, set `notion_oauth_state` cookie (HttpOnly, Secure, 10-min expiry), redirect to Notion's OAuth URL with client_id, redirect_uri, response_type=code, state
- [ ] 4.2 Implement `GET /api/notion?action=callback`: validate state cookie, exchange code via POST to Notion token endpoint, extract access_token + workspace metadata, upsert into `user_integrations`, redirect to `/profile?notion_connected=1`
- [ ] 4.3 Implement `DELETE /api/notion?action=revoke`: delete row from `user_integrations` for user + provider='notion', delete all user rows from `notion_course_targets`, return 200 or 404
- [ ] 4.4 Implement `GET /api/notion?action=status`: return `{ connected, workspace_name, workspace_icon, workspace_id }` from `user_integrations` metadata (no token exposed)

## 5. Backend — Target Picker Endpoint

- [ ] 5.1 Implement `GET /api/notion?action=search&q=<query>`: call Notion `/search` with `query` param, map results to `{ id, title, type, icon }`, return max 20 results
- [ ] 5.2 Implement `POST /api/notion?action=set_target`: upsert row into `notion_course_targets` for (user_id, course_id, generation_type) with notion_target_id/title/type
- [ ] 5.3 Implement `GET /api/notion?action=get_target&course_id=<id>&generation_type=<type>`: return existing sticky target for (user, course, generation_type) or `{ target: null }`

## 6. Backend — Export Endpoints

- [ ] 6.1 Implement `POST /api/notion?action=export` with `generation_type='flashcards'`: load generation + cards from DB, verify ownership, get/set sticky target, detect target type (database vs page), call `flashcard_to_database_row` or `flashcard_to_toggle_block`, call Notion API per card, return `{ exported, notion_url }`
- [ ] 6.2 Add database schema validation for flashcard export: call `GET /v1/databases/{id}` and verify at least one rich_text property exists; return 422 if not
- [ ] 6.3 Implement `POST /api/notion?action=export` with `generation_type='quiz'`: load quiz generation, verify target is a page (not database), call `quiz_to_blocks`, `POST /v1/blocks/{page_id}/children`, return `{ exported, notion_url }`
- [ ] 6.4 Implement `POST /api/notion?action=export` with `generation_type='report'`: load report generation (latest version), verify target is a page, call `report_to_blocks`, append blocks, return `{ exported, notion_url }`
- [ ] 6.5 Add 401-token-revoked detection in `_notion_api`: if Notion returns 401, delete the stale row from `user_integrations` and return a specific error code `notion_token_revoked` so the frontend can prompt re-auth

## 7. Frontend — ProfilePage Connected Apps Section

- [ ] 7.1 Add `NotionConnectionSection` component in `ProfilePage.jsx` that calls `GET /api/notion?action=status` on mount
- [ ] 7.2 Render connected state: workspace icon + name, "Disconnect" button that calls `DELETE /api/notion?action=revoke` and resets state
- [ ] 7.3 Render disconnected state: "Connect Notion" button that navigates to `GET /api/notion?action=auth`
- [ ] 7.4 Handle `?notion_connected=1` query param on `/profile` route to show a success toast on arrival from callback

## 8. Frontend — Notion Target Picker Component

- [ ] 8.1 Create `src/components/NotionTargetPicker.jsx`: a dropdown/modal that accepts `courseId`, `generationType`, `onSelect(target)` props
- [ ] 8.2 On open, call `GET /api/notion?action=get_target` to pre-populate with sticky target if one exists
- [ ] 8.3 Add search input that calls `GET /api/notion?action=search&q=<input>` with 300ms debounce, displays results as a list with type badges (Page / Database)
- [ ] 8.4 On selection, call `POST /api/notion?action=set_target` to persist the sticky target, then invoke `onSelect(target)`

## 9. Frontend — Export to Notion in Flashcards Viewer

- [ ] 9.1 Add "Export to Notion" button in `FlashcardViewer.jsx` (visible only when generation status is 'ready' and Notion is connected)
- [ ] 9.2 On click, open `NotionTargetPicker` if no sticky target exists for (courseId, 'flashcards'); skip picker if sticky target already set
- [ ] 9.3 On target confirmed, call `POST /api/notion?action=export` with `{ generation_id, generation_type: 'flashcards', course_id }`
- [ ] 9.4 Show success banner with Notion URL link on export completion; show error banner on failure

## 10. Frontend — Export to Notion in Quiz Viewer

- [ ] 10.1 Add "Export to Notion" button in `QuizViewer.jsx` (visible only when ready and connected)
- [ ] 10.2 Open `NotionTargetPicker` if no sticky target; call `POST /api/notion?action=export` with `generation_type: 'quiz'`
- [ ] 10.3 Show success/error banner with Notion URL

## 11. Frontend — Export to Notion in Reports Viewer

- [ ] 11.1 Add "Export to Notion" button in `ReportsViewer.jsx` (visible only when ready and connected)
- [ ] 11.2 Open `NotionTargetPicker` if no sticky target; call `POST /api/notion?action=export` with `generation_type: 'report'`
- [ ] 11.3 Show success/error banner with Notion URL

## 12. Environment & Config

- [ ] 12.1 Add `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI` to Vercel environment variables
- [ ] 12.2 Register the `NOTION_REDIRECT_URI` in the Notion developer portal integration settings

## 13. Backend — Target Picker Create-New Endpoints

- [ ] 13.1 Implement `POST /api/notion?action=create_target` with `type='page'`: call Notion `POST /v1/pages` with `parent.page_id` and title; upsert result into `course_export_targets`; return `{ id, title, type, notion_url }`
- [ ] 13.2 Implement `POST /api/notion?action=create_target` with `type='database'`: call Notion `POST /v1/databases` with hardcoded properties `Front` (title), `Back` (rich_text), `Hint` (rich_text); upsert into `course_export_targets`
- [ ] 13.3 Update `GET /api/notion?action=search` to accept optional `filter_type=page` param (used by create-new parent picker)

## 14. Backend — Source Point Endpoints

- [ ] 14.1 Implement `POST /api/notion?action=add_source_point`: validate Notion token, insert into `integration_source_points`, return created row; return 409 on duplicate
- [ ] 14.2 Implement `GET /api/notion?action=list_source_points&course_id=<id>`: return user's active source points for the course
- [ ] 14.3 Implement `DELETE /api/notion?action=remove_source_point&id=<id>`: soft-delete (set `is_active=false`) the source point owned by the requesting user
- [ ] 14.4 Implement `POST /api/notion?action=sync&course_id=<id>`: invoke `integration_poller` Lambda with `InvocationType='Event'` filtered to current user's source points for the course; return 202

## 15. Backend — Materials Selections Endpoint

- [ ] 15.1 Implement `GET /api/materials?action=selections&course_id=<id>&context=<context>`: return all accessible materials for the course with `selected` field derived from `material_selections` rows and ownership-based defaults; include `collaborator: { name, email }` for non-own materials
- [ ] 15.2 Implement `POST /api/materials?action=set_selection`: upsert `material_selections` row with `{ material_id, course_id, context, selected, provider }`

## 16. Lambda — Integration Poller

- [ ] 16.1 Create `lambda/integration_poller/` directory with `handler.py`, `requirements.txt`, `Dockerfile`, `build.sh`
- [ ] 16.2 Implement dispatcher in `handler.py`: query `integration_source_points WHERE is_active=true`, dispatch per `provider`, catch per-source-point exceptions and continue
- [ ] 16.3 Create `lambda/integration_poller/handlers/notion.py`: implement `sync_source_point(source_point, token)` — query Notion database for pages with `last_edited_time >= last_synced_at`, detect new vs updated pages
- [ ] 16.4 Implement `_notion_page_to_pdf(page_id, blocks, token)` in `handlers/notion.py`: fetch blocks (paginated), download image CDN URLs, render to PDF with `reportlab`; return PDF bytes
- [ ] 16.5 Implement new-page ingestion: upload PDF to S3 at `notion/{page_id}.pdf`, insert `materials` row (`source_type='notion'`, `visibility='private'`, `external_id`, `external_last_edited`), start `embed_materials` Step Function
- [ ] 16.6 Implement updated-page re-ingestion: delete old S3 PDF, `DELETE FROM chunks WHERE material_id=<id>`, regenerate PDF, re-upload to S3, update `materials` row, start Step Function
- [ ] 16.7 Update `integration_source_points.last_synced_at` after each successful source point sync
- [ ] 16.8 Add EventBridge Scheduler rule (rate: 2 hours) targeting `integration_poller` Lambda ARN
- [ ] 16.9 Verify `embed_materials` worker appends vs replaces chunks — if it appends, confirm step 16.6's explicit `DELETE FROM chunks` is present before re-trigger

## 17. Frontend — Target Picker Create-New UI

- [ ] 17.1 Add `+` button to `NotionTargetPicker.jsx` that toggles a create-new sub-form
- [ ] 17.2 Sub-form: type selector (Page / Database), name input, parent page search (reuses search endpoint with `filter_type=page`)
- [ ] 17.3 On confirm, call `POST /api/notion?action=create_target`; on success close sub-form and auto-select the new resource as sticky target

## 18. Frontend — Course Source Points Panel

- [ ] 18.1 Add "Notion Sources" section to course settings (or a dedicated panel in the course view) listing the user's active source points with `last_synced_at` timestamp
- [ ] 18.2 Add search-and-add flow: search Notion databases via `GET /api/notion?action=search`, filter to databases only, call `POST /api/notion?action=add_source_point` on selection
- [ ] 18.3 Add remove button per source point (calls `DELETE /api/notion?action=remove_source_point`)
- [ ] 18.4 Add "Sync Now" button that calls `POST /api/notion?action=sync&course_id=<id>` and shows a "Syncing…" indicator

## 19. Frontend — Material Picker Refactor (ChatTab, Quiz, Flashcards, Reports)

- [ ] 19.1 Replace localStorage-based selection with `GET /api/materials?action=selections` call on mount; populate picker from response
- [ ] 19.2 Split picker into two sections: "My materials" (own, default selected) and "From collaborators" (public non-own, default unselected)
- [ ] 19.3 On toggle, call `POST /api/materials?action=set_selection` to persist the change
- [ ] 19.4 Add hover tooltip to collaborator material items: 3-line tooltip showing collaborator name, full material title, and email (see design.md D14)
- [ ] 19.5 Apply refactor to all four components: `ChatTab.jsx`, `Quiz.jsx`, `Flashcards.jsx`, `Reports.jsx`
