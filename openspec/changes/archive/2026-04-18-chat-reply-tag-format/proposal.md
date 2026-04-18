## Why

LLM responses embed markdown content inside a JSON string value, causing LaTeX backslashes (`\frac`, `\times`, `\text`) to collide with JSON escape sequences — `\f` is parsed as form feed, `\t` as tab, silently corrupting math content. A secondary failure mode produces literal ` ```json{...}``` ` as rendered text when the JSON fails to parse. Both failures are structural: you cannot reliably encode LaTeX inside JSON strings without a character-level arms race.

## What Changes

- Replace the current `{"reply": "...", ...}` single-JSON-blob format with a tag-delimited format that keeps the reply body outside of JSON encoding entirely.
- The new format wraps the markdown reply in `<REPLY>...</REPLY>` and the small metadata blob in `<META>{...}</META>`.
- Implement a multi-stage fallback parser: tagged → brace-scan boundary split → whole-text reply.
- Update system prompts (`_JSON_SYNTHESIS_INSTRUCTION`, `_AGENTIC_JSON_FINAL_INSTRUCTION`) to instruct the LLM to emit the new format.
- Remove the character-level `_repair_json_string_escapes` logic that was compensating for the old format's fragility.
- Stream the reply section directly to the client; buffer only the small `<META>` tail.

## Capabilities

### New Capabilities
- `chat-reply-tag-format`: Tag-delimited LLM response format with robust multi-stage fallback parsing that eliminates LaTeX corruption and JSON fence bleed-through.

### Modified Capabilities
- `follow-up-generation`: Follow-up questions now arrive in `<META>` rather than the top-level JSON `follow_ups` key — same data, different envelope.
- `clarification-request`: Clarifying question field moves to `<META>` — same behavior, new format.
- `chat-message-summary`: Summary field moves to `<META>` — same behavior, new format.

## Impact

- `api/llm.py`: System prompt constants, `_parse_synthesis_json`, `_extract_synthesis_obj`, `_repair_json_string_escapes` (removal/simplification).
- `api/chat.py`: Response parsing call site — no schema change, same fields returned to frontend.
- Frontend (`src/ChatTab.jsx`): No change — still receives plain markdown string, renders with `ReactMarkdown` + `rehype-katex`.
- No database schema change — the stored `content` field remains a plain markdown string.
