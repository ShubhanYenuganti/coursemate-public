## 1. LLM Schema & Parsing

- [x] 1.1 Add `clarifying_question` field instruction to `AGENTIC_JSON_FINAL_INSTRUCTION` in `api/llm.py` — depth-0 wording: "Only emit `clarifying_question` if you cannot provide a useful answer without knowing this. Most prompts should have `clarifying_question: null`."
- [x] 1.2 Add `clarifying_question` field instruction to `_SYNTHESIS_JSON_FINAL_INSTRUCTION` (non-agentic path) with the same depth-0 wording
- [x] 1.3 Update `_parse_synthesis_json` to extract `clarifying_question` from the JSON object and return it as a 4th element of the tuple
- [x] 1.4 Update all call sites of `_parse_synthesis_json` and `run_agent_openai` / `synthesize` to handle the new 4th return value

## 2. Clarification Synthesis Path

- [x] 2.1 Implement `synthesize_with_clarification(conn, user_id, original_prompt, prior_reply, clarifying_question, user_clarification, clarification_depth, ...)` in `api/llm.py` — constructs structured context bundle and calls the LLM for the next refined answer
- [x] 2.2 Inject depth-aware prompt pressure into `synthesize_with_clarification`: depth 1 uses stricter language ("only ask another if the answer would be fundamentally different... prefer null")
- [x] 2.3 After parsing the model output in `synthesize_with_clarification`, hard-cap: if `clarification_depth >= 2`, force `clarifying_question = None` regardless of model output
- [x] 2.4 Ensure `synthesize_with_clarification` works for both agentic and non-agentic paths

## 3. Chat Send Handler Routing

- [x] 3.1 In `chat.py` `_send_message` (sync send action): query the last assistant message for `is_clarification_request`, `clarification_skipped`, and `clarification_depth` before calling `synthesize`; route to `synthesize_with_clarification` when clarification is pending
- [x] 3.2 In `chat.py` `_send_message` (stream send action): same clarification routing logic as 3.1
- [x] 3.3 Update the 4 synthesis INSERT statements (send sync, send stream, edit, regenerate) to include `clarification_question`, `is_clarification_request`, `clarification_skipped`, `clarification_depth` columns — set `clarification_depth = prior_depth + 1` when `clarifying_question` is non-null, else `0`

## 4. Skip Clarification Endpoint

- [x] 4.1 Add a `clarification_skip` action (or PATCH resource) in `chat.py` that sets `clarification_skipped = TRUE` for a given message ID, scoped to the authenticated user
- [x] 4.2 Return the updated message row in the response

## 5. Frontend — Clarification Request UI

- [x] 5.1 In `AssistantMessage` (`src/ChatTab.jsx`), add conditional rendering: when `msg.is_clarification_request && !msg.clarification_skipped`, render the Q block below R1 — visually distinct block with the question text and a Skip Clarification button
- [x] 5.2 Wire Skip button to call the skip endpoint (4.1) and update local message state (`clarification_skipped: true`)
- [x] 5.3 When `msg.is_clarification_request && !msg.clarification_skipped`, suppress follow-up chip rendering entirely

## 6. Frontend — Post-Skip Follow-Up Chips

- [x] 6.1 In `AssistantMessage`, when `msg.is_clarification_request && msg.clarification_skipped`, render follow-up chips preceded by the header "Would you like to discuss any of these further?"
- [x] 6.2 Verify normal (non-clarification) messages still render follow-up chips without the header

## 7. Verification

- [x] 7.1 Test: send an ambiguous prompt — confirm Q block appears below R1, chips hidden
- [x] 7.2 Test: click Skip — confirm Q block disappears, chips appear with header, page reload preserves state
- [ ] 7.3 Test: respond to clarifying question — confirm refined answer is generated with its own follow-up chips
- [ ] 7.4 Test: respond to round-1 clarification with still-ambiguous answer — confirm round-2 Q block appears (depth=2 permitted)
- [x] 7.5 Test: round-2 clarification response — confirm final answer has no Q block regardless of model output (hard cap enforced)
- [x] 7.6 Test: unambiguous prompt — confirm normal flow (no Q block, chips shown normally)
- [ ] 7.7 Test: send an "unrelated" message while clarification is pending — confirm synthesis is routed through clarification path and handles mixed context gracefully
