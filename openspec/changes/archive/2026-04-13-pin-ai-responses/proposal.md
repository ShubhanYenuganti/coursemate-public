## Why

Users want to save specific AI responses for later reference — currently there's no way to bookmark or retrieve a helpful answer without scrolling back through chat history. The existing thumbs up/down buttons provide no persistent value to the user.

## What Changes

- Remove `ThumbsUpIcon` and `ThumbsDownIcon` from the `MessageBubble` AI action bar
- Add a `PinIcon` button in their place on each AI response
- On pin click: display a transient "Saving…" toast banner at the top of the page
- Add a **Pins panel** below the chat area (and Sources box when open) inside `ChatTab`
- Pins panel lists saved entries with: Chat Name · Model Name · 4–5 word AI summary · date `mm/dd hh:mm TZ` · chevron toggle icon
- Clicking a pin row or its chevron expands a card showing the user message and AI reply, styled identically to the chat message bubbles
- Clicking the chevron again (when expanded) collapses the card

## Capabilities

### New Capabilities
- `pinned-responses`: Pin-saving UI for AI responses — includes pin button on message bubbles, saving toast, pinned entries panel with expandable chat cards, and API-backed persistence
- `pinned-messages-backend`: Backend persistence for pinned messages — new `pinned_messages` table, API endpoint for pin/unpin, and list retrieval per course

### Modified Capabilities
<!-- No existing spec-level requirement changes -->

## Impact

- `src/ChatTab.jsx`: add `PinIcon`, `PinToast`, `PinsPanel` component; remove `ThumbsUpIcon` / `ThumbsDownIcon` usage; add `pinnedResponses` state backed by API
- `api/chat.py` (or new `api/pins.py`): new `/api/pin` endpoint handling `pin`, `unpin`, `list` actions
- Database: new `pinned_messages` table with FK references to `chat_messages`, `chats`, `courses`, `users`
- Migration: one SQL statement to create the table (provided inline, not as a script file)
