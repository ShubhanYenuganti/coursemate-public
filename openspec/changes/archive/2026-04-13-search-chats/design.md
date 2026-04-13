## Backend

### New resource: `chat_search`

`GET /api/chat?resource=chat_search&q=<query>&course_id=<id>`

Two CTEs in a single query:

1. **Title matches** — FTS on `chats.title` with `ts_rank × 3.0` boost, filtered by `course_id` / `user_id` / `is_archived = FALSE`.
2. **Content matches** — FTS on `chat_messages.content`, grouped by `chat_id`, scored as `(1 + ln(hit_count)) × best_rank`, excludes chat IDs already in title matches.

Response shape:
```json
{
  "title_matches":   [{ "id", "title", "last_message_at" }],
  "content_matches": [{ "id", "title", "last_message_at", "hit_count" }]
}
```

Both lists capped at 20 results each. Deduplication between lists happens in SQL (content query adds `AND cm.chat_id NOT IN (title match ids)`).

### GIN indexes (migration)

See `migrations/007_chat_search_gin_indexes.sql`. Run against the database before deploying the `chat_search` endpoint.

---

## Frontend

### SearchChat.jsx

**Props:** `courseId`, `chats` (already-loaded array from ChatTab), `onSelectChat(chatId)`, `onClose()`

**State:** `query` (string), `results` (`{ title_matches, content_matches } | null`), `loading` (bool)

**Behavior:**
- `query === ''` → render `chats` sorted by `last_message_at DESC`, flat list, no section headers. No fetch.
- `query !== ''` → debounce 300 ms → `GET /api/chat?resource=chat_search&q=…&course_id=…` → set `results`.
- Row click → `onSelectChat(id)` then `onClose()`.
- `Escape` keydown → `onClose()`.
- Backdrop click → `onClose()`.

**Layout:**
```
fixed inset-0 z-50
  backdrop: bg-black/20
  modal: absolute top-[18%] left-1/2 -translate-x-1/2
         w-full max-w-xl bg-white rounded-2xl shadow-xl border border-gray-200
         flex flex-col max-h-[62vh]

  header (sticky):
    px-4 py-3 flex items-center gap-3 border-b border-gray-100
    [search icon indigo-400] [input flex-1 text-sm gray-800] [✕ button gray-400]

  results (overflow-y-auto flex-1):
    empty query  → flat rows, no section label
    with query   → section label "TITLE MATCHES" then rows,
                   then section label "IN CONVERSATION" then rows
                   (section label omitted if that section is empty)
    no results   → centered "No chats found" text-sm text-gray-400

  row:
    px-4 py-2.5 flex items-center gap-3 hover:bg-indigo-50 cursor-pointer
    [chat-bubble icon text-gray-400]
    [title text-sm text-gray-800 truncate flex-1]
    [relative date text-[11px] text-gray-400 flex-shrink-0]

  section label:
    px-4 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider
    bg-gray-50 border-b border-gray-100 sticky top-0
```

### ChatTab.jsx changes

- Add `searchOpen` state (bool, default false).
- Search icon `onClick` → `setSearchOpen(true)`.
- Render `{searchOpen && <SearchChat courseId={course.id} chats={chats} onSelectChat={handleConvSelect} onClose={() => setSearchOpen(false)} />}` — positioned as a sibling of the main layout so it overlays everything.

---

## Decisions

- **No keyboard navigation (arrow + Enter):** scroll and click only, per spec.
- **No snippets in results:** title + relative date only, keeps rows compact.
- **Empty query uses prop data:** avoids a redundant fetch on modal open.
- **Archived chats excluded:** `chat_search` only queries `is_archived = FALSE`.
- **Content matches capped at 20:** prevents overwhelming results; title matches also capped at 20.
- **Deduplication in SQL:** content CTE filters out title-matched chat IDs so a chat never appears in both sections.
