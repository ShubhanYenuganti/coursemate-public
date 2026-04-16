## MODIFIED Requirements

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
