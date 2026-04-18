## Purpose

Defines the frontend UI for displaying and interacting with follow-up question chips rendered below assistant messages.

## Requirements

### Requirement: Follow-up chips render below each assistant message
The system SHALL render follow-up questions as interactive chip elements below every assistant message that has a non-empty `follow_ups` array AND does not have a pending clarification (`is_clarification_request = TRUE` and `clarification_skipped = FALSE`). Chips SHALL NOT appear on messages with an empty `follow_ups` array. When a clarification has been skipped (`clarification_skipped = TRUE`), chips SHALL render preceded by the header "Would you like to discuss any of these further?".

#### Scenario: Non-empty follow-ups render chips (no pending clarification)
- **WHEN** an assistant message has a `follow_ups` array with at least one item and `is_clarification_request = FALSE`
- **THEN** each item is displayed as a distinct chip element below the message content with no header

#### Scenario: Empty follow-ups renders nothing
- **WHEN** an assistant message has `follow_ups: []` or the field is absent
- **THEN** no chip container or empty state is rendered below the message

#### Scenario: Chips display full question text
- **WHEN** a follow-up chip is rendered
- **THEN** the chip displays the full text of the follow-up question without truncation

#### Scenario: Follow-up chips hidden while clarification is pending
- **WHEN** an assistant message has `is_clarification_request = TRUE` and `clarification_skipped = FALSE`
- **THEN** no follow-up chips are rendered, even if `follow_ups` is non-empty

#### Scenario: Follow-up chips revealed with header after Skip
- **WHEN** an assistant message has `is_clarification_request = TRUE` and `clarification_skipped = TRUE`
- **THEN** the header "Would you like to discuss any of these further?" is rendered above the follow-up chips

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
