## Why

The chat experience is passive — users get an answer and must independently decide what to ask next, which breaks the learning flow. Surfacing 2-3 follow-up questions at the end of every assistant reply gives learners a structured path to go deeper without having to construct their next question from scratch.

## What Changes

- The LLM response JSON schema gains a `follow_ups` field: an array of 2-3 suggested follow-up questions generated alongside every reply.
- The system prompt in `_build_layered_system_context` (and the synthesize path) gains an instruction to always produce this field.
- `_parse_synthesis_json` is updated to extract and return the `follow_ups` array.
- `synthesize()` return signature expands to carry `follow_ups` through to `chat.py`.
- All six assistant-message INSERT paths in `chat.py` store follow-ups alongside the message (new `follow_ups` JSONB column on `chat_messages`).
- The chat message API response includes `follow_ups` in the message payload.
- Frontend renders follow-up chips below each assistant message; clicking a chip loads the question text into the chat input box (no auto-submit) so the user can edit or choose a different model before sending.

## Capabilities

### New Capabilities
- `follow-up-generation`: Backend generates 2-3 follow-up questions as part of every LLM response, returned in the `follow_ups` JSON field and persisted to the database.
- `follow-up-chips`: Frontend renders follow-up questions as interactive chips below assistant messages; clicking loads text into the input box without submitting.

### Modified Capabilities

## Impact

- `api/llm.py`: system prompt instruction, `_parse_synthesis_json`, `synthesize()` return value, `run_agent_openai` streaming path
- `api/chat.py`: all six assistant INSERT paths, message API response payload
- `chat_messages` table: new `follow_ups JSONB` column (nullable, default `[]`)
- Frontend (`ChatTab.jsx` or `AssistantMessage` component): chip rendering and click handler that writes to the input ref
