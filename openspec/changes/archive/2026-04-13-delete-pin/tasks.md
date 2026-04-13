## 1. Backend — DELETE route for pins

- [x] 1.1 In `api/chat.py` `do_DELETE`, add `elif resource == 'pin': self._unpin_message(user, data)` before the `else` branch

## 2. Frontend — handleDeletePin function

- [x] 2.1 In `ChatTab`, add `handleDeletePin(pin)` async function that calls `DELETE /api/chat` with `{ resource: 'pin', assistant_message_id: pin.assistant_message_id }` and on success filters `pinnedResponses` to remove the entry

## 3. Frontend — PinsPanel trash icon

- [x] 3.1 Add `onDeletePin` prop to `PinsPanel` component signature
- [x] 3.2 In each pin row, add a sibling `<button>` (outside the expand/collapse button) with a trash/`XMarkIcon` or inline SVG trash icon, styled `text-gray-400 hover:text-red-500`, that calls `onDeletePin(pin)` on click
- [x] 3.3 Pass `onDeletePin={handleDeletePin}` to `<PinsPanel>` at the call site in `ChatTab`
