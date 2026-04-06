## Why

Users want to export AI-generated study materials (flashcards, quizzes, reports) directly to their Notion workspace without manual copy-paste. A persistent OAuth connection with sticky per-course targeting removes friction from the export loop and creates a foundation for future integrations (e.g., pinning chat messages to Notion, Google Drive sync).

Beyond export, users and collaborators want to feed live Notion databases into CourseMate as course materials — so notes, readings, and resources updated in Notion automatically propagate into the embedding pipeline without manual re-upload. Multiple collaborators can each connect their own Notion source points to a shared course, keeping their material feeds independent.

## What Changes

- Add `user_integrations` table to store OAuth tokens and workspace metadata per user (provider-agnostic)
- Add `integration_source_points` table to store per-user watched Notion databases per course (generalised for future providers)
- Add `course_export_targets` table to store sticky export destinations per (user, course, provider, generation_type)
- Add `material_selections` table to persist per-user material selections per context (chat, quiz, flashcards, report) with FK cascade on material removal
- Extend `materials` table with `external_id` and `external_last_edited` for provider-sourced materials
- New `/api/notion.py` serverless function handles all Notion concerns: OAuth, target search, create-new destination, all export actions, source point management, and manual sync trigger
- New `lambda/integration_poller/` Lambda: polls all active source points across providers every ~2 hours via EventBridge Scheduler; converts Notion pages to PDF via `reportlab` and feeds into existing `embed_materials` Step Function unchanged
- New `api/services/export_blocks.py` (provider-agnostic block builder) with `providers/notion.py` submodule
- ProfilePage gains a "Connected Apps" section with Connect/Revoke per provider; course settings gain a "Source Points" panel for managing watched databases
- Material pickers in ChatTab, Quiz, Flashcards, and Reports default to the user's own materials; collaborator public materials appear in an opt-in pool with hover metadata (name, material title, email)
- Flashcards viewer gains "Export to Notion" action; Quiz and Reports viewers gain "Export to Notion" action

## Capabilities

### New Capabilities

- `notion-oauth`: User connects/disconnects their Notion workspace via OAuth 2.0 public integration; connection status displayed in ProfilePage
- `notion-export-flashcards`: Authenticated users export a ready flashcard generation as rows in a Notion database, with sticky per-course target remembered
- `notion-export-quiz`: Authenticated users export a ready quiz generation as a structured Notion page, with sticky per-course target remembered
- `notion-export-report`: Authenticated users export a ready report generation as a structured Notion page, with sticky per-course target remembered
- `notion-target-picker`: Users search and select a Notion page or database as the export destination, or create a new one; selection is persisted as the sticky default for (course, generation_type)
- `notion-source-points`: Per-user per-course Notion database watchers; new and updated pages are automatically converted to PDF and ingested via the existing embed pipeline; manual sync available
- `material-selection-persistence`: Per-user material selections per context are persisted in DB; own materials default to selected, collaborator public materials default to unselected; selections survive material deletions via FK cascade

### Modified Capabilities

- `ChatTab`, `Quiz`, `Flashcards`, `Reports` material pickers: default selection scoped to own materials; collaborator public materials available in opt-in section with hover tooltip (name / material title / email)

## Impact

- **New DB tables**: `user_integrations`, `integration_source_points`, `course_export_targets`, `material_selections`
- **Modified DB**: `materials` gains `external_id TEXT`, `external_last_edited TEXT`; `source_type` values extended to include `'notion'`, `'google_drive'`
- **New API file**: `api/notion.py` — all Notion backend in one serverless function
- **New Lambda**: `lambda/integration_poller/` — EventBridge-triggered poller with provider-dispatched sync handlers
- **New service**: `api/services/export_blocks.py` with `api/services/providers/notion.py`
- **Modified frontend**: `ProfilePage.jsx` (Connected Apps), `ChatTab.jsx`, `Flashcards.jsx`, `Quiz.jsx`, `Reports.jsx` (material picker + export buttons), course settings (Source Points panel)
- **New env vars**: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI`
- **New AWS resources**: EventBridge Scheduler rule, `integration_poller` Lambda
