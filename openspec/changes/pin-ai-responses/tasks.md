## 1. Icon Changes in MessageBubble

- [x] 1.1 Add `PinIcon` SVG component to the icon section of `ChatTab.jsx`
- [x] 1.2 Remove `ThumbsUpIcon` and `ThumbsDownIcon` SVG components
- [x] 1.3 Remove the two thumbs-up/down `<button>` elements from the `MessageBubble` AI action bar
- [x] 1.4 Add pin `<button>` in their place, accepting `onPin`, `isPinned` props; render filled/indigo when pinned, outline/gray when not

## 2. Database Migration

- [x] 2.1 Create a new migration file `migrations/004_pinned_messages.sql` containing the following SQL (do not run it):

```sql
CREATE TABLE public.pinned_messages (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id             INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chat_id               INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_message_id       INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    assistant_message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    ai_summary            VARCHAR(300),
    pinned_at             TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pinned_messages_unique_pin UNIQUE (user_id, assistant_message_id)
);
CREATE INDEX idx_pinned_messages_course_user
    ON public.pinned_messages (course_id, user_id);
```

## 3. Pin API — resource=pin branch in api/chat.py

- [x] 3.1 Add a `resource == 'pin'` branch to the existing `api/chat.py` handler (alongside the existing `resource == 'chat'` and `resource == 'message'` branches)
- [x] 3.2 Implement `GET /api/chat?resource=pin&course_id=<id>`: query `pinned_messages` for the authenticated user and course, return `{ pins: [...] }` ordered by `pinned_at DESC`
- [x] 3.3 Implement `POST /api/chat` with `{ resource: "pin", action: "pin", user_message_id, assistant_message_id, course_id, chat_id, ai_summary }`: verify ownership of both message IDs (`chat_messages.user_id = session user_id`), INSERT with `ON CONFLICT DO NOTHING`, return `{ pin: { id, pinned_at } }`
- [x] 3.4 Implement `POST /api/chat` with `{ resource: "pin", action: "unpin", assistant_message_id }`: DELETE the row for `(user_id, assistant_message_id)`, return `{ deleted: true/false }`
- [x] 3.5 Return HTTP 401 for unauthenticated requests and HTTP 403 if ownership check fails

## 4. Pin State (API-backed)

- [x] 4.1 Add `pinnedResponses` state (`useState([])`) to `ChatTab`, populated by fetching `GET /api/chat?resource=pin&course_id=<id>` on mount when `course?.id` is set
- [x] 4.2 Add `derivePinSummary(text)` helper: split on whitespace, take first 5 words, append "…" if content is longer
- [x] 4.3 Implement `handlePinMessage(msg, userMsg)`: call `POST /api/chat { resource: "pin", action: "pin/unpin", ... }`; on success update `pinnedResponses` state; call `derivePinSummary` on the AI content to populate `ai_summary`
- [x] 4.4 Wire `handlePinMessage` and `isPinned` check into the `MessageBubble` render loop (find the preceding user message to pass as `userMsg`)

## 5. Saving Toast

- [x] 5.1 Add `pinToast` state (`useState('')`) to `ChatTab`
- [x] 5.2 In `handlePinMessage`, set `pinToast` to `"Saving…"` (on pin) or `"Pin removed"` (on un-pin), then auto-clear after 1500 ms via `setTimeout`
- [x] 5.3 Render the `pinToast` banner in the JSX return using the same `absolute top-3 left-1/2 -translate-x-1/2` positioning as the existing `switchBanner`

## 6. Pins Panel Component

- [x] 6.1 Create `PinsPanel` sub-component accepting `pins`, `courseName`, `userData`, `materials` props
- [x] 6.2 Render the panel header with a pin icon, "Saved Pins" label, and count badge
- [x] 6.3 Render empty state: "No saved pins yet." when `pins` is empty
- [x] 6.4 For each pin entry render a row with: Chat Name, Model Name, `ai_summary`, date formatted as `mm/dd hh:mm TZ` using `formatDateTime` / `parseUTC`, and a `ChevronDownIcon` that rotates 180° when expanded
- [x] 6.5 Manage `expandedPin` state (`useState(null)`) inside `PinsPanel`; toggle on row or chevron click
- [x] 6.6 When expanded, render a card below the row with two read-only `MessageBubble` instances (user + assistant, all action handler props `null`)
- [x] 6.7 Wire `PinsPanel` into the `ChatTab` JSX return below the main chat `div`, inside the right-hand flex column
