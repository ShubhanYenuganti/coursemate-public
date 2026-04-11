## Why

When "Sync Now" completes and a file has not changed, the frontend currently shows nothing — users cannot tell whether the sync succeeded or found no updates. Integration materials also lack any timestamp surface, so users have no way to judge staleness without triggering another sync.

## What Changes

- `EmbedStatusBadge` gains an `'up_to_date'` state that renders a gray "No changes detected" badge
- Integration material cards (source_type = `gdrive` | `notion`) gain a persistent "Last Edited At: {date + time}" line sourced from the `external_last_edited` field already returned by the API
- On initial materials page load, any row with `embed_status = 'up_to_date'` is mapped to `'done'` in React state so the badge is session-scoped (disappears on next page load)

## Capabilities

### New Capabilities

- `embed-status-up-to-date-badge`: `EmbedStatusBadge` handling for the new `'up_to_date'` status value — renders a distinct "No changes detected" state and maps to `'done'` on page load
- `material-card-last-edited-at`: Persistent "Last Edited At" timestamp line on integration material cards, formatted with month, day, year, hour, and minutes

### Modified Capabilities

## Impact

- `src/MaterialsPage.jsx` — `EmbedStatusBadge` component and `MaterialCard` component
- No API changes; `external_last_edited` is already returned by `GET /courses/{id}/materials`
- No schema changes; `'up_to_date'` is a new string value in the existing `material_embed_jobs.status` text column (written by the backend poller change, read here)
