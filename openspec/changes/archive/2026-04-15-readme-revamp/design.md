## Context

`README.md` currently contains only `# OneShotCourseMate`. The project has accumulated significant capability across three areas — integrations (Notion + GDrive OAuth, Lambda poller, exports), chat (search, pins, summaries), and materials management — none of which is documented. The full picture exists in `openspec/specs/` but specs are requirement contracts, not narrative explanations.

## Goals / Non-Goals

**Goals:**
- Single `README.md` that gives a complete feature picture to a new contributor or stakeholder in one read
- Explain the Notion and GDrive integration lifecycle end-to-end (OAuth → staging → Lambda poller) with architecture diagrams
- Explain the dual-trigger poller model (EventBridge sweep vs Sync Now) and the staleness check logic
- Explain the chat search system (empty-query recency mode, FTS title matching, log-damped content scoring)
- Cover exports, pinned responses, and materials management at summary depth

**Non-Goals:**
- API reference or endpoint catalogue
- Setup / local development instructions (those belong in a separate CONTRIBUTING or SETUP doc)
- Code-level implementation details (those live in specs and code comments)

## Decisions

### Decision: Section ordering follows user journey, not feature alphabetical order
**Rationale:** A reader landing on the README for the first time benefits from understanding the app concept → integrations (the most complex piece) → chat → materials. Alphabetical order (Chat, GDrive, Materials, Notion) breaks the conceptual arc. The integration lifecycle (OAuth → staging → Lambda → progress) is a linear flow and should be presented as one narrative section rather than split by provider.

**Alternative considered:** Split by provider (Notion section, GDrive section). Rejected — the OAuth, staging, and poller mechanics are nearly identical between providers; merging them avoids repetition and makes the shared design legible.

### Decision: Use ASCII diagrams for the poller's two trigger paths and the staleness check
**Rationale:** The dual-path poller (EventBridge vs Sync Now) and `_needs_ingest` decision tree are logic-heavy. Prose alone is hard to scan; a diagram makes the branching immediately visible. ASCII keeps the README renderable in any plain-text viewer without image hosting.

### Decision: Chat search section explains the SQL scoring logic in plain language
**Rationale:** The log-damped content ranking (`(1 + ln(hit_count)) × best_message_rank`) is a non-obvious design choice. Readers (including future contributors) need to understand why it exists (to prevent a chat with 50 weak hits from outranking one with 5 strong hits). A brief plain-language note with the formula is appropriate; the full SQL stays in the codebase.

### Decision: Export section covers all three content types in a single table, not individual subsections
**Rationale:** The export behavior is highly parallel across flashcards, quizzes, and reports (same batch API, same sticky-target mechanism, same 207 response shape). A comparison table communicates this more efficiently than three nearly-identical subsections.

### Decision: Pinned responses and chat summaries are a single subsection
**Rationale:** Pins and LLM-generated summaries are tightly coupled — summaries are generated at reply time specifically to power the PinsPanel preview. Separating them creates an artificial split.

## Risks / Trade-offs

- **Staleness risk:** The README will drift as the codebase evolves. Mitigation: keep each section grounded in the spec files it describes; when specs update, the README section is the obvious place to update.
- **Depth vs. length tension:** Covering every spec at full depth would produce a very long README. Mitigation: integrations get full narrative + diagrams; chat and materials get summary depth. Export system gets a table rather than individual subsections.

## Open Questions

- None — scope is clear.
