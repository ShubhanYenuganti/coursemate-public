# Chat Search — Message-Level Results — Design Spec

Date: 2026-05-31
Status: Approved (brainstorming complete; ready for implementation plan)
Category: Easy Improvement (extends an existing, working feature)

## Summary

Improve the existing in-course chat search (`SearchChat` command palette) so that
"In Conversation" (content) matches show **why** they matched and let the user jump
straight to the matching message. Today a content match shows only the chat title +
timestamp and, on click, opens the chat at the top with no indication of the hit.

This adds: (1) a highlighted **snippet** of the best-matching message per chat in the
results, and (2) **deep-linking** — clicking a content match opens the chat scrolled to
and briefly highlighting that message.

## Context: What Already Exists

This is an enhancement, not a new feature. Already built and working:

- `chat_messages` are stored with a GIN full-text index on `content`.
- `GET /api/chat?resource=chat_search&course_id=<id>&q=<query>` (`api/chat.py::_search_chats`)
  runs FTS across the user's non-archived chats in the course, returning `title_matches`
  and `content_matches` (chat-level: `id`, `title`, `last_message_at`, `hit_count`).
- `src/SearchChat.jsx` is a command-palette modal (debounced fetch, recency list on empty
  query, two result sections, click-to-open) opened from `ChatTab` via `searchOpen` state.

The gap: content matches are chat-level only — no snippet, no matching-message identity,
no scroll-to on open.

## Goals

- Each content match displays a one-line highlighted snippet from the best-matching message.
- Clicking a content match opens the chat, scrolls the matching message into view, and
  applies a brief highlight.
- No regression to title matches or the empty-query recency list.

## Non-Goals (YAGNI)

- Including archived chats in search.
- Semantic / vector search in this UI (the surface is intentionally FTS).
- More than one snippet/match row per chat.
- Jumping to the Nth occurrence within a message.
- Any change to chat synthesis / grounding retrieval.

## Architecture & Data Flow

```
User types in SearchChat modal
   │ debounced GET /api/chat?resource=chat_search&course_id&q
   ▼
_search_chats (api/chat.py)
   ├── title_matches   (unchanged)
   └── content_matches (CHANGED): best message per chat
         DISTINCT ON (chat_id) ordered by ts_rank desc
         + ts_headline snippet
         → returns: id, title, last_message_at,
                    message_id, message_index, snippet, hit_count
   ▼
SearchChat renders content rows with snippet (<mark> → styled span)
   │ onSelectChat(chatId, { messageId, messageIndex })
   ▼
ChatTab sets activeConv + pendingScrollMessageId
   │ messages load
   ▼
effect: scrollIntoView({block:'center'}) + transient highlight (~2s)
```

## Component Changes

### 1. `api/chat.py::_search_chats` — message-level content matches

Replace the chat-level `content_matches` aggregation with a per-chat best-message
selection:

- Rank each matching message by
  `ts_rank(to_tsvector('english', cm.content), plainto_tsquery('english', q))`.
- Use `DISTINCT ON (cm.chat_id)` ordered by `(chat_id, rank DESC)` to take the single
  best-matching message per chat.
- Generate the snippet with
  `ts_headline('english', cm.content, plainto_tsquery('english', q),
   'StartSel=<mark>,StopSel=</mark>,MaxFragments=1,MaxWords=18,MinWords=6')`.
- Keep the existing course/user/non-archived filters and the
  "exclude chats already in title_matches" rule.
- Preserve `hit_count` (number of matching messages in the chat) for ranking/secondary display.

Returned content-match item shape:
```json
{
  "id": <chat_id>,
  "title": "...",
  "last_message_at": "...",
  "message_id": <int>,
  "message_index": <int>,
  "snippet": "...<mark>handshake</mark>...",
  "hit_count": <int>
}
```
Title-match item shape is unchanged.

### 2. `src/SearchChat.jsx` — render snippet, pass target on click

- `ResultRow` accepts an optional `snippet` and an optional `target` ({ messageId, messageIndex }).
- When `snippet` is present, render a second line below the title showing the snippet,
  converting the `<mark>…</mark>` markers into a highlighted `<span>` (no raw HTML
  injection — split on the markers and render React nodes).
- Content rows call `onSelectChat(chat.id, { messageId, messageIndex })`; title rows and
  recency rows call `onSelectChat(chat.id)` (no target) as today.

### 3. `src/ChatTab.jsx` — scroll-to + highlight on open

- Extend the `onSelectChat` handler passed to `SearchChat` to accept an optional second
  `target` argument. When present, store `pendingScrollMessageId` (the `message_id`).
- Give each rendered message element a stable DOM id, e.g. `id={`msg-${m.id}`}`.
- Add an effect that fires when messages for the active chat have loaded and
  `pendingScrollMessageId` is set: locate `#msg-<id>`, `scrollIntoView({ block: 'center' })`,
  apply a transient highlight class for ~2s, then clear `pendingScrollMessageId`.
- If the element is not found (deleted/out of range), clear the pending state and leave the
  chat at its default position (no error).

## Error / Edge Handling

- Target message missing (deleted or not in loaded range): open chat normally, no scroll, no error.
- `snippet` null/absent for a content match: row falls back to the current title-only display.
- Empty query: unchanged recency list behavior.
- Snippet rendering never injects raw HTML; only the known `<mark>`/`</mark>` markers are
  interpreted, everything else is plain text.

## Acceptance Criteria

- Searching a term that appears in a message body shows an "In Conversation" result with a
  highlighted snippet containing that term.
- Clicking that result opens the chat, scrolls the matching message into view, and briefly
  highlights it.
- Title matches and the empty-query recency list behave exactly as before.
- Searching a deleted message's former text does not crash; clicking a stale result opens
  the chat without scrolling.
- Archived chats still do not appear in results.

## Files Likely Touched

- `api/chat.py` (`_search_chats`)
- `src/SearchChat.jsx`
- `src/ChatTab.jsx`
- `tests/` — backend test for the new content-match shape (snippet + message_id)

## Verification Plan

- Backend: unit test calling the search path (or a SQL-shape assertion) confirming content
  matches include `message_id`, `message_index`, and a `<mark>`-wrapped `snippet`.
- Frontend: `npm run build` succeeds; manual flow — search a known phrase, confirm snippet
  renders highlighted, click → chat opens scrolled to and highlighting the matching message.
- Regression: title-only search and empty-query recency list unchanged.
