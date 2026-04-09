## 1. Environment & OAuth App Setup

- [x] 1.1 Create a Google Cloud project and enable the Drive API and Google Docs API
- [x] 1.2 Create an OAuth 2.0 client ID (Web application type) with the callback URI `<app-url>/api/gdrive?action=callback`
- [x] 1.3 Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` to `.env` and Vercel environment variables
- [x] 1.4 Add the same three env vars to the Lambda integration_poller environment configuration

## 2. Backend OAuth Flow (`api/gdrive.py`)

- [x] 2.1 Create `api/gdrive.py` with a top-level `handler(request, response)` function and action dispatcher (mirrors `api/notion.py` structure)
- [x] 2.2 Implement `action=auth` — generate state token, store in session, redirect to Google OAuth consent URL with `drive.readonly` and `drive.file` scopes and `access_type=offline`
- [x] 2.3 Implement `action=callback` — validate state token, exchange code for tokens (access + refresh + expires_in), encrypt JSON payload, upsert into `user_integrations` with `provider="gdrive"`; handle SameSite fallback via `gdrive_pending_token` cookie + redirect to `/profile?gdrive_pending=1`
- [x] 2.4 Implement `action=finalize_connection` — read `gdrive_pending_token` cookie, decrypt, store token in `user_integrations`, clear cookie
- [x] 2.5 Implement `get_valid_token(user_id, db)` helper — decrypt stored JSON, check `expires_at`, call Google token refresh endpoint if within 5 minutes of expiry, re-encrypt and store fresh token, return valid access token; raise 401 if refresh fails
- [x] 2.6 Implement `action=status` — return connection state and Google account email (fetch from `https://www.googleapis.com/oauth2/v2/userinfo` using stored token)
- [x] 2.7 Implement `action=revoke` — delete `user_integrations` row for user and provider `"gdrive"`

## 3. Backend Source Point Endpoints (`api/gdrive.py` continued)

- [x] 3.1 Implement `action=add_source_point` — validate Drive folder ID is accessible (call Drive API `files.get` on the folder), upsert `integration_source_points` with `provider="gdrive"` and the folder ID as `external_id`, return new source point; return 409 on duplicate, 403 on inaccessible folder
- [x] 3.2 Implement `action=list_source_points` — return all `integration_source_points` for given `course_id` and `provider="gdrive"`
- [x] 3.3 Implement `action=toggle_source_point` — update `is_active` on `integration_source_points`
- [x] 3.4 Implement `action=remove_source_point` — delete `integration_source_points` record
- [x] 3.5 Implement `action=sync` — trigger Lambda integration poller for the course's Drive source points (POST to SQS or Step Functions, same as Notion sync)

## 4. Backend Export Endpoints (`api/gdrive.py` + service module)

- [x] 4.1 Create `api/services/providers/gdrive.py` with `flashcard_to_doc_requests()`, `quiz_to_doc_requests()`, `report_to_doc_requests()` returning Google Docs API `batchUpdate` request arrays
- [x] 4.2 Implement `action=export` — create a new Google Doc in the target folder using Google Docs API, apply formatted content via `batchUpdate`, return the Doc URL
- [x] 4.3 Implement `action=set_target` — upsert `course_export_targets` with `provider="gdrive"`, storing folder ID and name
- [x] 4.4 Implement `action=get_target` — return saved `course_export_targets` entry for user/course/generation_type and provider `"gdrive"`
- [x] 4.5 Implement `action=search` — query Drive API for folders matching search term (`mimeType='application/vnd.google-apps.folder'`), or list recent folders if no term; return list of `{id, name}` objects

## 5. Lambda Poller Handler (`lambda/integration_poller/handlers/gdrive.py`)

- [x] 5.1 Create `handlers/gdrive.py` with `sync_source_point(source_point, token, force_full_sync)` function (mirrors `handlers/notion.py`); source point `external_id` is a Drive folder ID
- [x] 5.2 Implement token validation and refresh within the Lambda handler using the same encrypted JSON pattern
- [x] 5.3 Implement `_list_folder_files(folder_id, token)` — call Drive API `files.list` with `q="'<folder_id>' in parents and trashed=false"` to enumerate all files in the source point folder; return list of `{id, name, mimeType, modifiedTime}`
- [x] 5.4 Implement `_get_drive_file_as_pdf(file_id, mime_type, token)` — use Drive `files.export` for Google Docs/Sheets/Slides (`mimeType=application/pdf`); use `files.get?alt=media` for native PDFs; raise error if file > 50 MB
- [x] 5.5 Implement change detection per file — for each file returned by `_list_folder_files`, look up existing material by `external_id` (Drive file ID); skip if `modifiedTime` matches `external_last_edited`; mark inactive if file no longer present in folder listing
- [x] 5.6 Implement `_upsert_material()` — create/update materials record with `external_id` (Drive file ID, not folder ID) and `external_last_edited` (Drive file `modifiedTime`); re-use existing pattern from Notion handler
- [x] 5.7 Integrate with existing S3 upload (`_upload_pdf_to_s3`) and embed pipeline (`_enqueue_embed_job`, `_delete_old_chunks`) — identical calls to Notion handler; called per file within the folder
- [x] 5.8 Register `gdrive` handler in the Lambda dispatcher (wherever Notion handler is registered in the poller entry point)

## 6. Frontend — Profile Page Connection UI

- [x] 6.1 Add `GDriveConnectionSection` component to `ProfilePage.jsx` (mirrors `NotionConnectionSection`) — shows connected state with Google account email, or "Connect Google Drive" button when not connected
- [x] 6.2 Wire "Connect" button to `window.location = "/api/gdrive?action=auth"`
- [x] 6.3 Wire "Disconnect" button to DELETE `/api/gdrive?action=revoke` with confirmation dialog
- [x] 6.4 Detect `?gdrive_pending=1` query param on profile page load and call `GET /api/gdrive?action=finalize_connection`, then reload connection status

## 7. Frontend — Drive Target Picker

- [x] 7.1 Create `GDriveTargetPicker.jsx` component (mirrors `NotionTargetPicker.jsx`) — modal with search input for Drive folders, confirm/cancel buttons, loading and error states
- [x] 7.2 Implement folder search calling `GET /api/gdrive?action=search&q=<term>`; show recent folders when search is empty
- [x] 7.3 On confirm, call `POST /api/gdrive?action=set_target` to persist selection and trigger `POST /api/gdrive?action=export` with selected folder ID
- [x] 7.4 Load saved target on mount via `GET /api/gdrive?action=get_target` and pre-select it in the picker

## 8. Frontend — Export Integration

- [x] 8.1 Add "Export to Google Drive" option to the flashcard export UI (alongside existing Notion export), showing `GDriveTargetPicker` when no sticky target is set
- [x] 8.2 Add "Export to Google Drive" option to the quiz export UI
- [x] 8.3 Add "Export to Google Drive" option to the report export UI
- [x] 8.4 Display exported Doc URL as a clickable link after successful export (mirrors Notion export success state)

## 9. Verification

- [ ] 9.1 Verify full OAuth flow end-to-end: connect → Profile shows email → disconnect → Profile shows connect button
- [ ] 9.2 Verify SameSite finalize flow works (test by simulating cross-site redirect)
- [ ] 9.3 Verify token auto-refresh: manually set `expires_at` to past, trigger any Drive API call, confirm new token is stored
- [ ] 9.4 Verify import: add a Google Drive folder as source point, trigger sync, confirm all files in folder appear as materials with embed jobs
- [ ] 9.5 Verify export: export flashcards/quiz/report to Drive, confirm Google Doc is created with correct content and URL is returned
- [ ] 9.6 Verify sticky target: select folder, re-open export UI, confirm folder is pre-selected
