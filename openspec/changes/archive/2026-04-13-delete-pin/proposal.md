## Why

Pins in the PinsPanel can currently only be removed by clicking the pin icon on the original assistant message in the chat log — there is no way to delete a pin directly from the PinsPanel. Users need a one-click trash icon in the pin list itself so they can manage saved pins without hunting for the original message.

## What Changes

- Add `'pin'` resource handling to the existing `do_DELETE` method in `api/chat.py`, delegating to the already-implemented `_unpin_message` helper.
- Add a `handleDeletePin(pin)` function to `ChatTab` that calls `DELETE /api/chat` and removes the pin from `pinnedResponses` state.
- Pass `onDeletePin` prop into `PinsPanel`.
- Add a trash icon button to the right of the chevron in each pin row inside `PinsPanel`; clicking it deletes the pin and stops row expand/collapse from triggering.

## Capabilities

### New Capabilities

- `pin-delete`: Ability to delete a pin directly from the PinsPanel via a trash icon, removing it from the database and unmarking the assistant message in the chat log.

### Modified Capabilities

<!-- None — no existing spec-level behavior changes. -->

## Impact

- `api/chat.py`: `do_DELETE` gains a `pin` resource branch.
- `src/ChatTab.jsx`: New `handleDeletePin` function; `PinsPanel` receives `onDeletePin` prop; trash icon added to pin rows.
- No schema changes, no new dependencies.
