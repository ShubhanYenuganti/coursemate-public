# chat-reply-tag-format Specification

## Purpose
Defines the tag-delimited response format used by the LLM synthesis layer, where the reply body is wrapped in `<REPLY>…</REPLY>` and metadata is wrapped in `<META>…</META>`. This format prevents backslash corruption of LaTeX and other special characters that occurred with JSON-encoded reply fields.

## Requirements

### Requirement: LLM responses use tag-delimited format
The system SHALL instruct the LLM to return responses in a tag-delimited format where the reply body is wrapped in `<REPLY>…</REPLY>` and metadata is wrapped in `<META>…</META>`. The reply body SHALL be plain markdown, never JSON-encoded. The `<META>` block SHALL contain a JSON object with `summary`, `follow_ups`, and `clarifying_question` fields.

#### Scenario: Well-formed tagged response is parsed correctly
- **WHEN** the LLM emits a response containing `<REPLY>…</REPLY>` and `<META>{…}</META>`
- **THEN** the parser extracts the content between the REPLY tags as the reply string and parses the META JSON for metadata fields

#### Scenario: LaTeX in reply passes through intact
- **WHEN** the reply body contains LaTeX expressions such as `$\frac{a}{b}$` or `\times`
- **THEN** the stored and returned reply string contains those expressions unchanged, with no backslash corruption

### Requirement: Three-stage fallback parser
The system SHALL implement a three-stage fallback in `_parse_synthesis_json`:

1. **Tagged**: extract content via `<REPLY>` and `<META>` regex.
2. **Brace-boundary split**: locate the last balanced JSON object in the text via `rfind('}')` plus backward brace walk; validate it contains `summary` or `follow_ups`; treat all text before it as the reply.
3. **Whole-text**: treat the entire output as the reply with empty metadata.

No fallback stage SHALL JSON-decode the reply body, ensuring LaTeX is never corrupted regardless of which stage handles the response.

#### Scenario: Missing tags, trailing metadata JSON
- **WHEN** the LLM omits tags but appends a valid metadata JSON object at the end of the response
- **THEN** the brace-boundary stage detects the JSON object, splits the text at its start, and returns the preceding text as the reply

#### Scenario: No tags and no metadata JSON
- **WHEN** the LLM emits only plain markdown with no tags and no trailing JSON
- **THEN** the whole-text stage returns the full output as the reply with `summary=None`, `follow_ups=[]`, `clarifying_question=None`

#### Scenario: Brace-scan candidate fails schema validation
- **WHEN** the trailing JSON object does not contain `summary` or `follow_ups` keys
- **THEN** the brace-boundary stage is skipped and the whole-text fallback is used

### Requirement: Reply body is streamed directly; META is buffered
The system SHALL stream tokens within `<REPLY>…</REPLY>` to the client immediately upon receipt. Tokens from `</REPLY>` onward SHALL be buffered server-side until the full `<META>` block is received and parsed.

#### Scenario: Streaming begins before META is received
- **WHEN** the LLM begins emitting the REPLY block
- **THEN** reply tokens are forwarded to the client without waiting for the META block to arrive

#### Scenario: META parse failure does not lose reply
- **WHEN** the `<META>` block is malformed or absent
- **THEN** the already-streamed reply is preserved and metadata fields default to empty values
