## 1. Project Overview Section

- [x] 1.1 Write 2–3 paragraph overview: what the app is, primary use case (AI-assisted study from course materials), tech stack (Python/React, PostgreSQL, AWS Lambda, EventBridge)

## 2. Integrations — OAuth Connection

- [x] 2.1 Write Notion OAuth subsection: connection initiated from Profile, state-cookie CSRF guard, token storage in `user_integrations`, workspace metadata display, disconnection (also deletes `notion_course_targets`)
- [x] 2.2 Write Google Drive OAuth subsection: same shape as Notion, plus SameSite cookie finalize path (pending cookie → `/profile?gdrive_pending=1` → finalize call), auto-refresh on tokens expiring within 5 minutes

## 3. Integrations — Sync Staging Modal

- [x] 3.1 Describe the first-connect flow: source point selected → modal lists all files with toggles default ON → user may toggle off → Sync writes rows (`sync=true/false`, `doc_type`)
- [x] 3.2 Describe the Sync Now flow: modal pre-populated from stored sync state, new files appear with toggle ON, confirm updates existing rows and inserts new ones

## 4. Integrations — Async Lambda Poller (EventBridge)

- [x] 4.1 Write ASCII diagram showing the two invocation paths: EventBridge sweep (work list from `materials WHERE sync=TRUE`) vs Sync Now (explicit `external_ids` in Lambda event)
- [x] 4.2 Explain `_needs_ingest` staleness check: True when `api_time > db_time`, `db_time` is NULL, or parse error; False only when `api_time ≤ db_time`; include decision table or diagram
- [x] 4.3 Describe Notion ingestion pipeline: `pages API last_edited_time` → blocks fetch → ReportLab PDF → S3 → materials row → embed job
- [x] 4.4 Describe GDrive ingestion pipeline: `Drive modifiedTime` → export as PDF (Docs/Sheets/Slides) or direct download (native PDF) → S3 → materials row → embed job; note 50 MB size guard
- [x] 4.5 Note the `up_to_date` status: written to `material_embed_jobs` only on Sync Now runs when file is unchanged, NOT on background sweeps

## 5. Integrations — Progress Panel

- [x] 5.1 Describe status lifecycle: Syncing → Queued → Indexing → Done (derived from `embed_status`, polled every 2 s during active jobs)
- [x] 5.2 Note dismissible behaviour (localStorage) and auto-reopen when new activity starts

## 6. Integrations — Exporting Generated Content

- [x] 6.1 Write export section with a table covering all three content types (flashcards, quizzes, reports) for both providers (Notion, Google Drive)
- [x] 6.2 Document Notion block mappings: reports → `heading_2`/`paragraph`; quizzes → `heading_2`/`bulleted_list_item`/`toggle` answer; flashcards → `toggle` (front = heading, back = expanded content)
- [x] 6.3 Document GDrive exports: creates a Google Doc per export in the selected folder
- [x] 6.4 Explain sticky export targets (remembered per user × course × generation type) and the target-type guard (report/quiz/flashcard exports require a Notion Page, not a Database — warning icon shown if wrong type)
- [x] 6.5 Explain batch API: `exports` array envelope, 207 Multi-Status response shape, partial-failure semantics (successful entries not rolled back by failures in other entries)

## 7. Chat — Search

- [x] 7.1 Explain the two modes: empty query (in-memory, sorted by `last_message_at DESC`, no network request) and non-empty query (debounced 300 ms, hits `GET /api/chat?resource=chat_search`)
- [x] 7.2 Explain FTS ranking: title matches get ≥ 3× ts_rank boost with prefix matching on the last token; a chat in title matches does NOT appear in content matches
- [x] 7.3 Explain log-damped content scoring: `(1 + ln(hit_count)) × best_message_rank` — include the formula and a plain-language note on why log-damping exists (prevents high hit-count chats from outranking high-relevance ones)
- [x] 7.4 Describe UI: modal triggered by sidebar search icon, TITLE MATCHES / IN CONVERSATION section headers, ESC/backdrop dismissal, click-to-navigate, results capped at 20 per section, archived chats excluded

## 8. Chat — Pinned Responses

- [x] 8.1 Describe the pin icon (replaces thumbs up/down on AI messages), toggle behaviour, and visual active/inactive states
- [x] 8.2 Explain DB-persisted storage: `pinned_messages` table, ownership enforcement (server verifies message belongs to authenticated user)
- [x] 8.3 Explain LLM-generated summaries: model returns `summary` field alongside every reply, stored in `chat_messages.summary`, surfaced as PinsPanel row preview (server-side, not client-derived truncation)
- [x] 8.4 Describe PinsPanel: expandable rows (user + AI bubbles), trash-icon deletion, pin state reflects deletion immediately in the chat log
- [x] 8.5 Note pin state preservation through message revert/restore operations

## 9. Materials Management

- [x] 9.1 Briefly describe `doc_type` per material: selected in Sync Modal, stored on the materials row, returned in `list_source_point_files`
- [x] 9.2 Note synced file deletion behaviour (tombstoning — previously ingested materials are not automatically deleted when a source point is removed)
- [x] 9.3 Note duplicate invite rejection guard (already-a-member check on course invite)
