## Why

The chat sidebar lists conversations by recency but provides no way to find a specific chat by content. As the number of chats per course grows beyond a few dozen, users must scroll through the entire list to locate a past conversation. A fast, full-text search modal — triggered from the existing search icon in the sidebar header — solves this without adding UI clutter.

## What Changes

- Add a new backend resource `chat_search` to `api/chat.py` that runs a two-phase PostgreSQL full-text search: title matches (high-weighted, `ts_rank × 3`) first, then content matches (aggregated by `chat_id`, ordered by hit count) for chats not already matched by title. Returns `{ title_matches, content_matches }` in a single response.
- Add two GIN indexes (migration) on `chats.title` and `chat_messages.content` so full-text queries stay fast at >500 chats.
- Add `SearchChat.jsx` — a centered overlay modal with an indigo/gray/white theme, a search input, and a scrollable two-section results list (Title Matches → In Conversation). Empty query shows all chats sorted by recency from already-loaded state (no extra fetch).
- Wire the existing search icon button in `ChatTab.jsx` to open the modal; pass `onSelectChat` and `onClose` callbacks.

## Capabilities

### New Capabilities

- `chat-search`: Full-text search across chat titles and message content within a course, surfaced as a centered command-palette modal. Results are ranked: title matches appear first, content matches (aggregated hit count) appear below as the user scrolls.

### Modified Capabilities

<!-- None — no existing spec-level behavior changes. -->

## Impact

- `api/chat.py`: New `chat_search` resource handler in `do_GET`; new `_search_chats` method with two-CTE SQL query.
- `src/SearchChat.jsx`: New component (modal overlay, search input, two-section results list, debounce, ESC/backdrop dismiss).
- `src/ChatTab.jsx`: Search icon gains `onClick` to open modal; `SearchChat` rendered conditionally as an overlay.
- Database: two `CREATE INDEX IF NOT EXISTS … USING gin(to_tsvector(…))` statements (simple migration, no schema change).
- No new dependencies.
