# Auto Chat Title Suggestion

**Date:** 2026-03-24
**Status:** Approved

## Overview

On every qualifying message exchange (send, edit, regenerate), call GPT-4o-mini with accumulated conversation context to suggest a minimally-altered refined title for the chat. The suggested title is delivered via the existing `done` SSE event and persisted to the DB. The initial title on chat creation changes from the first-80-chars of the user's message to the placeholder `"New Chat"`.

## Goals

- Titles evolve naturally as the conversation topic becomes clearer
- Minimal disruption: the title changes infrequently (every 4th exchange) and only makes small alterations
- Manual renames are respected permanently — once a user renames a chat, auto-titling stops for that chat
- No new API endpoints; the title is piggybacked onto existing response shapes

## Non-Goals

- Real-time streaming of title updates (not needed — title arrives with `done`)
- Title undo/history
- Per-user opt-out toggle in UI

---

## Database

Migration already applied:

```sql
ALTER TABLE chats ADD COLUMN title_auto BOOLEAN NOT NULL DEFAULT TRUE;
```

`title_auto = TRUE` means auto-titling is active. Set to `FALSE` permanently when the user manually renames via `_update_chat`.

---

## Firing Cadence

Auto-titling fires on exchange 1 (the first exchange, to replace "New Chat"), then on every 4th exchange thereafter: 1, 5, 9, 13, …

**Formula** (using zero-based `next_idx` already available in send/edit handlers):

```python
exchange_number = (next_idx // 2) + 1
should_suggest = (exchange_number == 1) or ((exchange_number - 1) % 4 == 0)
```

`next_idx` is the message index of the user message being inserted. The assistant message lands at `next_idx + 1`.

---

## Backend

### `api/llm.py` — `suggest_chat_title`

New function:

```python
def suggest_chat_title(
    conn,
    user_id: int,
    chat_id: int,
    current_title: str,
    recent_msgs: list,   # from _fetch_recent_messages in tools.py
) -> str | None:
```

- Fetches the user's stored OpenAI API key via `_get_api_key(conn, user_id, "openai")`
- Calls GPT-4o-mini (`gpt-4o-mini`) with:
  - **System prompt**: instruct minimal-alteration title refinement, max 80 chars, no quotes, no markdown, return strict JSON `{"title": "..."}`
  - **User payload**: current title + last up to 6 message turns (role + content truncated to 300 chars each)
- Parses the JSON response and returns the `title` string
- Returns `None` silently on any error (network failure, missing API key, bad JSON, etc.)
- `temperature=0`, `response_format={"type": "json_object"}`

### `api/chat.py` — `_stream_send_message` / `_send_message`

After inserting the assistant message:

1. Re-fetch `chat['title_auto']` (available from the `_get_chat` call at the top of the handler)
2. Compute `should_suggest` from `next_idx`
3. If `chat['title_auto']` and `should_suggest`:
   - Fetch recent messages via `_fetch_recent_messages(conn, chat_id, limit=6)`
   - Call `suggest_chat_title(...)`
   - If a title is returned: `UPDATE chats SET title = %s WHERE id = %s`
4. Include `suggested_title` (the new title string, or `None`) in the response:
   - Streaming: add `"suggested_title"` key to the `done` SSE event payload
   - Non-streaming: add `"suggested_title"` key to the JSON response body

### `api/chat.py` — `_stream_edit_message` / `_edit_message`

Same pattern as send. `next_idx` is derived from the user message's `message_index` (already fetched as part of the edit flow).

### `api/chat.py` — `_regenerate_message`

Same pattern. `next_idx` is derived from the assistant message's `message_index - 1`.

### `api/chat.py` — `_update_chat`

Add `title_auto = FALSE` to the existing UPDATE:

```sql
UPDATE chats SET title = %s, title_auto = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE id = %s
```

### `api/chat.py` — `_create_chat`

No change needed in the backend handler — the frontend will now always send `"New Chat"` as the title.

---

## Frontend — `src/ChatTab.jsx`

### Chat creation (in `handleSend`)

```js
// Before:
const title = text.slice(0, 80);

// After:
const title = 'New Chat';
```

Also update the optimistic placeholder (already `'New Chat'` in `handleNewChat` — no change needed there).

### `done` event handler

In the three streaming `done` handlers (`handleSend`, `handleEditMessage`, `handleRegenerateMessage`), after updating messages state, check for `suggested_title`:

```js
if (data.suggested_title) {
  setChats((prev) =>
    prev.map((c) => c.id === chatId ? { ...c, title: data.suggested_title } : c)
  );
}
```

---

## Error Handling

- `suggest_chat_title` always returns `None` on failure — the `done` event simply omits `suggested_title`, and the existing title is unchanged
- The title update DB write is fire-and-continue: if it fails, the chat title stays as-is and no error is surfaced to the user
- Missing OpenAI API key → `suggest_chat_title` returns `None`

---

## Data Flow (streaming send)

```
User sends message
  → insert user_message
  → synthesize (agentic loop)
  → insert assistant_message
  → [if title_auto AND cadence fires]
      → fetch recent_msgs
      → call GPT-4o-mini → suggested_title
      → UPDATE chats SET title = suggested_title
  → send SSE done { user_message, assistant_message, suggested_title? }
Frontend receives done
  → update messages state
  → [if suggested_title] update chats state title
```
