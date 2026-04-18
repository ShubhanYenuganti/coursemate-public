## ADDED Requirements

### Requirement: Send handler detects pending clarification and routes to R2 path
The system SHALL check the previous assistant message before calling `synthesize()`. If the previous assistant message has `is_clarification_request = TRUE` and `clarification_skipped = FALSE`, the send handler SHALL route to `synthesize_with_clarification()` instead of the normal `synthesize()` path.

#### Scenario: Pending clarification routes to R2 synthesis
- **WHEN** the user sends a message and the last assistant message in the chat has `is_clarification_request = TRUE` and `clarification_skipped = FALSE`
- **THEN** the backend calls `synthesize_with_clarification()` with the original prompt, R1 content, clarification question, and current user message

#### Scenario: No pending clarification routes normally
- **WHEN** the user sends a message and the last assistant message has `is_clarification_request = FALSE` or `clarification_skipped = TRUE`
- **THEN** the backend calls `synthesize()` normally

#### Scenario: Skipped clarification does not trigger R2
- **WHEN** the user sends a message after clicking Skip Clarification
- **THEN** the backend calls `synthesize()` normally, not `synthesize_with_clarification()`

### Requirement: R2 synthesis uses a structured clarification context bundle
The system SHALL implement `synthesize_with_clarification()` that constructs a purpose-built context prompt containing: the original user prompt, R1 (the prior assistant answer), the clarifying question, and the user's clarification response. This function SHALL instruct the model to produce a complete, cohesive final answer informed by all four inputs. R2 SHALL pass through both agentic and non-agentic paths.

#### Scenario: R2 context bundle includes all four inputs
- **WHEN** `synthesize_with_clarification()` is called
- **THEN** the LLM receives a prompt that includes the original question, R1, the clarifying question asked, and the user's clarification in a structured format

#### Scenario: R2 includes follow_ups
- **WHEN** R2 synthesis completes
- **THEN** the assistant message includes a non-empty `follow_ups` array (the same JSON schema as a normal response)

#### Scenario: R2 clarifying_question respects depth cap
- **WHEN** R2 synthesis completes at `clarification_depth < 2`
- **THEN** the assistant message may have `is_clarification_request = TRUE` if the model emitted a non-null `clarifying_question` — supporting up to 2 rounds of clarification
- **WHEN** R2 synthesis completes at `clarification_depth >= 2`
- **THEN** the assistant message has `is_clarification_request = FALSE` — the hard cap forces `clarifying_question = null` post-parse regardless of model output

#### Scenario: R2 stored as normal assistant message
- **WHEN** R2 synthesis completes
- **THEN** a normal `chat_messages` row is inserted with `role = assistant`, `is_clarification_request = FALSE`, and the refined content as `content`

### Requirement: R2 applies to both send and stream actions
The system SHALL apply clarification routing in both the synchronous send action and the streaming send action of the chat handler.

#### Scenario: Stream send detects pending clarification
- **WHEN** the user sends a message via the streaming path and clarification is pending
- **THEN** the stream handler routes to `synthesize_with_clarification()` and streams R2

#### Scenario: Sync send detects pending clarification
- **WHEN** the user sends a message via the synchronous send path and clarification is pending
- **THEN** the sync handler routes to `synthesize_with_clarification()` and returns R2
