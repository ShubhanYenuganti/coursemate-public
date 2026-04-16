## ADDED Requirements

### Requirement: LLM generates follow-up questions with every reply
The system SHALL generate 2-3 follow-up questions alongside every assistant reply. Follow-up questions SHALL be produced in the same LLM call as the main reply by including them in the structured JSON output. The system SHALL NOT make a separate API call to generate follow-ups.

#### Scenario: Standard reply includes follow-ups
- **WHEN** the LLM produces a reply
- **THEN** the response JSON contains a `follow_ups` array with 2-3 question strings

#### Scenario: Malformed or missing follow_ups field
- **WHEN** the LLM response is missing the `follow_ups` field or it cannot be parsed
- **THEN** `follow_ups` defaults to an empty list `[]` and the reply is not failed

#### Scenario: Follow-ups are topically relevant
- **WHEN** the LLM generates follow-up questions
- **THEN** each question is a natural next step or subtopic that extends the answer in the current reply

### Requirement: Follow-up questions are persisted to the database
The system SHALL store follow-up questions in the `chat_messages` table in a `follow_ups` JSONB column. All six assistant-message INSERT paths (send, stream, edit, regenerate, revert, restore) SHALL write this field. Revert and restore paths SHALL copy `follow_ups` from the original stored row.

#### Scenario: Successful insert stores follow-ups
- **WHEN** an assistant message is inserted after synthesis
- **THEN** `chat_messages.follow_ups` contains the array returned by `synthesize()`

#### Scenario: Revert copies follow-ups from original row
- **WHEN** a revert or restore operation replays a stored assistant message
- **THEN** `follow_ups` written to the new row is read from the original message row, not re-generated

#### Scenario: Migration default for existing rows
- **WHEN** the `follow_ups` column is added via migration
- **THEN** all existing rows receive a default value of `[]`

### Requirement: Follow-up questions are returned in the message API response
The system SHALL include `follow_ups` in every assistant message payload returned by the chat API (both the send response and the message list endpoint).

#### Scenario: Send response includes follow-ups
- **WHEN** a user sends a message and receives an assistant reply
- **THEN** the API response payload for the assistant message contains a `follow_ups` array

#### Scenario: Message list includes follow-ups
- **WHEN** the frontend loads conversation history
- **THEN** each assistant message object contains a `follow_ups` array (possibly empty for older messages)
