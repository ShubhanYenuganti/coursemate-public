## 1. CoursePage — add state and pass props

- [x] 1.1 Add `syncJobs` / `setSyncJobs` state (initial `[]`) to `CoursePage`
- [x] 1.2 Add `uploadItems` / `setUploadItems` state (initial `[]`) to `CoursePage`
- [x] 1.3 Add `panelDismissed` / `setPanelDismissed` state (initial `false`) to `CoursePage`
- [x] 1.4 Pass all six values as props to `<MaterialsPage>` in the Materials tab render

## 2. MaterialsPage — consume props instead of local state

- [x] 2.1 Add `syncJobs`, `setSyncJobs`, `uploadItems`, `setUploadItems`, `panelDismissed`, `setPanelDismissed` to the `MaterialsPage` function signature
- [x] 2.2 Remove the three `useState` declarations for these values
- [x] 2.3 Remove `localStorage.getItem("coursemate_progress_dismissed")` initializer
- [x] 2.4 Remove all `localStorage.setItem("coursemate_progress_dismissed", "true")` calls
- [x] 2.5 Remove all `localStorage.removeItem("coursemate_progress_dismissed")` calls

## 3. Verification

- [x] 3.1 Start an upload, switch to Chat tab, return to Materials — confirm `ProgressPanel` is still visible with correct items
- [x] 3.2 Start a sync, switch tabs, return — confirm sync jobs are still listed
- [x] 3.3 Dismiss the panel, switch tabs, return — confirm panel stays dismissed
- [x] 3.4 Confirm no console errors or prop-type warnings on tab switch
