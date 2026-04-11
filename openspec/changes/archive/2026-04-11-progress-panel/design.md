## Context

`MaterialsPage` currently manages two parallel progress surfaces: inline upload rows (active/completed sections inside the upload card) and a sync modal that switches between staging and progress modes. The progress mode has a correctness bug — `pendingSyncRows` clears as soon as material records exist in the DB, not when embedding is done. Polling fires every 5 s via a 90-second `syncPolling` window, which gives no feedback during the Lambda's 10–15 s execution. There is no shared surface between uploads and sync jobs, and `EmbedStatusBadge` on material cards is easy to scroll past and miss.

## Goals / Non-Goals

**Goals:**
- Single inline `ProgressPanel` between upload section and materials grid showing all active and recently completed jobs
- Correct terminal condition: an item is done when `embed_status === 'done'`
- 2 s polling while any job is active; poll stops when all jobs are terminal
- SyncModal reduced to staging-only (no `progress` mode)
- `EmbedStatusBadge` removed from `MaterialCard`
- Panel dismiss via localStorage; auto-reopens on next upload or sync

**Non-Goals:**
- Server-sent events or WebSocket push
- Backend schema changes
- Per-file upload progress percentage (byte-level streaming)
- Multi-course or cross-page panel persistence

## Decisions

### 1. Replace `syncPolling` + `pendingSyncRows` with `syncJobs`

**Decision**: Introduce a `syncJobs` array where each entry represents one `handleSyncConfirm` call.

```js
// shape of one sync job
{
  jobId: uid(),           // local only
  label: string,          // source point title
  provider: 'gdrive' | 'notion',
  items: [
    { external_id: string, name: string }
    // status derived on each render from materials[]
  ]
}
```

Status for each item is derived — not stored — by looking up `materials.find(m => m.external_id === item.external_id)?.embed_status` on every render cycle. This avoids a separate status sync step and keeps the derived state minimal.

**Why over alternatives**:
- Keeping `pendingSyncRows` would require fixing its filter bug AND adding phase tracking; a clean replacement is simpler
- Storing per-item status in state risks divergence from the polled materials array

### 2. Upload items stay in `uploadItems` state; ProgressPanel reads from it directly

**Decision**: `uploadItems` state shape is unchanged. `ProgressPanel` receives it as a prop and renders upload rows. The inline active/completed upload sections inside the upload card are removed.

**Why**: Avoids duplicating upload state. The panel is purely presentational for uploads — it reads the same array that already drives the upload logic.

### 3. Polling rewrite: item-aware, 2 s interval

**Decision**: Replace the 90-second `syncPolling` window with a computed `hasActiveJobs` flag:

```js
const hasActiveJobs =
  syncJobs.some(job =>
    job.items.some(item => {
      const m = materials.find(m => m.external_id === item.external_id);
      return !m || m.embed_status !== 'done';
    })
  ) || uploadItems.some(i => i.status === 'uploading' || i.status === 'confirming');

// polling effect
useEffect(() => {
  if (!hasActiveJobs) return;
  const timer = setTimeout(fetchMaterials, 2000);
  return () => clearTimeout(timer);
}, [materials, hasActiveJobs, fetchMaterials]);
```

Polling continues only while items are non-terminal. No arbitrary timeout window needed.

### 4. SyncModal becomes staging-only

**Decision**: Remove `mode`, `pendingRows`, and all progress-mode rendering from `SyncModal`. On confirm, the modal closes and `handleSyncConfirm` pushes a new entry into `syncJobs`.

**Why**: The progress mode was always conceptually separate from file selection. Unifying them in one modal caused the confusing state machine. Splitting them makes each component single-purpose.

### 5. ProgressPanel placement and visibility

**Decision**: Panel renders between the upload card and materials grid. It is conditionally rendered when `syncJobs.length > 0 || uploadItems.length > 0`. Visibility is governed by a `panelDismissed` state that is read from/written to `localStorage` under the key `coursemate_progress_dismissed`.

Lifecycle:
- New job or upload added → `setPanelDismissed(false)` → panel appears
- User clicks "Clear done" → completed items removed from state; if no active items remain, `setPanelDismissed(true)` and write to localStorage
- On mount, if `syncJobs.length > 0 || uploadItems.length > 0`, ignore localStorage and show panel

### 6. EmbedStatusBadge removal from MaterialCard

**Decision**: Remove `<EmbedStatusBadge>` from `MaterialCard`. `SourceTypeBadge` is kept (it's identity metadata, not status). The `EmbedStatusBadge` component itself can be kept as a utility and reused inside `ProgressPanel` rows.

**Why**: Badge on card served as the only status signal before; now `ProgressPanel` covers that role with better visibility. Removing it from cards reduces noise on the grid.

## Risks / Trade-offs

- **Panel blindness when navigating away**: If the user navigates to another route (e.g. Chat) and back, `syncJobs` is ephemeral React state and resets. Active syncs will still complete in the backend, and the next `fetchMaterials()` on mount will reflect final status — but the user loses the per-file progress view.
  → Acceptable for now; full persistence would require either URL state or a context store.

- **Polling at 2 s while jobs are active**: More frequent than before but still lightweight (one GET /api/material call). If a course has hundreds of materials the payload grows, but this is the same call made today.
  → Mitigated by the fact that polling stops immediately when all jobs are terminal.

- **No upload byte-progress**: `uploadItems` tracks `status` only (uploading/confirming/done/error), not a 0–100% progress value. The panel will show a spinner during upload rather than a progress bar.
  → Acceptable; implementing XHR progress tracking is a separate concern.

## Migration Plan

1. All changes are frontend-only in `src/MaterialsPage.jsx`
2. No DB migrations, no API changes
3. Rollback: revert the single file; no persistent state to clean up (localStorage key is additive)

## Open Questions

- Should completed sync jobs auto-dismiss after a delay (e.g. 5 s after all items done), or stay until the user explicitly clears them? Current design requires explicit clear.
