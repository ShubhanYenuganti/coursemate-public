## MODIFIED Requirements

### Requirement: LLM synthesis returns reply and summary
The system SHALL instruct the model to return a tag-delimited response where the reply body is in `<REPLY>…</REPLY>` (plain markdown) and the `<META>` block contains a JSON object with string fields `summary` (a concise phrase capturing keywords/concepts, about 5–6 words) and `follow_ups`. The system SHALL parse the META block after synthesis, extract `summary`, and cap its length for storage.

#### Scenario: Successful parse persists both fields
- **WHEN** synthesis returns a well-formed tagged response with a parseable `<META>` block containing `summary`
- **THEN** the stored assistant `content` SHALL equal the reply body from `<REPLY>`
- **THEN** the stored assistant `summary` SHALL equal the trimmed summary (after cap)

#### Scenario: META parse failure still stores answer
- **WHEN** the `<META>` block is absent or unparseable
- **THEN** the system SHALL store the reply body as `content` and SHALL set `summary` to null
