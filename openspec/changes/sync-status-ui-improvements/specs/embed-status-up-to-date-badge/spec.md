## ADDED Requirements

### Requirement: EmbedStatusBadge renders a distinct state for up_to_date status
The `EmbedStatusBadge` component SHALL render a gray "No changes detected" badge when `embed_status === 'up_to_date'`. This badge SHALL be visually distinct from the existing syncing (purple), pending/processing (amber), and failed (red) states.

#### Scenario: up_to_date badge rendered after targeted sync
- **WHEN** the materials list is refreshed after a "Sync Now" run and the poller writes `embed_status = 'up_to_date'` for a material
- **THEN** the `EmbedStatusBadge` for that material SHALL display a gray "No changes detected" badge

#### Scenario: up_to_date badge absent for other status values
- **WHEN** `embed_status` is `null`, `'done'`, `'syncing'`, `'pending'`, `'processing'`, `'failed'`, or `'skipped'`
- **THEN** the component SHALL NOT render the "No changes detected" badge

### Requirement: up_to_date status is session-scoped via React state mapping on load
On initial materials fetch, the frontend SHALL map any row with `embed_status === 'up_to_date'` to `'done'` in React state before rendering. This ensures the "No changes detected" badge is only visible during the active session in which the sync ran.

#### Scenario: Page reload clears the badge
- **WHEN** a user reloads the materials page after a sync that produced `embed_status = 'up_to_date'`
- **THEN** the badge SHALL NOT appear — the status is treated as `'done'` on load

#### Scenario: Badge visible within the same session
- **WHEN** a materials list poll returns a row with `embed_status = 'up_to_date'` during an active session (without a full page reload)
- **THEN** the "No changes detected" badge SHALL be visible for that material
