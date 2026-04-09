## Why

Users store course-relevant content (lecture slides, PDFs, notes) in Google Drive, but CourseMate currently has no way to ingest it directly. Adding a Google Drive OAuth integration — modeled on the existing Notion integration — lets users grant CourseMate read access to their Drive files so they can be imported as course materials, and write access so generated study content can be exported back to Drive.

## What Changes

- New Google Drive OAuth connection flow (initiate, callback, finalize, revoke) in a new `/api/gdrive.py` serverless function
- User can connect/disconnect Google Drive from their Profile page, identical UX to the Notion connection section
- Drive **folders** selected as course source points are polled by the integration Lambda; all files within the folder are converted to PDF and ingested as materials (same pipeline as Notion)
- Generated content (flashcards, quizzes, reports) can be exported as Google Docs to a user-selected Drive **folder**
- Sticky export target saved per user/course/generation type (reuses `course_export_targets` table with `provider = "gdrive"`)
- Source points stored in `integration_source_points` with `provider = "gdrive"`
- OAuth tokens stored in `user_integrations` with `provider = "gdrive"` (encrypted)

## Capabilities

### New Capabilities

- `gdrive-oauth`: OAuth 2.0 connection flow for Google Drive — initiate, callback, finalize, status, revoke endpoints; token encryption/storage in `user_integrations`
- `gdrive-import`: Add Drive **folders** as course source points; Lambda poller lists all files in each folder, fetches and converts them to PDF materials (same pipeline as Notion)
- `gdrive-export`: Export flashcards/quizzes/reports to Google Drive as Google Docs; sticky target picker for Drive **folders** only

### Modified Capabilities

- *(none — no existing spec-level requirements change)*

## Impact

- **New file**: `api/gdrive.py` (mirrors structure of `api/notion.py`)
- **New Lambda handler**: `lambda/integration_poller/handlers/gdrive.py` (mirrors `handlers/notion.py`)
- **New service module**: `api/services/providers/gdrive.py` (block formatters for Google Docs export)
- **Frontend**: New `GDriveConnectionSection` on `ProfilePage.jsx`; new `GDriveTargetPicker.jsx` component
- **Database**: No new tables; existing `user_integrations`, `course_export_targets`, `integration_source_points` tables already support multi-provider via the `provider` column
- **Migrations**: None required — schema is already multi-provider
- **Env vars**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` added to `.env` and Lambda config
- **Google OAuth scopes needed**: `https://www.googleapis.com/auth/drive.readonly` (import) + `https://www.googleapis.com/auth/drive.file` (export)
