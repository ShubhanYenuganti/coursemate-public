## Why

The sync and upload workflows in MaterialsPage have no meaningful feedback during the 10–15 second Lambda execution window: the existing `pendingSyncRows` filter closes the progress modal as soon as material records exist in the DB (not when embedding is done), the 5-second poll interval is sluggish, and inline status badges on material cards are easy to miss. Uploads and syncs need a unified, persistent, inline progress surface that is responsive and correct.

## What Changes

- **New**: `ProgressPanel` component renders full-width between the upload section and materials grid; shows sync jobs and upload jobs with per-item status derived from live polling
- **New**: `syncJobs` state replaces `syncPolling` + `pendingSyncRows`; each `handleSyncConfirm` call pushes one job entry with its file list
- **Changed**: Polling interval drops from 5 s to 2 s during any active job; polling stops when all jobs are terminal
- **Fixed**: Progress tracking now closes only when `embed_status === 'done'` for each item (not on material existence)
- **Changed**: `SyncModal` becomes staging-only — the `progress` mode and `pendingRows` prop are removed **BREAKING**
- **Changed**: Upload items (active + completed) move from inline sections inside the upload card into `ProgressPanel`
- **Removed**: `EmbedStatusBadge` removed from `MaterialCard` — status is surfaced in `ProgressPanel` only
- **New**: `ProgressPanel` visibility is localStorage-backed; dismissed panel re-appears automatically on next upload or sync

## Capabilities

### New Capabilities

- `progress-panel`: Full-width inline panel between upload section and materials grid; unified display of sync jobs and upload jobs with per-item live status; localStorage-backed dismiss with auto-reopen on next activity

### Modified Capabilities

<!-- None — all changes are scoped to the new progress-panel capability -->

## Impact

- `src/MaterialsPage.jsx`: state model changes (`syncJobs`, remove `syncPolling`/`pendingSyncRows`/`syncModalMode`), polling `useEffect` rewritten, `SyncModal` props simplified, `EmbedStatusBadge` removed from `MaterialCard`, `ProgressPanel` added between upload section and materials grid
- No backend changes required
- No new dependencies
