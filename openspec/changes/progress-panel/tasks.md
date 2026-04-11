## 1. State Model Refactor

- [x] 1.1 Add `syncJobs` state (`useState([])`) to `MaterialsPage`; remove `syncPolling`, `syncPollingTimeoutRef`, `pendingSyncRows`, and `beginSyncPollingWindow`
- [x] 1.2 Add `panelDismissed` state initialized from `localStorage.getItem('coursemate_progress_dismissed') === 'true'`
- [x] 1.3 Remove `syncModalMode` state and all references to `'progress'` mode throughout the component

## 2. Polling Rewrite

- [x] 2.1 Replace the existing `syncPolling`-based `useEffect` poll with a new effect that computes `hasActiveJobs`: true if any sync job item has no matching material or `embed_status !== 'done'`, OR any upload item is `uploading`/`confirming`
- [x] 2.2 Set polling interval to 2000 ms (down from 5000 ms) in the new effect
- [x] 2.3 Remove the 90-second timeout ref (`syncPollingTimeoutRef`) and its cleanup `useEffect`

## 3. handleSyncConfirm Refactor

- [x] 3.1 After a successful `bulk_upsert_sync` API call, push a new entry into `syncJobs` with `jobId`, `label` (source point title), `provider`, and `items` (array of `{ external_id, name }` for files where `sync === true`)
- [x] 3.2 Call `setPanelDismissed(false)` and `localStorage.removeItem('coursemate_progress_dismissed')` when adding a new sync job
- [x] 3.3 Remove `setSyncModalMode('progress')`, `setPendingSyncRows(...)`, and `beginSyncPollingWindow()` calls from `handleSyncConfirm`
- [x] 3.4 Close `SyncModal` immediately on confirm success (`setSyncModalOpen(false)`)

## 4. Upload Items → ProgressPanel

- [x] 4.1 In `handleStagingUpload`, call `setPanelDismissed(false)` and `localStorage.removeItem('coursemate_progress_dismissed')` when adding a new upload item
- [x] 4.2 Remove the inline "Uploading" and "Just uploaded" / "Completed" sections from the upload card JSX (the `activeUploads` and `completedUploads` rendered blocks)

## 5. SyncModal Simplification

- [x] 5.1 Remove the `mode` prop and all `mode === 'progress'` conditional branches from `SyncModal`
- [x] 5.2 Remove the `pendingRows` prop and its associated progress list rendering from `SyncModal`
- [x] 5.3 Update `SyncModal` call site in `MaterialsPage` JSX: remove `mode`, `pendingRows` props
- [x] 5.4 Remove the two `useEffect`s that watch `syncModalMode` and `pendingSyncRows` for modal auto-close logic

## 6. ProgressPanel Component

- [x] 6.1 Create `ProgressPanel` function component accepting props: `syncJobs`, `uploadItems`, `materials`, `onClearDone`, `onVisibilityChange`
- [x] 6.2 For sync sections: group items by job; derive each item's display status by looking up `materials.find(m => m.external_id === item.external_id)?.embed_status`; map to label: no match → "Syncing…", `pending` → "Queued", `processing` → "Indexing…", `done` → "Done", `failed` → "Failed", `skipped` → "Skipped"
- [x] 6.3 For upload section: render rows for all `uploadItems`; map `status` to label: `uploading`/`confirming` → spinner + label, `done` → "Done", `error` → "Failed"
- [x] 6.4 Render "Clear done" button in panel header; on click call `onClearDone()`
- [x] 6.5 Style panel as `bg-white rounded-xl border border-gray-200 shadow-sm` consistent with other MaterialsPage cards; use indigo/gray Tailwind palette for status indicators

## 7. Wire ProgressPanel into MaterialsPage

- [x] 7.1 Implement `handleClearDone` callback: filter `syncJobs` to remove jobs where all items are terminal; filter `uploadItems` to remove terminal items; if no active items remain, set `panelDismissed(true)` and write to `localStorage`
- [x] 7.2 Add `ProgressPanel` to the JSX between the upload card and the materials grid, rendered conditionally: `(syncJobs.length > 0 || uploadItems.length > 0) && !panelDismissed`
- [x] 7.3 Revert the upload section from `{syncModalOpen ? <SyncModal/> : <UploadSection/>}` toggle to always-visible `<UploadSection/>` alongside `<SyncModal/>` (modal is an overlay, not a replacement)

## 8. MaterialCard Cleanup

- [x] 8.1 Remove `<EmbedStatusBadge>` from `MaterialCard` render output
- [x] 8.2 Keep `EmbedStatusBadge` component definition (reused inside `ProgressPanel` if desired) or inline equivalent status labels in `ProgressPanel` directly

## 9. Verification

- [ ] 9.1 Trigger a GDrive sync: confirm SyncModal closes immediately, ProgressPanel appears with all synced files showing "Syncing…", items update to "Queued" → "Indexing…" → "Done" as polling progresses
- [x] 9.2 Upload a file via staging queue: confirm file appears in ProgressPanel (not inline in upload card), shows upload progress, then "Done"
- [ ] 9.3 Confirm "Clear done" removes completed items and hides panel when no active items remain; confirm panel reappears on next upload
- [x] 9.4 Confirm polling stops after all items are terminal (no further network calls to `/api/material`)
- [x] 9.5 Confirm material cards no longer show any embed status badge
