## Context

`CoursePage` currently holds three progress-panel state values in memory — `syncJobs`, `uploadItems`, `panelDismissed` — lifted there from `MaterialsPage` so they survive tab switches. A page refresh destroys `CoursePage` entirely, losing all in-flight job tracking. Separately, `fetchMaterials()` is called immediately after a file upload or sync confirms, which fetches DB records whose `embed_status` is still `"pending"` or `"processing"`. These items land in `visibleMaterials` and display in the grid before they are usable.

## Goals / Non-Goals

**Goals:**
- Progress panel state (jobs, uploads, dismissed flag) survives a full page refresh
- Done upload items reappear after refresh (user can still see what finished)
- Materials mid-indexing do not appear in the materials grid until embedding reaches a terminal state
- Interrupted uploads (`"uploading"` / `"confirming"` at refresh time) surface as errors on restore

**Non-Goals:**
- Server-side job state persistence — localStorage is sufficient; polling already re-syncs statuses
- Cross-device or cross-browser persistence
- Restoring upload progress percentage or byte counts

## Decisions

### D1: localStorage over server-side state

**Decision**: Serialize progress panel state to `localStorage` keyed by `coursemate_progress_${courseId}`.

**Rationale**: The existing polling mechanism already re-fetches embed statuses from the server within seconds of mount. localStorage only needs to preserve *which items exist* and *that the panel was open* — the server fills in current statuses. A server-side approach would require new API endpoints and adds latency.

**Alternative considered**: URL-encoded state (query params). Rejected — progress state is transient UX, not a shareable route.

### D2: Write on every state change, read on mount

**Decision**: A single `useEffect` in `CoursePage` watches `[syncJobs, uploadItems, panelDismissed, courseId]` and writes to localStorage. A lazy initializer on each `useState` reads from localStorage on mount.

**Rationale**: Keeps the persistence logic co-located in one file (`CoursePage.jsx`) without adding any new hooks or utilities.

**Alternative considered**: Debounced writes. Rejected — state changes are infrequent and small; debouncing adds complexity with no measurable benefit.

### D3: Scrub interrupted uploads on restore

**Decision**: On restore, any `uploadItem` with `status === "uploading"` or `status === "confirming"` is patched to `status: "error"`. All other statuses (including `"done"`, `"indexing"`, `"failed"`) restore verbatim.

**Rationale**: These statuses mean an active HTTP request was in flight. The request died with the page; the server never received the complete upload or confirmation. Showing them as "error" is honest; silently dropping them would hide the fact something was interrupted.

### D4: Terminal-status filter on visibleMaterials

**Decision**: `visibleMaterials` in `MaterialsPage` includes only materials where `embed_status` is `"done"`, `"failed"`, or `"skipped"`.

**Rationale**: The ProgressPanel is the designated owner of in-flight items. Showing indexing materials in the grid creates a confusing dual-display and surfaces materials before they are queryable. The existing `prevHadActiveJobs` effect already calls `fetchMaterials()` when all jobs finish, so the material will appear in the grid at the right moment without any additional plumbing.

**Alternative considered**: Show all materials but badge indexing ones as "not ready". Rejected — users cannot use indexing materials in chat; showing them suggests otherwise.

## Risks / Trade-offs

- **Stale localStorage on long gaps**: If a user leaves the page for hours and jobs complete server-side, the panel will show items that are now "done" with stale statuses. The embed-status polling will correct this within 2 seconds of mount — acceptable flicker.
- **localStorage quota**: Progress state is small (a few KB at most). Not a practical concern.
- **`"skipped"` materials**: Materials the embedder skips (wrong type, too large) are included in the grid. This is intentional — they are valid materials even if not indexed.

## Migration Plan

No data migration needed. The localStorage keys are new and scoped to courseId. Old behavior simply disappears on first mount after deploy.
