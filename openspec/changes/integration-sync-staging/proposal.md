## Why

The integration poller currently ingests every file it detects under a connected source point with no user intervention — users who connect a large Google Drive folder or Notion database have no way to exclude files they don't want embedded. This change introduces an explicit opt-out staging step so users control exactly which files enter the embed pipeline before any processing begins.

## What Changes

- A standalone **Sync Modal** in `MaterialsPage` populates all files from a newly selected source point with per-file sync toggles (default ON); no DB writes until the user clicks Sync.
- During sync workflows, `MaterialsPage` SHALL hide the Upload Modal and replace it with the Sync Modal; the Upload Modal returns only after sync handoff is complete for all selected files.
- A `sync` boolean column is added to the `materials` table (`NOT NULL DEFAULT true`) — `false` means explicitly excluded, row is retained but skipped by the poller.
- The integration poller checks each detected file's `sync` field before any PDF conversion work; `false` → skip, `true` or missing row → proceed (insert with `sync = true` for new files).
- **BREAKING** Delete behavior diverges by file type: normal materials delete the row + S3 object; synced (integration-linked) files retain the row with `sync = false` and remove only the S3 object, preventing re-ingestion on the next poll cycle.
- "Sync Now" in `MaterialsPage` on a connected source point opens the Sync Modal pre-populated with current toggle state: `sync = false` rows appear OFF, new/missing rows appear ON; Sync applies diffs.
- API strategy for this change: keep provider-specific source-point list endpoints (`gdrive`/`notion`) and normalize them into a shared Sync Modal data model in frontend.
- After the user clicks Sync, the Sync Modal remains visible (Upload Modal still hidden) and its pending-files dropdown shrinks as files pass poller staging and transition into embed processing; when all selected files complete the poller handoff, the Sync Modal closes and Upload Modal is restored.

## Capabilities

### New Capabilities
- `integration-staging-modal`: Per-file toggle UI in MaterialsPage for staging source point files before ingestion; covers initial selection and Sync Now re-staging flows.
- `synced-file-deletion`: Conditional delete handler that retains the materials row with `sync = false` when the material has a third-party integration foreign key, versus full row + S3 deletion for normal materials.
- `notion-import`: Notion poller ingestion behavior with sync gate — pages with `sync = false` are skipped before block fetching and PDF generation; new pages auto-inserted with `sync = true`.

### Modified Capabilities
- `gdrive-import`: Poller must now consult the `sync` field on each detected file before handing off to the embed pipeline; new files auto-inserted with `sync = true`.

## Impact

- `src/MaterialsPage.jsx` — standalone sync modal, toggle state, sync lifecycle state machine (replace/hide upload modal during sync), conditional delete handler
- `src/CoursePage.jsx` — adjust/remove existing source-panel "Sync Now" triggers so sync entry point is `MaterialsPage`
- `lambda/integration_poller/handlers/gdrive.py` — sync field lookup + skip logic before Drive export/download
- `lambda/integration_poller/handlers/notion.py` — sync field lookup + skip logic before block fetch and PDF generation
- `materials` table — migration: `ALTER TABLE materials ADD COLUMN sync BOOLEAN NOT NULL DEFAULT true`
- API layer (`api/material.py` + integration source-point file listing endpoints) — support sync toggle upsert + paginated source-point file listing for Sync Modal
- No changes expected to `lambda/embed_materials/`
