## Purpose

Defines the frontend UI for displaying and interacting with follow-up question chips rendered below assistant messages.

## Requirements

### Requirement: Follow-up chips render below each assistant message
The system SHALL render follow-up questions as interactive chip elements below every assistant message that has a non-empty `follow_ups` array. Chips SHALL NOT appear on messages with an empty `follow_ups` array.

#### Scenario: Non-empty follow-ups render chips
- **WHEN** an assistant message has a `follow_ups` array with at least one item
- **THEN** each item is displayed as a distinct chip element below the message content

#### Scenario: Empty follow-ups renders nothing
- **WHEN** an assistant message has `follow_ups: []` or the field is absent
- **THEN** no chip container or empty state is rendered below the message

#### Scenario: Chips display full question text
- **WHEN** a follow-up chip is rendered
- **THEN** the chip displays the full text of the follow-up question without truncation

### Requirement: Clicking a chip loads the question into the chat input
The system SHALL populate the chat input field with the follow-up question text when a chip is clicked. The input SHALL receive focus after population. The message SHALL NOT be auto-submitted.

#### Scenario: Chip click populates input
- **WHEN** the user clicks a follow-up chip
- **THEN** the chat input field contains the chip's question text and the input is focused

#### Scenario: Chip click does not submit
- **WHEN** the user clicks a follow-up chip
- **THEN** no message is sent; the user must explicitly submit the input

#### Scenario: User can edit after chip click
- **WHEN** the user clicks a chip and the input is populated
- **THEN** the input is editable and the user can modify the text before sending

### Requirement: Chips are visually distinct from the message body
Chips SHALL be visually styled to indicate interactivity (e.g., outlined or pill-shaped) and SHALL be clearly separated from the assistant message text. The chip style SHALL be consistent with the existing Tailwind/indigo design language.

#### Scenario: Chips appear after message content
- **WHEN** follow-up chips are rendered
- **THEN** they appear below the message body with visible vertical separation
