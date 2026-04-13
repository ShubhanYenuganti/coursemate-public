## Tasks

### 1. Backend

- [x] 1.1 Register `chat_search` resource in the `do_GET` dispatch block in `api/chat.py`, routing to a new `_search_chats(user, params)` method.
- [x] 1.2 Implement the title matches query in `_search_chats` — FTS on `chats.title` using `to_tsvector` / `plainto_tsquery`, scored with `ts_rank × 3.0`, filtered by `course_id`, `user_id`, `is_archived = FALSE`, capped at 20, ordered by score DESC.
- [x] 1.3 Implement the content matches query in `_search_chats` — FTS on `chat_messages.content` grouped by `chat_id`, scored as `(1 + ln(hit_count)) × best_rank`, capped at 20, ordered by score DESC. Join back to `chats` to retrieve `title` and `last_message_at`. Deduplication against title matches is enforced in SQL via `AND cm.chat_id != ALL(<title_match_ids_array>)` so a chat that matched by title never appears again in the content section.
- [x] 1.4 Return `{ "title_matches": [...], "content_matches": [...] }` from `_search_chats`, with each item shaped as `{ id, title, last_message_at }` (content matches also include `hit_count`).

### 2. Frontend — SearchChat.jsx

- [x] 2.1 **Modal overlay** — render a `fixed inset-0 z-50` backdrop (`bg-black/20`) containing a centered modal (`absolute top-[18%] left-1/2 -translate-x-1/2 w-full max-w-xl bg-white rounded-2xl shadow-xl border border-gray-200 flex flex-col max-h-[62vh]`).
- [x] 2.2 **Search input** — sticky header row with a magnifying-glass icon (`text-indigo-400`), a flex-1 text input (placeholder "Search chats…", auto-focused on mount), and a `✕` button (`text-gray-400`) that clears the query.
- [x] 2.3 **Empty query — recency list** — when `query === ''`, render the `chats` prop sorted by `last_message_at DESC` as a flat list with no section headers and no network request. Revert to this state if the user clears a previous query.
- [x] 2.4 **Debounced fetch** — when `query` is non-empty, wait 300 ms after the last keystroke then `GET /api/chat?resource=chat_search&q=<query>&course_id=<courseId>` and set `results`.
- [x] 2.5 **Two-section results list** — render a scrollable area with a sticky "TITLE MATCHES" section header followed by title match rows, then a sticky "IN CONVERSATION" section header followed by content match rows. Omit a section entirely (header and rows) if its array is empty. Show a "No chats found" empty state when both arrays are empty.
- [x] 2.6 **Result row** — each row renders a chat-bubble icon (`text-gray-400`), the chat title (`text-sm text-gray-800 truncate flex-1`), and a relative date (`text-[11px] text-gray-400`). `hover:bg-indigo-50`. Clicking calls `onSelectChat(id)` then `onClose()`.
- [x] 2.7 **ESC / backdrop dismiss** — attach a `keydown` listener for `Escape` that calls `onClose()`; clicking the backdrop (outside the modal card) also calls `onClose()`.

### 3. Frontend — ChatTab.jsx

- [x] 3.1 Add `searchOpen` state (bool, default `false`). Wire the existing search icon `onClick` to `setSearchOpen(true)`.
- [x] 3.2 Render `{searchOpen && <SearchChat courseId={course.id} chats={chats} onSelectChat={handleConvSelect} onClose={() => setSearchOpen(false)} />}` as a sibling of the main layout so it overlays the full chat area.
