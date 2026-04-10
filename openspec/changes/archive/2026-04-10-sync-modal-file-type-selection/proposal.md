## Why

When instructors sync files from Google Drive or Notion into a course, the backend hard-codes `doc_type = 'general'` for every ingested material, losing the context needed for accurate retrieval and display. The upload modal already supports per-file document type selection; the sync modal should offer the same control so integration-sourced materials are classified correctly from the first ingest.

## What Changes

- Each row in the sync modal gains a `doc_type` dropdown (same `DOCUMENT_TYPES` list used in the upload staging area)
- When a file has already been synced (`sync = true`), the modal pre-fills the dropdown with the last stored `doc_type` from the materials table
- The `list_source_point_files` query in both `gdrive.py` and `notion.py` is extended to return `doc_type` alongside `sync`
- The `_bulk_upsert_sync` handler is extended to accept and persist a per-file `doc_type` field
- The frontend `syncDocTypes` state map tracks per-file selections; `handleSyncConfirm` includes `doc_type` in each file object of the payload

## Capabilities

### New Capabilities

- `sync-modal-doc-type`: Per-file document type selection in the integration sync modal, with pre-fill from persisted `doc_type` on re-open

### Modified Capabilities

- `gdrive-import`: The `list_source_point_files` response now includes `doc_type`; `bulk_upsert_sync` now accepts and stores `doc_type` per file

## Impact

- **Frontend**: `SyncModal` component, `normalizeSyncRows`, `handleSyncConfirm`, new `syncDocTypes` state in `MaterialsPage.jsx`
- **Backend**: `_handle_list_source_point_files` in `gdrive.py` and its Notion equivalent in `notion.py`; `_bulk_upsert_sync` in `material.py`
- **Database**: No schema change — `doc_type` column already exists on `materials`
