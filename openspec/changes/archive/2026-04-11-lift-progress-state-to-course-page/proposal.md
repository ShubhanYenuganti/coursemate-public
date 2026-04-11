## Why

When a user switches tabs in `CoursePage` (e.g., from Materials to Chat and back), `MaterialsPage` unmounts and remounts, resetting `syncJobs` and `uploadItems` to empty arrays. This causes the `ProgressPanel` to disappear mid-upload or mid-sync even though work is still in progress on the backend.

## What Changes

- `syncJobs`, `uploadItems`, and `panelDismissed` state move from `MaterialsPage` into `CoursePage`
- `MaterialsPage` receives these values and their setters as props
- The `localStorage` key `coursemate_progress_dismissed` is removed — `CoursePage` lifetime already spans all tab switches, so no persistence layer is needed
- `ProgressPanel` rendering logic and the `onClearDone` handler remain inside `MaterialsPage`

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none — this is a pure internal state-ownership refactor with no spec-level behavior changes -->

## Impact

- **`src/CoursePage.jsx`** — gains three state declarations and passes them as props to `MaterialsPage`
- **`src/MaterialsPage.jsx`** — `syncJobs`, `uploadItems`, `panelDismissed` become props instead of local state; `localStorage` read/write for `panelDismissed` is removed
