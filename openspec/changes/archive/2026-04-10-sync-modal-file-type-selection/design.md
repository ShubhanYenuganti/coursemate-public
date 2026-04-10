## Context

The sync modal in `MaterialsPage.jsx` lets instructors select which Drive/Notion files to ingest into a course. The upload modal already includes a per-file `doc_type` dropdown (using `DOCUMENT_TYPES` and `StagingItemRow`), but the sync modal has no equivalent — every synced file lands in the database with `doc_type = 'general'`.

The `materials` table already has a `doc_type` column. The gap is entirely in the UI (no selector) and in the two API layers that need to round-trip the value: `list_source_point_files` (read) and `bulk_upsert_sync` (write).

The Notion equivalent paths mirror GDrive exactly in terms of architecture.

## Goals / Non-Goals

**Goals:**
- Add a `doc_type` dropdown to each row in the sync modal's staging view
- Pre-fill that dropdown from the stored `doc_type` when the file has previously been synced (`sync = true`)
- Persist the selected `doc_type` through `bulk_upsert_sync` so the poller and retrieval system can use it
- Keep the implementation symmetric between GDrive and Notion

**Non-Goals:**
- Bulk-setting doc type for all rows at once (each file is independent)
- Allowing doc type changes after sync (out of scope for this change)
- Modifying the poller Lambdas (they already receive `doc_type` from the materials table)

## Decisions

### 1. State model: parallel `syncDocTypes` map alongside `syncToggles`

A separate `syncDocTypes: Record<externalId, string>` state mirrors the existing `syncToggles` pattern. The alternative (embedding `docType` inside each `syncRows` object) would require mutating immutable row data and would make the default-from-server harder to override per interaction.

**Why separate state**: `syncToggles` is already a pure override layer on top of `row.sync`. `syncDocTypes` follows the same pattern as a pure override layer on top of `row.doc_type`.

### 2. Pre-fill: backend returns `doc_type` in `list_source_point_files`

The `list_source_point_files` query is already cross-referencing `materials` for `sync` state. Extending the same query to also fetch `doc_type` requires a one-line SQL change. `normalizeSyncRows` then includes the field and the frontend initialises `syncDocTypes` from it on open.

**Why not local storage**: `doc_type` is course + file specific and already exists server-side. Local storage would be stale on multi-device usage and duplicate state.

### 3. Backend: `doc_type` is per-file in the `files` array, not a top-level field

Each file object in the `bulk_upsert_sync` payload gains an optional `doc_type` field. If omitted, the backend falls back to `'general'` (existing default). This is backward-compatible — no breaking change.

**Alternative considered**: single top-level `doc_type` for all files. Rejected because files in the same source point often have different types (lecture slides vs readings).

### 4. Dropdown: reuse `DOCUMENT_TYPES` constant verbatim

The same array drives both the upload staging row and the sync row. No new constants needed.

## Risks / Trade-offs

- **Race: user changes toggle but not doc type** → Acceptable. Defaulting to `'general'` is the same behavior as today. The dropdown makes intent explicit without blocking the existing toggle flow.
- **Notion `list_source_point_files` parity** → The Notion handler in `notion.py` must mirror the GDrive SQL change. Omitting it would cause pre-fill to silently fail for Notion source points.
- **Pagination resets doc type state** → When the user navigates to a new page, `syncDocTypes` is reset alongside `syncToggles` (both are page-scoped). This is consistent with the current toggle behavior.

## Migration Plan

1. Deploy backend changes to `gdrive.py`, `notion.py`, and `material.py` — fully backward-compatible (new fields are additive)
2. Deploy frontend — uses new `doc_type` field if present, gracefully ignores if absent
3. No database migration needed
