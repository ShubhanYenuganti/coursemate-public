## 1. Backend — LLM Generation

- [x] 1.1 Extend the system prompt instruction in `_build_layered_system_context` (and any provider-specific prompt builders) to instruct the LLM to include a `follow_ups` array of 2-3 questions in the JSON output
- [x] 1.2 Update `_parse_synthesis_json` to extract `follow_ups` from the parsed JSON object, defaulting to `[]` if the field is absent or not a list
- [x] 1.3 Expand `synthesize()` return value from 2-tuple `(content, summary)` to 3-tuple `(content, summary, follow_ups)`
- [x] 1.4 Update the `run_agent_openai` streaming path to accumulate and emit `follow_ups` from the final structured response

## 2. Backend — Chat Paths

- [x] 2.1 Update the `_send_message` path: unpack 3-tuple from `synthesize()`, include `follow_ups` in the assistant INSERT statement
- [x] 2.2 Update the `_stream_send_message` path: unpack 3-tuple, include `follow_ups` in INSERT
- [x] 2.3 Update the `_edit_message` path: unpack 3-tuple, include `follow_ups` in INSERT
- [x] 2.4 Update the `_regenerate_message` path: unpack 3-tuple, include `follow_ups` in INSERT
- [x] 2.5 Update the `_revert_message` path: read `follow_ups` from the original stored row (same pattern as `summary`), include in INSERT
- [x] 2.6 Update the `_restore_message` path: read `follow_ups` from the original stored row, include in INSERT

## 3. Backend — API Response

- [x] 3.1 Include `follow_ups` in the assistant message dict returned by the send/stream response payload in `chat.py`
- [x] 3.2 Include `follow_ups` in the message objects returned by `_list_or_search_messages` (conversation history load)

## 4. Frontend — Chip Rendering

- [x] 4.1 Identify where assistant message content is rendered in `ChatTab.jsx` (or a sub-component) and add a chip container below the message body
- [x] 4.2 Render each item in `follow_ups` as a styled chip (pill/outlined, indigo palette) when the array is non-empty
- [x] 4.3 Implement chip click handler: set the chat input value to the chip's question text and focus the input (no auto-submit)
- [x] 4.4 Verify chips do not render when `follow_ups` is empty or absent

## 5. Verification

- [x] 5.1 Send a test message and confirm the assistant reply includes 2-3 follow-up chips in the UI
- [x] 5.2 Click a chip and confirm the input is populated with the question text without submitting
- [x] 5.3 Load conversation history and confirm follow-up chips appear on previously stored messages that have `follow_ups` data
- [x] 5.4 Confirm revert/restore operations preserve follow-ups from the original message row
