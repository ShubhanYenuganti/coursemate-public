## Why

Pinned responses currently show a client-truncated “summary” (first five words of the assistant body), which is noisy and not aligned with the conversation topic. The model can produce a short keyword-focused phrase; persisting it per assistant message lets pins and future UI reuse a single source of truth.

## What Changes

- Add nullable `summary` on `chat_messages` for assistant rows; populate it from the LLM on send, edit, regenerate, and non-stream/stream paths.
- Change synthesis prompts and parsing so the model returns JSON with `reply` (markdown answer) and `summary` (about 5–6 words). Parse failures fall back to plain text with `summary` null.
- **Pin list** `ai_summary` field SHALL prefer `chat_messages.summary` joined from the assistant message, with legacy fallback to `pinned_messages.ai_summary`.
- **Pin create** SHALL ignore client `ai_summary` and set `pinned_messages.ai_summary` from the assistant row’s `summary` (or empty).
- **Frontend** removes `derivePinSummary`; pin requests omit `ai_summary`; optimistic UI uses `assistantMsg.summary`.

## Capabilities

### New Capabilities

- `chat-message-summary`: LLM JSON synthesis shape, `chat_messages.summary` column, persistence on all assistant message writes, message list API includes `summary`, pin GET/POST behavior, frontend consumption.

### Modified Capabilities

- (none in `openspec/specs/` — prior pin behavior lived only under `openspec/changes/pin-ai-responses`; this change supersedes client-derived summaries as documented in that change.)

## Impact

- `api/llm.py` — structured output parsing; non-agentic and agentic paths; verifier/repair on inner `reply` markdown.
- `api/chat.py` — all assistant `INSERT`s, `RETURNING`, message `SELECT`s, `_list_pins`, `_pin_message`.
- `api/db.py` — `init_db` schema for new installs.
- New SQL migration for existing databases.
- `src/ChatTab.jsx` — remove helper; adjust pin body and optimistic state.