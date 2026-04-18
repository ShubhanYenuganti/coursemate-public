## Purpose

TBD — Defines the LLM schema extension, database persistence, and UI rendering for the clarification request flow, where the assistant may ask a focused follow-up question when it has made significant assumptions about the user's intent.

## Requirements

### Requirement: LLM JSON schema includes optional clarifying_question field
The system SHALL extend the LLM response schema to include an optional `clarifying_question` field (string or null) in the `<META>` JSON block of the tag-delimited response format. Both the agentic and non-agentic system prompts SHALL instruct the model to emit this field in `<META>` when it has made significant assumptions about the user's intent, and null otherwise.

#### Scenario: Model emits clarifying_question when assumptions are significant
- **WHEN** the LLM determines it has made one or more significant assumptions to answer the prompt
- **THEN** the `<META>` block contains `clarifying_question` set to a single focused question string

#### Scenario: Model emits null when no significant assumptions
- **WHEN** the LLM can answer the prompt without significant assumptions
- **THEN** the `<META>` block contains `clarifying_question: null`

#### Scenario: Parser extracts clarifying_question alongside existing fields
- **WHEN** `_parse_synthesis_json` processes a response containing `clarifying_question` in `<META>`
- **THEN** the parsed result includes the clarifying_question value alongside reply, summary, and follow_ups

### Requirement: Assistant message persists clarification state
The system SHALL store clarification state in three new columns on `chat_messages`: `clarification_question TEXT`, `is_clarification_request BOOL DEFAULT FALSE`, `clarification_skipped BOOL DEFAULT FALSE`.

#### Scenario: New message with clarifying_question persists state
- **WHEN** the LLM response includes a non-null `clarifying_question`
- **THEN** the inserted `chat_messages` row has `clarification_question` set to the question text and `is_clarification_request = TRUE`

#### Scenario: New message without clarifying_question persists defaults
- **WHEN** the LLM response includes `clarifying_question: null`
- **THEN** the inserted row has `is_clarification_request = FALSE` and `clarification_skipped = FALSE`

### Requirement: Assistant message with pending clarification renders Q block
The system SHALL render the clarifying question as a distinct block below R1 when `is_clarification_request = TRUE` and `clarification_skipped = FALSE`. The block SHALL display the question text and a Skip Clarification button. Follow-up chips SHALL be hidden in this state.

#### Scenario: Q block renders below R1
- **WHEN** an assistant message has `is_clarification_request = TRUE` and `clarification_skipped = FALSE`
- **THEN** the message body (R1) is shown, followed by a visually distinct clarifying question block containing the question text and a Skip Clarification button

#### Scenario: Follow-up chips hidden while pending
- **WHEN** an assistant message has `is_clarification_request = TRUE` and `clarification_skipped = FALSE`
- **THEN** no follow-up chips are rendered, even if `follow_ups` is non-empty

#### Scenario: Pending state persists on page reload
- **WHEN** the user reloads the page and the last assistant message has `is_clarification_request = TRUE, clarification_skipped = FALSE`
- **THEN** the Q block and Skip button are still visible; follow-up chips are still hidden

### Requirement: Skip Clarification resolves the pending state
The system SHALL mark the clarification as skipped when the user clicks the Skip Clarification button, persisting `clarification_skipped = TRUE` to the backend and transitioning the UI to show follow-up chips with a contextual header.

#### Scenario: Skip persists to backend
- **WHEN** the user clicks Skip Clarification
- **THEN** a POST request with `action: clarification_skip` is sent to mark `clarification_skipped = TRUE` for that message

#### Scenario: Skip reveals follow-up chips with header
- **WHEN** the Skip POST succeeds
- **THEN** the Q block disappears and follow-up chips are displayed with the label "Would you like to discuss any of these further?" above them

#### Scenario: Skip state persists on page reload
- **WHEN** the user reloads after clicking Skip
- **THEN** the Q block is gone and follow-up chips with the label are visible
