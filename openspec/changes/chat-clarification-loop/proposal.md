## Why

When a user sends an ambiguous prompt, the chat model makes implicit assumptions and returns an answer that may not match what the user actually needed — the user then has to re-ask, correct course, or accept a suboptimal response. A clarification loop catches significant assumption-making at the point of generation, asks one focused question, and uses the answer to produce a more cohesive final response.

## What Changes

- The LLM JSON response schema gains a new optional field: `clarifying_question` (`string | null`). When non-null, the model is signaling it made significant assumptions and wants clarification before the response is considered final.
- When `clarifying_question` is non-null: the assistant message renders both R1 (the initial answer) and the clarifying question below it; the normal follow-up chips are hidden.
- A **Skip Clarification** button on the clarifying question block dismisses it and reveals the follow-up chips with a "Would you like to discuss any of these further?" label.
- When the user sends any message while a clarification is pending (not yet skipped), the backend routes to a new **clarification synthesis path** that uses `(original_prompt, R1, clarifying_question, user_response)` as context to produce a refined final answer R2.
- R2 is a normal assistant message with its own follow-up chips.
- Skipping marks the clarification as resolved without triggering R2; any subsequent messages use the normal synthesis path.
- Both the agentic and non-agentic synthesis paths participate.

## Capabilities

### New Capabilities

- `clarification-request`: The assistant message state that holds a pending clarification question — includes the inline Q block, Skip affordance, and the DB fields that track pending/skipped status.
- `clarification-synthesis`: The backend synthesis path that constructs R2 from the clarification context bundle `(original_prompt, R1, clarifying_question, user_clarification)`.

### Modified Capabilities

- `follow-up-chips`: Follow-up chips are now conditionally hidden when a clarification is pending, and re-revealed (with a header label) after Skip is clicked.

## Impact

- **`api/llm.py`**: `AGENTIC_JSON_FINAL_INSTRUCTION` and `_SYNTHESIS_JSON_FINAL_INSTRUCTION` gain `clarifying_question` field; `_parse_synthesis_json` updated to extract it; new `synthesize_with_clarification()` function added.
- **`api/chat.py`**: `_send_message` checks the prior assistant message for a pending clarification before routing to `synthesize`; new `clarification_skipped` PATCH action added.
- **DB**: `chat_messages` gains three columns — `clarification_question TEXT`, `is_clarification_request BOOL DEFAULT FALSE`, `clarification_skipped BOOL DEFAULT FALSE`.
- **`src/ChatTab.jsx`**: `AssistantMessage` component gains conditional rendering for the Q block, Skip button, and the "Would you like to discuss any of these further?" chips header.
- No new external dependencies.
