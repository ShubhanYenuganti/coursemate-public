# Multi-Turn Conversational Memory — Design

**Date:** 2026-06-09
**Status:** Design approved, pending spec review
**Scope:** Chat send path (`api/chat.py` → `api/llm.py`). Course-material RAG (PageIndex) is out of scope and must not regress.

## Problem

The chat send path is **single-turn**. `run_agent_pageindex` (`api/llm.py:1635`) builds the
provider payload as exactly `[{system}, {current user message}]` — prior conversation turns are
never replayed to the model. Continuity today comes only from three narrow, overlapping
mechanisms: the clarification bundle (`synthesize_with_clarification`), the layered-grounding
follow-up resolver (`_build_layered_system_context`), and prior-image recall
(`_recall_prior_chat_images`).

We want the synthesis model — and the retrieval agent — to condition on prior turns of the
conversation, within a token budget, and to consolidate the three ad-hoc mechanisms into one.

## Goal

The model sees the active-branch conversation history (verbatim) up to a token ceiling on every
send. Provider/model switches continue to work because each turn is independent and already
tagged with its generating model.

## Decisions (from brainstorming)

1. **Introduce genuine multi-turn memory** — replay prior turns, not a new RAG corpus.
2. **Chat-message retrieval stays separate from PageIndex.** The course-material indexer
   (page/document-shaped) is untouched. The natural primitive for chat recall is the existing
   `message_embedding` + ivfflat index — but it is **deferred** (see Tiers).
3. **v1 retrieval stays on `gpt-4o-mini`.** Making the user's model drive retrieval (which would
   require a provider-agnostic tool-calling refactor across old-GPT / Responses-API / Claude /
   Gemini) is a separate, later change.
4. **Active branch is linear** (verified): editing mutates the row in place and soft-deletes the
   tail; revert/regenerate is an undo/redo stack inside `reply_history`. Branches are never live
   sibling rows. `WHERE chat_id = ? AND is_deleted = FALSE ORDER BY message_index ASC` is the
   active branch. `message_index` has gaps after edits — order by it, never assume consecutive.
5. **Skip intent tags.** Embeddings already cover semantic matching; a closed intent vocabulary is
   YAGNI.
6. **No conversation-length telemetry exists** — so budget pressure is currently hypothetical.
7. **Hot tier only in v1.** Warm (summary-substitution) and retrieved (embedding recall of dropped
   turns) tiers are deferred behind real truncation data.

## What is stored vs. what is sent

These are different and must not be conflated.

**Stored per message (canonical record):** raw text, role, timestamp, generating model
(`ai_provider`/`ai_model`), 1–2 sentence `summary`, `message_embedding`, approximate token counts.
Write-time derived fields.

**Sent into the agent (v1, hot tier):** the **verbatim raw text** of prior active-branch turns
(`role` + `content`) within the token budget — `[system, …prior turns verbatim, current user]`.
**Not** the summary, embedding, or token counts.

The derived fields exist to feed the deferred tiers, not the v1 payload:
- `summary` → warm tier (deferred). Only assistant turns carry one today; user-turn summaries are
  not needed until warm tier exists.
- `message_embedding` → retrieved tier (deferred). Already written inline via
  `embed_text_via_lambda`; nothing in v1 sends it.
- token counts → consumed by the budget estimator to decide how many verbatim turns fit, and
  persisted for instrumentation. Metadata, never payload content.

## Architecture

### 1. History loader
New helper (in `api/chat.py` or a small module). Given `chat_id` and the current `message_index`,
returns prior turns oldest→newest:

```sql
SELECT role, content, summary, ai_provider, ai_model, image_s3_keys, message_index
FROM chat_messages
WHERE chat_id = %s AND is_deleted = FALSE AND message_index < %s
ORDER BY message_index ASC
```

Ignores `reply_history` blobs (undo state, not conversation).

### 2. Budget estimator
New, server-side (`api/llm.py`):
- `MODEL_CONTEXT_WINDOWS`: backend map of model id → context window. `src/modelCatalog.js` is
  frontend-only and carries no window data, so this is net-new.
- Token estimate via the existing chars≈tokens heuristic (`_char_cap_from_tokens` family) plus a
  per-provider multiplier and a safety margin (10–20%). No real tokenizer dependency — precision
  isn't worth it.
- `budget = window − system − response_reserve − current_user_message − safety_margin`.

### 3. History composer
Replaces the two-message construction in `run_agent_pageindex`. Produces
`[system, …prior turns verbatim, current user]`:
- Fill **newest-first**; when the running estimate exceeds budget, **drop oldest turns first**.
- Per-provider shaping reuses existing converters (`_messages_to_responses_input`, the
  Claude/Gemini message builders) — they already iterate a messages list.
- **Image de-dup:** prior images continue to come via `_recall_prior_chat_images`; a turn whose
  images are already recalled must not be double-injected when its text is in verbatim history.

### 4. Consolidate grounding / clarification
Verified call-site audit: the only **live** legacy memory mechanism is the clarification branch.
`_build_layered_system_context` and `_verify_grounding` have **zero call sites** — they are already
dead code and not part of the live path.
- `synthesize_with_clarification` (called at `chat.py:1007` and `chat.py:1249`) becomes redundant —
  history replay puts the original question, prior answer, and clarifying question directly in the
  model's view as normal history turns. Collapse both call sites into the plain `synthesize` path.
- **Preserve** the clarification **depth cap** (no further clarifying questions at depth ≥ 2) by
  threading `clarification_depth` into the agent and emitting it as a system instruction.
- `_build_layered_system_context` / `_verify_grounding`: out of scope — already unwired; leave as-is
  (removing dead code is a separate cleanup, not this feature).

### 5. Instrumentation
Populate the currently-dead `context_token_count` / `response_token_count` columns. Log turns
included, turns dropped, estimated history tokens. This data decides whether warm/retrieved tiers
are ever built.

## Out of scope (deferred)
- Warm tier (per-message summary substitution for older turns).
- Retrieved tier (embedding recall of dropped turns via `message_embedding`).
- Episode / cold summaries and topic-boundary detection.
- Per-message intent tags.
- User's selected model driving retrieval + provider-agnostic tool-calling refactor.

## Error handling / edges
- **Streaming:** composition happens before the SSE `on_event` loop; the tool-calling loop just
  gets a longer message prefix.
- **Two-model split:** history feeds both retrieval (gpt-4o-mini, 128K — ample) and synthesis.
- **Null embeddings:** irrelevant in v1 (retrieved tier deferred).
- **Auth:** per-user/per-provider API keys (`_get_api_key`) unchanged.
- **Gaps in `message_index`:** handled by ordering rather than arithmetic.

## Testing
- History loader: correct ordered active-branch turns; excludes `is_deleted`; ignores
  `reply_history`.
- Budget estimator: keeps all turns under ceiling; drops oldest-first when over.
- Composer: correct messages shape per provider; image de-dup holds.
- Clarification flow still works through the unified path; depth cap honored.
- Regression: existing PageIndex retrieval and citation tests stay green.
