## MODIFIED Requirements

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
