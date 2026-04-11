## Why

When the user clicks "Sync" in the sync modal, there is a window between the `bulk_upsert_sync` API call completing and the first polling cycle returning updated `embed_status` values from the backend. During this window, material cards show an empty or stale badge instead of "Syncing", creating a jarring visual discontinuity.

## What Changes

- After `handleSyncConfirm` successfully posts `bulk_upsert_sync`, immediately optimistically force the `embed_status` of all confirmed-sync materials to `'syncing'` in local React state before the polling window begins.
- Cards consistently transition: empty/stale → **Syncing** → (polling-driven updates) rather than empty/stale → empty → Syncing.

## Capabilities

### New Capabilities
- `sync-badge-optimistic-update`: Optimistically set `embed_status: 'syncing'` on material cards immediately after sync confirmation, guaranteeing the badge is never empty between user action and first poll.

### Modified Capabilities
<!-- None — this is a purely local state mutation with no spec-level requirement changes. -->

## Impact

- `src/MaterialsPage.jsx`: `handleSyncConfirm` callback — one additional `setMaterials` call after the successful API response, matching confirmed files by `external_id` + `source_type`.
- No backend changes. No API contract changes. No new state variables needed.
