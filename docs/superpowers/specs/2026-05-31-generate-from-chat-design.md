# Generate-From-Chat — Design Spec

Date: 2026-05-31
Status: Approved (brainstorming complete; ready for implementation plan)
Category: New Feature (Partially-enabled by existing generation + agentic-loop infra)

## Summary

Let users trigger a quiz / flashcard / report generation directly from a chat
conversation. When a user makes a generation request in chat (e.g. "make me a
quiz about the TCP handshake"), the model proposes a generation inline as a
**Proposal Card**. The user can either **Build** it immediately (creates the
draft and queues the job, no modal) or **Refine** it (opens the existing
generation modal prefilled with the proposed values).

The generation is **conversation-grounded**: the generator receives both a
model-distilled summary of what was discussed *and* the chat's context
materials (hybrid source), so the output reflects the actual discussion rather
than only the source PDFs.

## Sequencing Dependency

This feature depends on the **PageIndex-for-Claude/Gemini agentic loop**
(roadmap priority #1). The proposal mechanism is an agentic tool, so it only
functions on providers that run the agentic loop. Until priority #1 ships,
`propose_generation` works on OpenAI only. This is consistent with the agreed
roadmap ordering and is not a blocker for building the feature behind that work.

## Goals

- A generation request in chat produces a conversational reply **plus** a
  Proposal Card describing the proposed generation.
- **Build** queues the generation with zero further input, bypassing the modal.
- **Refine** opens the normal generation modal prefilled with the proposed values.
- Generation output reflects the conversation (hybrid: distilled summary + materials).
- Defaults require no new generation pipeline — reuse the existing
  draft-create + `action=generate` (SQS enqueue) endpoints.

## Non-Goals (YAGNI)

- Auto-generating without an explicit Build/Refine click.
- Inline editing of the discussion summary on the card.
- Proposing multiple generations in a single turn.
- Multi-modal page retrieval changes to the generators.
- A dedicated `generate_from_chat` backend endpoint (we reuse existing endpoints).

## Architecture & Flow

```
User: "make me a quiz about the TCP handshake"
   │
   ▼ agentic loop (all 3 providers once priority #1 lands; OpenAI before then)
Model calls propose_generation(
   type            = "quiz",
   title           = "TCP Handshake Quiz",
   discussion_summary = "We covered SYN / SYN-ACK / ACK, sequence numbers, ...",
   material_ids    = [chat.context_material_ids],   # default
   counts          = { tf: 3, sa: 2, la: 1 })       # model-proposed; modal defaults if omitted
   │
   ▼ assistant streams BOTH:
   • a short conversational reply
   • a `generation_proposal` SSE event → rendered as a Proposal Card
   │
   ├── [Build]  → create draft (prefilled values + conversation_context + provider=chat's)
   │              → action=generate → SQS enqueue → toast "Quiz queued". No modal.
   │
   └── [Refine] → open existing quiz/flashcard/report modal, prefilled with proposed
                  values (incl. conversation_context passthrough) → normal generate flow.
```

### `propose_generation` tool

- Registered once in the `api/llm.py` tool list and surfaced in each provider's
  tool format (OpenAI function-calling, Anthropic `tool_use`, Gemini
  `functionDeclarations`). The shared registration is the reason priority #1
  (all-providers agentic loop) lands first.
- **The tool does not generate and has no side effects.** Its "execution"
  produces a structured proposal object that is forwarded to the client as a
  `generation_proposal` SSE event. It is a "render this card" tool.
- Tool arguments:
  - `type`: `"quiz" | "flashcards" | "report"`
  - `title`: short human-readable title
  - `discussion_summary`: concise distillation of the relevant conversation,
    authored by the model (which already holds the conversation in context).
    Bounded in size; doubles as the card's source-preview text.
  - `material_ids`: defaults to the chat's `context_material_ids` (the model
    may narrow, but default is the chat's selected materials).
  - `counts` / generation parameters: model-proposed; if omitted, each modal's
    existing defaults apply.
- After emitting the proposal event, the model also emits a brief conversational
  reply in the same turn.

### Build path

- Reuses the **existing** draft-create + `action=generate` endpoints. No new
  generation pipeline.
- The only backend addition is an optional `conversation_context` field
  (the `discussion_summary`) on the quiz / flashcard / report draft, threaded
  into the generator's context assembly so the source = summary + material chunks.
- Provider / model default to the chat's `ai_provider` / `ai_model`, carried in
  the proposal and persisted with the draft.

### Refine path

- Opens the existing generation modal (`Quiz.jsx` / `Flashcards.jsx` /
  `Reports.jsx`) prefilled from the proposal, including `conversation_context`
  as a passthrough so a refined-then-generated job is still conversation-grounded.

## Data & Contract Changes

- **No new endpoints.** Add optional `conversation_context: str | null` to the
  draft-create request bodies for quiz, flashcards, and report generation.
- Persist `conversation_context` on the generation draft record (one nullable
  text column per generation table, or reuse an existing settings/JSON column if
  present — to be confirmed in the implementation plan).
- Thread `conversation_context` into the generator's material-context assembly
  (e.g. alongside `_fetch_material_context`) so it is prepended/merged as source.
- New SSE event type `generation_proposal` carrying the proposal object for the UI.

## Defaults (approved)

- **Materials** = the chat's `context_material_ids`. If the chat has no materials
  selected, the generation runs **conversation-only** (summary as sole source)
  rather than blocking.
- **Counts / difficulty** = model-proposed; fall back to each modal's existing
  defaults when omitted.
- **Scope** = all three generation types (quiz, flashcards, report).
- **Provider/model** = the chat's selected provider/model.
- **Build** reuses existing endpoints (no dedicated `generate_from_chat` endpoint).

## Acceptance Criteria

- Asking "make me a quiz about X" in chat (on a provider with the agentic loop)
  streams a conversational reply and a Proposal Card showing type, title,
  question counts, and the source materials/conversation.
- Clicking **Build** creates and enqueues the generation with the chat's provider,
  shows a queued confirmation, and produces a generation whose content reflects
  the discussion summary plus the context materials.
- Clicking **Refine** opens the corresponding modal prefilled with the proposed
  values; generating from the modal yields the same conversation-grounded result.
- With no materials selected in the chat, Build still succeeds using the
  conversation summary as the sole source.
- Flashcards and reports follow the same Build/Refine behavior as quiz.

## Files Likely Touched

- `api/llm.py` — register `propose_generation`; emit `generation_proposal` SSE
  event; no tool-side generation.
- `api/quiz.py`, `api/flashcards*.py`, `api/reports.py` — accept optional
  `conversation_context` on draft create; thread into context assembly.
- `src/ChatTab.jsx` — render Proposal Card; wire Build (direct enqueue) and
  Refine (open modal prefilled).
- `src/Quiz.jsx`, `src/Flashcards.jsx`, `src/Reports.jsx` — accept prefilled
  values + `conversation_context` passthrough.

## Risks / Open Items

- **Depends on priority #1** (all-providers agentic loop). OpenAI-only until then.
- Confirm the storage location for `conversation_context` (new column vs. existing
  JSON settings field) per generation table during implementation planning.
- Token budget: `discussion_summary` must be bounded so the generator's combined
  context (summary + material chunks) stays within model limits.
- Source attribution: a conversation-grounded generation has no page citations for
  the summary-derived content; ensure the viewer doesn't imply false citations.

## Verification Plan

- Chat with 2 materials selected → "make me a quiz about <topic>" → Proposal Card
  shows 2 materials → Build → quiz queued and produced, reflecting the discussion.
- Refine path: same request → Refine → modal prefilled → adjust counts → generate.
- No-materials chat → Build → conversation-only quiz produced.
- Repeat for flashcards and report types.
