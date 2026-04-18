## Context

The chat system currently produces a final answer in a single synthesis pass. The LLM already emits a JSON object (`{reply, summary, follow_ups}`) at the end of each turn. When the model makes significant assumptions to fill in ambiguity, those assumptions are baked silently into the reply — the user has no opportunity to correct course before seeing the answer.

The clarification loop introduces an optional multi-round refinement path: if the model decides it made significant assumptions, it surfaces a single clarifying question. The user responds (or skips), and the backend synthesizes a refined answer. That refined answer may itself ask a follow-up clarifying question, up to a hard cap of 2 rounds. After the cap, clarification is forced off regardless of model output.

Relevant code surfaces:
- `api/llm.py`: JSON schema (`AGENTIC_JSON_FINAL_INSTRUCTION`, `_SYNTHESIS_JSON_FINAL_INSTRUCTION`), `_parse_synthesis_json`, `run_agent_openai`, `synthesize`
- `api/chat.py`: `_send_message` (send, stream, edit paths), `_skip_clarification` (new)
- `src/ChatTab.jsx`: `AssistantMessage` component, follow-up chips rendering

## Goals / Non-Goals

**Goals:**
- Surface a clarifying question inline below R1 when the model flags significant assumptions
- Hide follow-up chips while clarification is pending; reveal them with a contextual header after Skip
- Route any user message sent while clarification is pending through a dedicated synthesis path
- Support up to 2 rounds of clarification per user message thread, with a hard cap enforced post-parse
- Use escalating prompt pressure per round to discourage unnecessary follow-up questions
- Persist clarification state (including depth) across page reloads (DB-backed)
- Apply to both agentic and non-agentic synthesis paths

**Non-Goals:**
- More than 2 clarification rounds (hard cap, not configurable per-request)
- Automatically detecting whether a user's response is "on-topic" for the clarification — any message while pending is treated as a clarification response
- Streaming clarification responses differently than a normal response
- Retroactively re-clarifying old messages

## Decisions

### D1: Inline JSON field, not a second LLM call

**Decision**: Add `clarifying_question: string | null` to the existing JSON schema rather than running a separate post-hoc assessment call.

**Rationale**: The model already knows at generation time what assumptions it's making. A second call would add latency and cost for every message, and the model is well-positioned to self-report ambiguity in the same pass. This is zero-cost when no clarification is needed.

**Alternative considered**: Post-hoc classification call ("did you make assumptions?"). Rejected — extra latency always, redundant reasoning.

### D2: R1 is shown to the user alongside the clarifying question

**Decision**: Display R1 as a normal assistant response with the clarifying question block appended below. Follow-up chips are hidden while clarification is pending.

**Rationale**: R1 is a genuine best-effort answer. Hiding it entirely would frustrate users who wanted an immediate answer. Showing it alongside Q gives them the answer AND an upgrade path. If they click Skip, follow-up chips surface with a contextual header.

**Alternative considered**: Hide R1, show only Q. Rejected — user gets no value until they clarify.

### D3: Clarification state read from the prior assistant message (not the user message)

**Decision**: In `_send_message`, check whether the previous assistant message has `is_clarification_request=true AND clarification_skipped=false` to decide routing. No new field on the user message row.

**Rationale**: Keeps the routing decision co-located with the clarification state. User messages remain semantically clean. The prior message is always available in the send handler.

### D4: Any message while pending → clarification synthesis path (intent-naive)

**Decision**: Any user message sent while a clarification is pending is routed to the clarification synthesis path. No attempt to detect whether the message is "really" answering the clarification question.

**Rationale**: Explicit Skip is available for users who want to abandon. The LLM has full context (original prompt, prior Rn, Q, user message) and can handle an off-topic user message gracefully. Eliminates the hard intent-detection problem entirely.

### D5: Clarification synthesis uses a structured context bundle, not history replay

**Decision**: `synthesize_with_clarification()` constructs a purpose-built prompt bundle — `{original_prompt, prior_reply, clarifying_question, user_clarification, clarification_depth}` — injected into a special system instruction, rather than replaying raw multi-turn history.

**Rationale**: The raw history contains the LLM's JSON output (including `clarifying_question` field text) which would be confusing to replay verbatim. A clean context bundle gives the model a clear "here's what you said, here's the clarification, now write the best possible answer" framing. `clarification_depth` is included so prompt pressure can be applied correctly.

### D6: Skip action persisted to DB

**Decision**: Clicking Skip fires a PATCH to update `clarification_skipped=true` on the assistant message, not a client-side-only state toggle.

**Rationale**: On page reload, the chat must reflect the correct state — showing follow-up chips with label, not the Q block with Skip button. Ephemeral client state would cause an inconsistent reload experience.

### D7: Multi-round clarification with hard cap of 2 and escalating prompt pressure

**Decision**: Allow up to 2 rounds of clarification. A `clarification_depth` column (`INT DEFAULT 0`) on `chat_messages` tracks how deep the current clarification chain is. Two complementary mechanisms prevent over-triggering:

1. **Hard cap (deterministic)**: After parsing the model's JSON output, if `clarification_depth >= 2`, `clarifying_question` is forced to `null` before persisting — regardless of what the model emitted. The model cannot override this.

2. **Escalating prompt pressure (behavioral)**: The synthesis prompt instruction varies by depth:
   - Depth 0: *"Only emit `clarifying_question` if you cannot provide a useful answer without knowing this. Most prompts should have `clarifying_question: null`."*
   - Depth 1: *"You have already asked one clarifying question. Only ask another if the answer would be fundamentally different across possible interpretations and you have no reasonable default. Prefer `null`."*
   - Depth ≥ 2: `clarifying_question` is forced `null` post-parse; no instruction emitted.

When a clarification response produces a new clarification request, `clarification_depth` increments: the new assistant message gets `clarification_depth = prior_depth + 1`.

**Rationale**: Prompt pressure alone is not reliable — LLMs drift toward thoroughness over time. The hard cap is a deterministic backstop that makes the worst-case bounded. Escalating language reduces unnecessary round 2 questions without requiring the cap to do all the work.

**Alternative considered**: Per-user preference ("ask once", "always ask", "never ask"). Rejected — adds UI complexity, doesn't address the core over-triggering problem, and the cap already handles the worst case.

## Risks / Trade-offs

- **Model over-triggering clarification at depth 0** → Mitigation: Strong prompt language ("most prompts should have null"). Degrades gracefully — worst case is 2 clarification rounds before hard cap.
- **Model never triggering clarification** → Mitigation: Monitor via logging; feature degrades gracefully to normal flow with no user impact.
- **Clarification synthesis awkwardly addresses an unrelated user message** → Accepted trade-off per D4. The model handles it gracefully in practice.
- **Skip adds a round-trip** → Acceptable; Skip is an explicit user action, not a hot path.
- **Clarification chain depth miscounted** → Mitigation: `clarification_depth` is written at INSERT time and read directly — no runtime chain-walking.

## Migration Plan

1. DB migrations already applied: `clarification_question TEXT`, `is_clarification_request BOOL DEFAULT FALSE`, `clarification_skipped BOOL DEFAULT FALSE`, `clarification_depth INT DEFAULT 0` on `chat_messages`.
2. Deploy backend changes (schema update, new synthesis path, Skip endpoint, depth tracking). Existing messages with columns at default values behave identically to before.
3. Deploy frontend changes. Existing messages without `is_clarification_request` render normally.

Rollback: remove frontend conditional rendering; backend falls back to normal synthesis path (redeploy prior backend).

## Open Questions

- Should `clarifying_question` be included in `follow_ups` fields for the non-agentic path, or only the agentic path? (Proposal says both — confirm implementation complexity is acceptable.)
