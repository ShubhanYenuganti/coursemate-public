## Context

CourseMate already ships a complete Notion OAuth integration: token storage in `user_integrations` (encrypted), source points in `integration_source_points`, export targets in `course_export_targets`, and a Lambda-based polling pipeline. All three tables use a `provider` varchar column, making them inherently multi-provider. The goal is to add Google Drive as a second provider using the same infrastructure with minimal new code surface.

Google OAuth 2.0 differs from Notion's in one critical way: it issues **refresh tokens** in addition to short-lived access tokens (1-hour TTL). Notion tokens are long-lived and never expire. This changes how tokens must be stored and used.

## Goals / Non-Goals

**Goals:**
- OAuth 2.0 connection flow (initiate, callback, finalize, status, revoke) identical in UX to the Notion flow
- Import: Drive files/folders added as source points; Lambda poller fetches file content, converts to PDF, ingests as materials
- Export: Flashcards/quizzes/reports exported as Google Docs to a user-selected Drive folder
- Sticky export target per user/course/generation type via existing `course_export_targets` table
- Profile page connection UI matching the Notion section

**Non-Goals:**
- Real-time Drive change webhooks / push notifications (polling only, same as Notion)
- Shared Drive / Team Drive support (personal Drive only in v1)
- Bi-directional sync (import-only for Drive content; export is write-once)
- Supporting file types other than Docs/Sheets/PDFs/PPTX for import in v1

## Decisions

### 1. Reuse existing multi-provider schema as-is

**Decision:** No new tables. Use `provider = "gdrive"` in `user_integrations`, `integration_source_points`, and `course_export_targets`.

**Rationale:** The schema was designed for this. Adding Google Drive is a data-level addition, not a schema change. Avoids migration complexity entirely.

**Alternative considered:** Separate `gdrive_tokens` table — rejected because it would duplicate schema without benefit and break the single-provider-lookup pattern used throughout the codebase.

### 2. Store both access_token and refresh_token encrypted in `encrypted_token`

**Decision:** Serialize `{"access_token": ..., "refresh_token": ..., "expires_at": <unix_ts>}` as JSON, then encrypt the whole string before storing in `encrypted_token`.

**Rationale:** Notion stores a single opaque token string. For Google, we need refresh capability. Storing as encrypted JSON in the same column avoids adding new columns and keeps the storage layer identical.

**Alternative considered:** Add `encrypted_refresh_token` column — rejected to avoid a migration and maintain schema parity.

### 3. Auto-refresh tokens in the API handler before every Drive API call

**Decision:** In `api/gdrive.py`, add a `get_valid_token(user_id)` helper that decrypts the stored JSON, checks `expires_at`, and calls the Google token refresh endpoint if the token is within 5 minutes of expiry, then re-encrypts and stores the fresh token.

**Rationale:** Centralizes refresh logic; callers never see an expired token. Keeps route handlers clean.

### 4. New `api/gdrive.py` file (not appended to an existing API file)

**Decision:** Mirror `api/notion.py` as a standalone `api/gdrive.py` Vercel serverless function.

**Rationale:** Notion's handler is ~1450 lines. Merging Drive into it would create an unmanageable file. Separate file keeps provider logic isolated and independently deployable.

### 5. SameSite cookie workaround — same approach as Notion

**Decision:** Reuse the pending-token cookie + `/profile?gdrive_pending=1` finalize pattern.

**Rationale:** Google OAuth redirects from accounts.google.com also trigger SameSite=Lax restrictions on session cookies. The Notion solution already proves this pattern works.

### 6. Import format: export Drive files as PDF via Drive export API

**Decision:** For Google Docs/Sheets/Slides, use the Drive `files.export` API (`mimeType=application/pdf`) to get a PDF. For native PDFs and other binary files, use `files.get?alt=media`. Upload PDF to S3 and feed into the existing embed pipeline.

**Rationale:** Reuses the exact same Lambda pipeline that Notion uses (PDF → S3 → materials record → embed job). No new ingestion logic needed.

**Alternative considered:** Parse Google Docs content via the Docs API — rejected for v1 due to complexity; PDF export is simpler and produces identical input to what the embed pipeline already handles.

### 7. Export format: create Google Docs via Google Docs API

**Decision:** For export, use the Google Docs API to create a new Doc in the target folder, then append formatted content using `batchUpdate`. Provide a `gdrive.py` service module with `flashcard_to_doc_requests()`, `quiz_to_doc_requests()`, `report_to_doc_requests()` helpers.

**Rationale:** Mirrors `api/services/providers/notion.py` in structure. Google Docs API's `batchUpdate` request format (insertText, createParagraphBullets, etc.) maps cleanly to the existing block structure.

## Risks / Trade-offs

- **Google OAuth token expiry** → Mitigation: `get_valid_token()` auto-refresh; if refresh fails (token revoked), return 401 to frontend prompting reconnect.
- **Drive API quota limits (reads: 1000 req/100s per user)** → Mitigation: Lambda poller already uses per-source-point polling intervals; no burst risk in normal usage.
- **Large file downloads in Lambda** → Mitigation: Streaming PDF export to S3 in chunks (same as Notion PDF generation). Lambda memory limit is 256 MB; files larger than ~100 MB may fail. Cap importable file size at 50 MB (consistent with existing material upload limit).
- **Google OAuth consent screen requires domain verification for sensitive scopes** → Mitigation: `drive.file` scope (export only) is non-sensitive. `drive.readonly` is sensitive and requires Google verification before production launch. Use `drive.readonly` in development; document production verification requirement in env setup guide.

## Migration Plan

1. **No DB migration required** — schema already supports multi-provider.
2. Deploy `api/gdrive.py` behind Vercel. Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` to Vercel environment.
3. Deploy updated Lambda `integration_poller` with `handlers/gdrive.py`.
4. Deploy updated frontend with Profile page Google Drive section and `GDriveTargetPicker`.
5. **Rollback:** Remove env vars and delete `api/gdrive.py` from Vercel deployment. No data cleanup needed for existing users (none will have connected yet).

## Open Questions

- Should Google Drive import support folder-level source points (ingest all PDFs in a folder) or file-level only? Notion is database-level. **Recommend:** file-level for v1, folder-level as a follow-up.
- What Google OAuth app verification tier to target? `drive.readonly` requires verification. **Action needed:** Submit for verification before public launch or use restricted testing mode during development.
