## 1. CoursePage — localStorage persistence

- [x] 1.1 Add a helper to read initial progress state from `localStorage` under `coursemate_progress_${courseId}`, returning `{ syncJobs: [], uploadItems: [], panelDismissed: false }` as fallback
- [x] 1.2 In the helper, scrub any `uploadItems` with `status === "uploading"` or `status === "confirming"` to `status: "error"` before returning
- [x] 1.3 Replace the hardcoded `useState([])` / `useState(false)` initializers for `syncJobs`, `uploadItems`, and `panelDismissed` with lazy initializers that call the helper (note: `courseId` is not available at component declaration time — use a `useEffect` to load on first mount instead)
- [x] 1.4 Add a `useEffect` that watches `[syncJobs, uploadItems, panelDismissed, courseId]` and writes the current values to `localStorage["coursemate_progress_${courseId}"]` whenever any change (skip write if `courseId` is falsy)
- [x] 1.5 Confirm that switching courses (different `courseId`) loads the correct course's progress state and does not bleed between courses

## 2. MaterialsPage — embed_status grid filter

- [x] 2.1 In the `visibleMaterials` filter (around line 1830), add a terminal-status check: only include materials where `m.embed_status` is `"done"`, `"failed"`, or `"skipped"` (exclude `"pending"`, `"processing"`, `null`, or any other non-terminal value)
- [x] 2.2 Verify the existing `prevHadActiveJobs` effect still fires `fetchMaterials()` when jobs complete, causing newly-done materials to appear in the grid without additional changes

## 3. Verification

- [ ] 3.1 Start an upload, wait for it to reach "indexing" state — confirm material does NOT appear in grid, only in ProgressPanel
- [ ] 3.2 Wait for embedding to complete — confirm material appears in grid
- [ ] 3.3 Start an upload, then refresh mid-indexing — confirm ProgressPanel reappears showing the item (status from polling catches up)
- [ ] 3.4 Start an upload, refresh while still in "uploading" state — confirm item reappears as "error" in ProgressPanel
- [ ] 3.5 Dismiss the panel, refresh — confirm panel stays dismissed
- [ ] 3.6 Complete some uploads, refresh — confirm done items reappear in ProgressPanel
- [ ] 3.7 Trigger a sync, switch tabs, return — confirm sync jobs still show in ProgressPanel and mid-indexing materials are absent from grid
