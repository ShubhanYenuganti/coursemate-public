## Context

Chat responses from LLMs are currently returned as a single JSON object:
```json
{"reply": "...markdown...", "summary": "...", "follow_ups": [...], "clarifying_question": null}
```

The `reply` field embeds raw markdown — including LaTeX — inside a JSON string value. JSON uses `\` as its escape prefix; so does LaTeX. The LLM must double every LaTeX backslash (`\frac` → `\\frac` in JSON), and it is inconsistently reliable at this. The JSON spec treats `\f`, `\t`, `\b` as valid escape sequences (form feed, tab, backspace), so `\frac` silently becomes a form feed + `rac` even when the JSON is otherwise valid. A character-level repair function (`_repair_json_string_escapes`) attempts to compensate but cannot distinguish intentional `\n` (newline) from LaTeX `\nu` or `\nabla`. A second failure mode: when JSON parse fails entirely, the raw ` ```json{...}``` ` string falls through as the reply and is rendered as literal code fence text.

## Goals / Non-Goals

**Goals:**
- Eliminate LaTeX backslash corruption by never JSON-encoding the reply body.
- Eliminate code-fence bleed-through by removing the JSON-as-single-blob requirement.
- Implement a robust multi-stage fallback that degrades gracefully when the model doesn't follow format exactly.
- Keep the frontend unchanged — it still receives a plain markdown string.
- Keep the database schema unchanged — stored content remains plain markdown.

**Non-Goals:**
- Changing streaming architecture beyond buffering the small `<META>` tail.
- Supporting multiple LLM providers differently — same format applies to all.
- Changing how `follow_ups`, `clarifying_question`, or `summary` are used downstream.

## Decisions

### D1: Tag-delimited format with JSON only for metadata

**Decision**: The new format is:
```
<REPLY>
...plain markdown, LaTeX untouched...
</REPLY>
<META>{"summary": "...", "follow_ups": [...], "clarifying_question": null}</META>
```

**Rationale**: The reply body is never JSON-encoded. Backslashes in LaTeX pass through verbatim. The `<META>` JSON is small, contains no math, and has near-zero parse failure risk. Tags are unambiguous delimiters that don't appear in educational content.

**Alternatives considered**:
- *Keep JSON, use Structured Outputs (OpenAI)*: Guarantees valid JSON syntax but doesn't solve backslash collision — model still needs to double-escape LaTeX in the string value.
- *Two-pass (reply first, metadata separate LLM call)*: Eliminates collision entirely but doubles latency and cost.
- *Delimiter strings (===REPLY===)*: Equivalent, but XML-style tags are more visually distinct and less likely to appear in code samples.

---

### D2: Three-stage fallback parser

**Decision**: Parse in this order:

1. **Tagged**: find `<REPLY>…</REPLY>` and `<META>…</META>` via regex.
2. **Brace-boundary split**: `rfind('}')` + backward brace walk to find the last balanced JSON object; validate it has `summary` or `follow_ups`; everything before it is the reply.
3. **Whole-text**: treat the entire output as the reply, metadata fields empty.

**Rationale**: Stage 2 handles the common case where the model emits the right content but forgets the tags — the metadata JSON is always at the end. Stage 3 ensures something is always shown. No fallback can produce corrupted LaTeX because the reply body is never decoded from JSON in any stage.

**Alternatives considered**:
- *Fail hard on no tags*: Would surface errors to users on model non-compliance.
- *Attempt old JSON parse as stage 4*: Would re-introduce the corruption risk; excluded intentionally.

---

### D3: Remove `_repair_json_string_escapes`

**Decision**: Delete the character-level JSON repair function entirely once the new format is deployed.

**Rationale**: It was compensating for a structural problem now solved. Keeping it adds complexity and false confidence.

---

### D4: Buffer `<META>` tail during streaming, stream `<REPLY>` directly

**Decision**: Stream tokens within `<REPLY>…</REPLY>` to the client immediately. Buffer from `</REPLY>` onward to extract and parse `<META>`.

**Rationale**: The reply is the large, latency-sensitive part. The `<META>` block is ~100 tokens and arrives last. Buffering only the tail preserves the current streaming UX.

## Risks / Trade-offs

- **Model compliance**: The model may not always emit the tags correctly. → Mitigated by the three-stage fallback; worst case is missing metadata (no summary/follow_ups), not corrupted content.
- **`<REPLY>` in content**: If a model response contains the literal string `<REPLY>` or `</REPLY>` (e.g., explaining the tag format), the regex could mis-parse. → Low probability in educational content; can be addressed with a unique sentinel if it becomes an issue (e.g., `<|REPLY|>`).
- **`\n` vs `\nu` in `<META>` JSON**: `summary` and `follow_ups` are plain prose — no LaTeX — so the JSON escape collision doesn't apply to the metadata blob.
- **Old stored messages**: Messages stored before this change are plain markdown already (the reply field was always extracted before storage). No migration needed.

## Migration Plan

1. Update system prompts — the model immediately starts emitting the new format.
2. Deploy updated `_parse_synthesis_json` with three-stage fallback.
3. The fallback's brace-boundary stage handles any in-flight requests still using the old format during rollout.
4. **Rollback**: Revert prompt constants and parser to previous version — no data migration required.

## Open Questions

- Should the unique sentinel (`<|REPLY|>`) be used from the start to prevent the edge case in Risk 2, at the cost of slightly more unusual prompt text?
