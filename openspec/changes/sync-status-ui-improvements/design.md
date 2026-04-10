## Context

The backend poller redesign (`integration-poller-redesign`) introduces a new `material_embed_jobs.status` value: `'up_to_date'`. This is written when a targeted "Sync Now" run finds no changes (i.e., `_needs_ingest → False`). The frontend currently has no handling for this value — it will render nothing (same as `'done'`), which means users get no feedback after a sync that found nothing new.

Additionally, integration materials (`source_type = gdrive | notion`) already expose `external_last_edited` in every `GET /courses/{id}/materials` response, but this timestamp is not surfaced anywhere in the UI. Users have no way to judge the staleness of a material without triggering a sync.

## Goals / Non-Goals

**Goals:**
- Surface `'up_to_date'` as a distinct badge state ("No changes detected") in `EmbedStatusBadge`
- Make the badge session-scoped: map `'up_to_date'` → `'done'` in React state on initial page load so it disappears after reload
- Show a persistent "Last Edited At: {formatted timestamp}" line on integration material cards using `external_last_edited`
- Include hours and minutes in the timestamp (e.g., "Apr 9, 2026, 10:30 AM")

**Non-Goals:**
- Any API or schema changes — `external_last_edited` and `embed_status` are already available
- Changing the embed pipeline or polling behavior — that is handled in `integration-poller-redesign`
- Changing the badge behavior for any other `embed_status` values

## Decisions

### Decision: Session-scoped badge via React state mapping on load

**Chosen**: When the materials list is fetched, map any row with `embed_status === 'up_to_date'` to `'done'` in the React state (before rendering). If a sync runs during the session and the poller returns `'up_to_date'`, the component detects the polled status and shows the badge. On the next page load, it is gone.

**Alternative considered**: Never write `'up_to_date'` to the DB; frontend infers no-change from fast completion. Rejected: fragile timing dependency; no signal from the poller to the frontend.

**Alternative considered**: Clear `'up_to_date'` in the DB after the frontend reads it. Rejected: requires a dedicated API call or a write-on-read pattern that adds unnecessary complexity.

---

### Decision: Timestamp format with `toLocaleString`

**Chosen**: `external_last_edited.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })` — locale-aware, includes hours and minutes, outputs "Apr 9, 2026, 10:30 AM" style.

**Alternative considered**: Hard-coded `en-US` locale. Rejected: unnecessary when `undefined` already uses the browser locale, which is correct for internationalization.

---

### Decision: Show "Last Edited At" only for integration materials

**Chosen**: Render the line only when `material.source_type === 'gdrive' || material.source_type === 'notion'` — i.e., materials from integrations where `external_last_edited` is meaningful. Manually uploaded materials have no meaningful "last edited at" from an external source.

**Alternative considered**: Show for all materials. Rejected: `external_last_edited` is only populated for integration-synced materials; showing it for manual uploads would be empty or null and confusing.

## Risks / Trade-offs

**`external_last_edited` may be null for materials that failed mid-upload** → The "Last Edited At" line should be conditionally rendered only when the value is non-null. This is a natural guard and not a regression.

**Badge is session-scoped only** → The intended behavior: after reload users see the normal `'done'` state (nothing), which is correct. If a user expects persistent "no changes" feedback, they will not see it after reload — acceptable given the design decision.

## Migration Plan

1. Deploy frontend change — no backend dependency (reads existing fields)
2. Deploy `integration-poller-redesign` Lambda — begins writing `'up_to_date'` values
3. No rollback risk: if frontend is deployed before the backend, `'up_to_date'` is never written so the new badge code path is never reached
