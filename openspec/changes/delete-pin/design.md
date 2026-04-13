## Context

The pin system in CourseMate lets users save assistant messages. Pins are stored in `pinned_messages` DB table. The backend already has an `_unpin_message` helper (called via POST with `action: 'unpin'`) and a `do_DELETE` handler (currently handles `resource == 'chat'` only). The frontend `PinsPanel` component renders the pin list but has no delete affordance — users must return to the original chat message and click the pin icon to remove a pin.

## Goals / Non-Goals

**Goals:**
- Expose `DELETE /api/chat` with `resource: 'pin'` as the canonical REST endpoint for pin deletion.
- Add a trash icon button in each `PinsPanel` row so users can delete a pin directly.
- Automatically unmark the assistant message in the active chat log when a pin is deleted (no extra wiring — derived from `pinnedResponses` state).

**Non-Goals:**
- Replacing the existing POST `action: 'unpin'` path used by the in-chat pin icon (both paths coexist; both call `_unpin_message`).
- Batch or bulk pin deletion.
- Undo/restore of deleted pins.

## Decisions

### 1. Reuse `_unpin_message` for the DELETE route

`_unpin_message` already accepts `assistant_message_id` and deletes the row with a user-ownership check. Adding it to `do_DELETE` under `resource == 'pin'` costs one routing line and zero new logic.

**Alternative**: Add a separate `_delete_pin_by_id` that takes the pin `id` instead of `assistant_message_id`. Rejected — the frontend already has `assistant_message_id` on every pin object; no need to add `pin.id` to the request.

### 2. Trash icon placement — sibling button, not nested

The entire pin row is a `<button>` (expand/collapse). Nesting a button inside a button is invalid HTML and causes unpredictable click propagation. The trash icon is implemented as a sibling `<button>` rendered after the row button in the DOM, absolutely positioned (or flex-placed) to the right of the chevron.

**Alternative**: Keep trash inside the row button and call `e.stopPropagation()`. Rejected — invalid HTML nesting is a lint/accessibility violation.

### 3. `onDeletePin` prop threaded through `PinsPanel`

`PinsPanel` is a pure display component. The delete handler lives in the parent `ChatTab` where `pinnedResponses` state and fetch credentials live. The prop is `onDeletePin(pin)` — takes the full pin object so the handler has both `assistant_message_id` (for the DELETE request) and `id` (for optimistic state removal).

## Risks / Trade-offs

- **Double-deletion**: If user clicks trash quickly twice, both requests fire. `_unpin_message` uses `cursor.rowcount` to detect deletion; second call returns `{ deleted: false }`. Frontend filters by `assistant_message_id` — filter on already-removed item is a no-op. Safe.
- **POST unpin vs DELETE unpin out of sync**: Both routes call the same `_unpin_message`; they are always in sync. No divergence risk.
- **Row layout shift**: Adding a trash button changes the row's right-side layout. The chevron and trash must be flex-aligned so the collapse button area doesn't visually break.
