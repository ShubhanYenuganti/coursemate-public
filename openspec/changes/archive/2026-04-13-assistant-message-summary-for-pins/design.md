## Context

CourseMate synthesizes assistant replies via `synthesize()` in `api/llm.py` (non-agentic: Claude/OpenAI/Gemini; agentic: OpenAI tool loop in `run_agent_openai`). Today the return is a single markdown string. Pins store `ai_summary` from the client using the first five words of content. The plan moves summary generation to the model and stores it on `chat_messages`.

## Goals / Non-Goals

**Goals:**

- Single JSON shape `{ "reply": "<markdown>", "summary": "<5–6 words>" }` from synthesis, parsed server-side.
- Persist `summary` on every new/updated assistant message row.
- Pin list and pin insert derive display text from DB, not the browser.

**Non-Goals:**

- Backfilling summaries for historical assistant rows.
- Changing `pinned_messages` table shape (reuse `ai_summary` column as denormalized copy at pin time).

## Decisions

1. **JSON field names** — Use `reply` for the markdown body (avoids ambiguity with HTTP “content”) and `summary` for the short phrase. Instructions appended to system prompt: respond with valid JSON only (non-agentic with `response_format` where supported).

2. **OpenAI non-agentic** — Use `response_format: { "type": "json_object" }` on chat completions.

3. **Claude / Gemini** — No universal JSON mode in the same way; rely on prompt + `_parse_synthesis_json()` with fallback: if parse fails, treat full string as `reply` and `summary = None`.

4. **Agentic loop** — When the model returns a final message without tool calls, parse JSON from that message text; run `_verify_grounding` / `_normalize_llm_markdown` / repair on `reply` only. Emit SSE `text` with the markdown `reply` only.

5. **Pin API** — `_list_pins` exposes `ai_summary` as `COALESCE(am.summary, pm.ai_summary, '')` for backward compatibility. `_pin_message` reads `summary` from `chat_messages` for `assistant_message_id` and writes into `pinned_messages.ai_summary`.

6. **Length cap** — Truncate stored `summary` to 200 characters server-side to match reasonable UI and DB size.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Model emits invalid JSON | Log, fallback to raw text as `reply`, `summary` null |
| JSON breaks verifier expectations | Run verifier on parsed `reply` only |
| Extra tokens in prompt | Small fixed overhead per completion |

## Migration Plan

1. Deploy migration adding `chat_messages.summary` (nullable).
2. Deploy application code.
3. Rollback: revert app; column can remain unused.

## Open Questions

- None for initial ship; optional later: mini-model backfill for old rows.
