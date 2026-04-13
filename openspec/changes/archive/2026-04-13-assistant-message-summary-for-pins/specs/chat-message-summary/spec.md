## ADDED Requirements

### Requirement: chat_messages.summary column

The system SHALL add a nullable `summary` column on `chat_messages` for storing a short phrase (typically 5–6 words) produced by the LLM alongside the assistant reply. User and system rows SHALL leave `summary` null.

#### Scenario: Migration adds column

- **WHEN** the migration runs on an existing database
- **THEN** `chat_messages.summary` SHALL exist and be nullable

#### Scenario: Fresh init_db includes column

- **WHEN** `init_db()` runs on a new database
- **THEN** `chat_messages` SHALL be created with a `summary` column consistent with the migration

### Requirement: LLM synthesis returns reply and summary

The system SHALL instruct the model to return a single JSON object with string fields `reply` (full markdown answer per existing formatting rules) and `summary` (a concise phrase capturing keywords/concepts, about 5–6 words). The system SHALL parse this JSON after synthesis, extract `reply` and `summary`, normalize markdown on `reply`, and cap `summary` length for storage.

#### Scenario: Successful parse persists both fields

- **WHEN** synthesis returns valid JSON with `reply` and `summary`
- **THEN** the stored assistant `content` SHALL equal the normalized `reply` text
- **THEN** the stored assistant `summary` SHALL equal the trimmed summary (after cap)

#### Scenario: Parse failure still stores answer

- **WHEN** the model output is not valid JSON or lacks `reply`
- **THEN** the system SHALL store the raw or best-effort body as `content` and MAY set `summary` to null

### Requirement: Assistant message writes include summary

Every code path that inserts or replaces an assistant `chat_messages` row SHALL supply `summary` when available from synthesis (or null).

#### Scenario: Stream send persists summary

- **WHEN** a streamed chat exchange completes successfully
- **THEN** the inserted assistant row SHALL include `summary` from the parsed synthesis result when present

### Requirement: Message list API exposes summary

GET `resource=message` responses for chat messages SHALL include `summary` in each message object when selected from the database.

#### Scenario: Client receives summary for assistant messages

- **WHEN** the client loads messages for a chat
- **THEN** assistant message objects SHALL include a `summary` field (possibly null)

### Requirement: Pin list prefers assistant summary

GET `resource=pin` SHALL set each pin’s `ai_summary` string to the assistant message’s `summary` when present, otherwise fall back to the value stored in `pinned_messages.ai_summary`.

#### Scenario: Listed pin shows stored assistant summary

- **WHEN** a pin exists for an assistant message with a non-null `summary`
- **THEN** the pin’s `ai_summary` in the JSON response SHALL reflect that summary

### Requirement: Pin create does not trust client summary

POST `resource=pin` with `action=pin` SHALL set `pinned_messages.ai_summary` from the assistant `chat_messages.summary` (or empty), not from the request body’s `ai_summary`.

#### Scenario: Client omits ai_summary on pin

- **WHEN** the client pins without sending `ai_summary`
- **THEN** the server SHALL still insert the pin with `ai_summary` populated from the database when available

### Requirement: Frontend stops client-side truncation

The chat UI SHALL NOT derive pin preview text by taking the first five words of assistant content. It SHALL use summary from the message or pin API.

#### Scenario: Pin action does not send derived ai_summary

- **WHEN** the user pins an assistant message
- **THEN** the client SHALL not compute a summary from `content` for the pin request
