## Why

The progress panel (tracking uploads and sync jobs) survives tab switches but is lost on page refresh because its state lives only in `CoursePage` memory. Additionally, materials that are mid-indexing appear immediately in the materials grid after an upload or sync confirms, even though they aren't usable yet — the ProgressPanel and grid have overlapping responsibilities for in-flight items.

## What Changes

- `CoursePage` persists `syncJobs`, `uploadItems`, and `panelDismissed` to `localStorage` keyed by `coursemate_progress_${courseId}`, writing on every change and reading on mount
- On restore from localStorage, any `uploadItems` with status `"uploading"` or `"confirming"` are converted to `"error"` (their HTTP requests died with the page); all other items restore as-is, including done items
- `visibleMaterials` in `MaterialsPage` gains a terminal-status filter: only materials with `embed_status` of `"done"`, `"failed"`, or `"skipped"` appear in the grid — mid-indexing materials are excluded until embedding completes

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none — this is a pure behavioral fix with no spec-level requirement changes -->

## Impact

- **`src/CoursePage.jsx`** — adds `useEffect` to read/write progress state from/to localStorage on courseId-scoped key; initializes state from localStorage with upload status scrubbing
- **`src/MaterialsPage.jsx`** — adds `embed_status` terminal-status check to `visibleMaterials` filter
