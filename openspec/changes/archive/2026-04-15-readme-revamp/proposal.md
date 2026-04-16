## Why

The project README contains only a title line — there is no documentation of what the application does, how its integrations work, or what its chat capabilities are. New contributors and stakeholders have no written reference. The integrations (Notion, Google Drive), the async Lambda poller, and the chat search system are architecturally non-trivial and deserve explanation.

## What Changes

- Replace the single-line `README.md` with a comprehensive document covering all major implemented capabilities
- Document the full Notion and Google Drive OAuth → Staging → Lambda Poller lifecycle with architecture diagrams
- Explain the dual-path EventBridge poller: background sweep (DB-derived work list) vs Sync Now (explicit external_ids)
- Explain the staleness check logic (`_needs_ingest`) used by both GDrive and Notion pollers
- Document the chat search system: empty-query recency list, FTS title matching, log-damped content matching, UI modal
- Document the Notion and Google Drive export system (reports, flashcards, quizzes; batch 207 API; sticky targets)
- Document the Pinned Responses feature and its LLM-generated summaries
- Document materials management: doc_type, progress panel, selection persistence, synced file deletion
- Include a short architecture/tech-stack overview section at the top

## Capabilities

### New Capabilities
<!-- None — this change produces documentation only, not new application behavior -->

### Modified Capabilities
<!-- None — no spec-level requirement changes -->

## Impact

- `README.md` — full rewrite
- No code, API, or database changes
- No new dependencies
