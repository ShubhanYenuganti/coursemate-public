## Context

`MaterialsPage.jsx` renders material cards with an `EmbedStatusBadge` driven by `material.embed_status` from the server. When the user confirms a sync in the modal, `handleSyncConfirm` calls `bulk_upsert_sync` and switches the modal to progress mode — but the local `materials[]` array is left untouched until the polling cycle (`fetchMaterials`) returns updated rows from the backend. The gap between user action and first successful poll leaves cards with an empty or stale badge, which looks broken.

## Goals / Non-Goals

**Goals:**
- Guarantee material cards show `'syncing'` immediately after the user clicks Sync — zero visible gap.
- Keep the change local to `handleSyncConfirm`; no new state variables, no new hooks.

**Non-Goals:**
- Backend changes of any kind.
- Changes to the polling frequency or window logic.
- Handling cases where `embed_status` is already in a terminal state (the user explicitly re-triggered sync, so forcing 'syncing' is correct regardless).

## Decisions

### Decision 1: Optimistic `setMaterials` inside `handleSyncConfirm`

After the `bulk_upsert_sync` POST succeeds (before the modal switches to progress mode), call `setMaterials(prev => prev.map(...))` to patch `embed_status: 'syncing'` on every material whose `external_id` + `source_type` matches a row in the confirmed-sync set.

**Why:** The `materials` array already drives `EmbedStatusBadge`. A single targeted map is O(n) and requires no new state. The polling cycle will overwrite the optimistic value with real server data on the very next tick, so there is no risk of stale state persisting.

**Alternative considered:** Add a separate `forcedSyncingIds` Set state and have `EmbedStatusBadge` check it first. Rejected — unnecessary complexity; patching the source-of-truth array is simpler and self-healing.

### Decision 2: Match by `external_id` + `source_type`

Materials created from integration files carry both fields. This pair is the stable identity used everywhere else in the sync flow (e.g. `pendingSyncRows` filtering) — using it here is consistent.

**Why not match by `id`?** At confirm time the frontend only has the `syncRows` list (provider file rows), not the database material IDs. `external_id` + `source_type` is the reliable cross-reference.

## Risks / Trade-offs

- **Risk: Material not yet in DB at confirm time** (e.g. a newly-toggled-on file that hasn't been ingested yet) → The map simply won't find a match for that row; no harm done. The badge will update correctly once the poller ingests and the material appears.
- **Risk: Optimistic 'syncing' shown briefly for a file that fails to sync** → Mitigation: the polling cycle will update with the real terminal status. The window is short (first poll fires immediately after modal switches to progress mode).

## Migration Plan

Single-file frontend change. No deploy coordination required. Rollback is reverting the `setMaterials` call.
