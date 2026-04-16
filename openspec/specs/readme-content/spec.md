## Purpose

Specifies what the project README.md must document — its structure, required sections, and the level of technical detail needed for each major feature area.

---

## Requirements

### Requirement: README contains a project overview section
The README SHALL open with a brief overview (2–3 paragraphs) describing what OneShotCourseMate is, its primary use case (AI-assisted study from course materials), and its technology stack (Python/React, PostgreSQL, AWS Lambda, EventBridge).

#### Scenario: Overview section is present
- **WHEN** a reader opens README.md
- **THEN** the first section SHALL describe the application's purpose and tech stack before any feature documentation

---

### Requirement: README documents the Notion and Google Drive OAuth connection flow
The README SHALL contain a subsection explaining the OAuth 2.0 connection process for both Notion and Google Drive, including: where connection is initiated (Profile page), the state-cookie CSRF guard, token storage in `user_integrations`, the GDrive SameSite cookie finalize path, GDrive auto-token-refresh (5-minute window), and how disconnection works.

#### Scenario: OAuth flow is explained end-to-end
- **WHEN** a reader consults the integrations section
- **THEN** they SHALL find a description of the full OAuth lifecycle from "Connect" click through token storage to disconnection, covering both providers

#### Scenario: GDrive-specific finalize path is called out
- **WHEN** the GDrive OAuth flow is described
- **THEN** the SameSite cookie redirect-and-finalize path SHALL be explicitly noted as a GDrive-specific behaviour

---

### Requirement: README documents the Sync Staging Modal flow
The README SHALL describe the integration staging step: selecting a source point for the first time opens a Sync Modal with per-file sync toggles (default ON), the user may toggle files off, and no database writes occur until the user clicks Sync. It SHALL also describe the Sync Now path (modal pre-populated from stored sync state).

#### Scenario: Staging flow is explained
- **WHEN** a reader consults the integrations section
- **THEN** they SHALL find an explanation that the staging modal is the human-in-the-loop step before async processing begins, and that `bulk_upsert_sync` persists sync state and doc_type per file

---

### Requirement: README documents the async Lambda poller with both trigger paths
The README SHALL contain a subsection explaining the EventBridge-triggered Lambda poller with an ASCII diagram showing the two invocation paths: (1) EventBridge background sweep — work list derived from `materials WHERE sync=TRUE`, no external API listing; (2) Sync Now — explicit `external_ids` passed in the Lambda event, bypasses DB query. It SHALL also explain the shared `_needs_ingest` staleness check logic with a decision table.

#### Scenario: Both trigger paths are documented
- **WHEN** a reader consults the Lambda poller subsection
- **THEN** they SHALL find a diagram or table distinguishing the EventBridge path from the Sync Now path, including how the work list is built in each case

#### Scenario: Staleness check logic is explained
- **WHEN** a reader consults the Lambda poller subsection
- **THEN** they SHALL find an explanation of `_needs_ingest`: returns True when api_time > db_time, when db_time is NULL (never ingested or prior failure), or on parse error; returns False only when api_time ≤ db_time

#### Scenario: Notion and GDrive ingestion pipelines are summarised
- **WHEN** a reader consults the Lambda poller subsection
- **THEN** the Notion pipeline (pages API → blocks → ReportLab PDF → S3 → embed) and GDrive pipeline (Drive modifiedTime → export/download → S3 → embed, with 50 MB guard) SHALL each be described briefly

---

### Requirement: README documents the export system
The README SHALL describe the ability to export generated flashcards, quizzes, and reports to Notion or Google Drive, including: the Notion block structure for each content type, the GDrive Google Docs creation, sticky export targets, and the batch 207 Multi-Status API shape.

#### Scenario: Export content types and block mappings are described
- **WHEN** a reader consults the exports subsection
- **THEN** they SHALL find a description of how each content type maps to Notion blocks (reports → heading_2/paragraph, quizzes → heading_2/bulleted_list_item/toggle answer, flashcards → toggle front/back) and Google Docs

#### Scenario: Batch API shape is noted
- **WHEN** a reader consults the exports subsection
- **THEN** the 207 Multi-Status envelope structure and partial-failure semantics SHALL be explained

---

### Requirement: README documents the chat search system
The README SHALL contain a section explaining chat search with two modes: (1) empty query — loads from in-memory chat state sorted by recency, no network request; (2) non-empty query — debounced 300 ms, FTS against chat titles (prefix matching, ts_rank × 3 boost) and message content (log-damped scoring: `(1 + ln(hit_count)) × best_message_rank`), results rendered in two labeled sections (TITLE MATCHES / IN CONVERSATION).

#### Scenario: Empty-query mode is explained
- **WHEN** a reader consults the chat search section
- **THEN** they SHALL find an explanation that the empty-query state reads from loaded state and performs no network request

#### Scenario: FTS ranking logic is explained
- **WHEN** a reader consults the chat search section
- **THEN** they SHALL find an explanation of title boosting (≥ 3× ts_rank) and log-damped content scoring with the formula `(1 + ln(hit_count)) × best_message_rank`, and why log-damping exists (prevents high hit-count chats from outranking high-relevance chats)

#### Scenario: UI behaviour is described
- **WHEN** a reader consults the chat search section
- **THEN** the modal trigger (search icon in sidebar), two-section result layout, ESC/backdrop dismissal, and click-to-navigate behaviour SHALL be described

---

### Requirement: README documents the pinned responses feature
The README SHALL describe the pin feature: pin icon on AI message bubbles, `pinned_messages` table (DB-persisted, not localStorage), LLM-generated 5–6 word summary stored in `chat_messages.summary` and used as the PinsPanel preview, expandable pin rows with user + AI bubbles, trash-icon deletion, and pin state preservation through message revert/restore.

#### Scenario: Pin storage mechanism is described
- **WHEN** a reader consults the pins section
- **THEN** they SHALL find a note that pins are persisted to the database (not localStorage) via `pinned_messages`, with ownership enforcement

#### Scenario: LLM summary generation is explained
- **WHEN** a reader consults the pins section
- **THEN** the README SHALL explain that the LLM returns a `summary` field alongside every reply, stored in `chat_messages.summary`, and used as the PinsPanel row preview

---

### Requirement: README documents materials management capabilities
The README SHALL briefly cover: `doc_type` per material (selected in staging modal, stored on the materials row), the Progress Panel (inline status surface showing Syncing → Queued → Indexing → Done, polling at 2 s during active jobs, dismissible), and synced file deletion behaviour.

#### Scenario: Progress Panel behaviour is described
- **WHEN** a reader consults the materials section
- **THEN** the status lifecycle (Syncing → Queued → Indexing → Done), the 2-second polling interval during active jobs, and the dismissible/auto-reopen behaviour SHALL be described
