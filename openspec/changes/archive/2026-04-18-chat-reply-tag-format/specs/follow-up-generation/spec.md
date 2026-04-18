## MODIFIED Requirements

### Requirement: LLM generates follow-up questions with every reply
The system SHALL generate 2-3 follow-up questions alongside every assistant reply. Follow-up questions SHALL be produced in the same LLM call as the main reply by including them in the `<META>` JSON block of the tag-delimited response format. The system SHALL NOT make a separate API call to generate follow-ups.

#### Scenario: Standard reply includes follow-ups
- **WHEN** the LLM produces a reply
- **THEN** the `<META>` block contains a `follow_ups` array with 2-3 question strings

#### Scenario: Malformed or missing follow_ups field
- **WHEN** the LLM response is missing the `follow_ups` field in `<META>` or the META block cannot be parsed
- **THEN** `follow_ups` defaults to an empty list `[]` and the reply is not failed

#### Scenario: Follow-ups are topically relevant
- **WHEN** the LLM generates follow-up questions
- **THEN** each question is a natural next step or subtopic that extends the answer in the current reply
