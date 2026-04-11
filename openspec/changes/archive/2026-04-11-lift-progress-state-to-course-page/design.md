## Context

`MaterialsPage` currently owns three pieces of state related to the progress panel:

| State | Type | Purpose |
|-------|------|---------|
| `syncJobs` | `array` | In-flight and recently-completed sync operations |
| `uploadItems` | `array` | In-flight and recently-completed file uploads (contains `File` objects — not serializable) |
| `panelDismissed` | `boolean` | Whether the user has closed the progress panel |

Because `CoursePage` conditionally renders `MaterialsPage` (only when the "Materials" tab is active), switching tabs unmounts `MaterialsPage` and destroys this state. On remount, all three reset to their initial values — `syncJobs`/`uploadItems` to `[]` and `panelDismissed` reading from `localStorage` — so the panel never reappears even with active work in progress.

`panelDismissed` already attempts persistence via `localStorage` (`coursemate_progress_dismissed`), but the job arrays are not persisted (and can't be, since `uploadItems` contains `File` objects). The net effect is: the dismissal state survives but there are no jobs to show, so the panel condition `syncJobs.length > 0 || uploadItems.length > 0` is always false on remount.

## Goals / Non-Goals

**Goals:**
- Progress panel survives tab switches within a single browser session
- No change to panel behavior from the user's perspective (same render logic, same dismiss/clear actions)
- Remove the now-unnecessary `localStorage` persistence for `panelDismissed`

**Non-Goals:**
- Surviving full page refreshes (jobs are inherently session-scoped; the backend is the source of truth after a reload)
- Sharing progress state across browser tabs or users
- Moving `ProgressPanel` component itself out of `MaterialsPage`

## Decisions

### D1: Lift state to `CoursePage`, pass as props

`CoursePage` lives for the entire user session on a given course. Moving `syncJobs`, `uploadItems`, and `panelDismissed` (plus their setters) into `CoursePage` and threading them down as props gives `MaterialsPage` the same interface it has today, while the state outlives any individual tab mount.

**Alternative considered — keep all tabs mounted (`display: none`)**  
Wrapping each tab in a persistent `<div className={hidden ? 'hidden' : ''}>` would also preserve state with zero prop changes. Rejected because it mounts all tabs eagerly, runs all polling simultaneously from page load, and hides complexity behind a CSS trick rather than making ownership explicit.

**Alternative considered — serialize jobs to `localStorage`**  
Would survive page refreshes but `uploadItems` contain `File` objects which are not JSON-serializable. Partial serialization (sync jobs only) would create inconsistency. Adds re-hydration complexity with no clear benefit for the targeted problem.

### D2: Remove `localStorage` for `panelDismissed`

With state owned by `CoursePage`, there is no longer any reason to persist `panelDismissed` to storage. `CoursePage` initializes `panelDismissed` to `false` on page load, which is correct — a fresh session should show the panel when jobs are active. The three `localStorage` call sites in `MaterialsPage` are removed.

### D3: `ProgressPanel` and all handlers stay in `MaterialsPage`

`ProgressPanel` is rendered inside `MaterialsPage` and references many other `MaterialsPage`-local values (`embedStatusMap`, `materials`, etc.). Moving it up would require lifting far more state than is warranted. The panel stays where it is; only its three driving state variables move up.

## Risks / Trade-offs

- **`CoursePage` gains materials-domain state** — `syncJobs` and `uploadItems` are semantically about material processing. Lifting them into the course shell component is a mild violation of single-responsibility. Acceptable because the coupling is explicit (props) and the fix is targeted.  
  → Mitigation: group the three props together in `CoursePage` with a clear comment block.

- **Prop-drilling one level** — `MaterialsPage` now receives these as props rather than owning them. Any future refactor extracting sub-components from `MaterialsPage` would need to thread them further.  
  → Mitigation: acceptable for now; if `MaterialsPage` grows a deeper tree, a context can be introduced then.

## Migration Plan

1. Add state declarations to `CoursePage` with initial values matching current `MaterialsPage` defaults
2. Pass all three state values and their setters as props to `MaterialsPage`
3. In `MaterialsPage`, convert the three `useState` declarations to destructured props
4. Remove all `localStorage.getItem/setItem/removeItem` calls for `coursemate_progress_dismissed`
5. No database or API changes required; no deployment steps beyond a normal frontend deploy
