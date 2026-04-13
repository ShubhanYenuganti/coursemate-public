## ADDED Requirements

### Requirement: Pin icon replaces thumbs up and thumbs down
The system SHALL replace the thumbs-up and thumbs-down buttons on every AI `MessageBubble` with a single pin icon button. The pin icon SHALL appear in the same position in the action bar.

#### Scenario: Pin icon renders on AI responses
- **WHEN** an AI message bubble is rendered
- **THEN** a pin icon button SHALL appear in the action row where thumbs-up/down previously appeared
- **THEN** no thumbs-up or thumbs-down icons SHALL be present

#### Scenario: Pin icon is not shown on user messages
- **WHEN** a user message bubble is rendered
- **THEN** no pin icon SHALL appear

### Requirement: Saving toast on pin
The system SHALL display a transient "Saving…" toast banner at the top of the chat area when a user clicks the pin icon.

#### Scenario: Toast appears on pin click
- **WHEN** the user clicks the pin icon on an AI response
- **THEN** a "Saving…" toast SHALL appear centered at the top of the chat panel
- **THEN** the toast SHALL disappear automatically after approximately 1.5 seconds

#### Scenario: Toast appears on un-pin
- **WHEN** the user clicks the pin icon on an already-pinned AI response
- **THEN** a "Pin removed" toast SHALL appear centered at the top of the chat panel

### Requirement: Pin toggle behavior
The system SHALL toggle the pinned state of an AI response when the pin icon is clicked. Pinning an already-pinned response SHALL remove the pin.

#### Scenario: Pin icon reflects pinned state
- **WHEN** an AI response is pinned
- **THEN** the pin icon SHALL appear visually active (filled / indigo color)
- **WHEN** the same response is not pinned
- **THEN** the pin icon SHALL appear in its default inactive style (outline / gray)

### Requirement: Pins persisted to localStorage
The system SHALL persist pinned responses to localStorage under the key `pins_<course_id>`. Each pin entry SHALL store: `{ id, chat_id, chatTitle, modelLabel, summary, pinnedAt, userContent, aiContent }`.

#### Scenario: Pins survive page reload
- **WHEN** the user pins a response and reloads the page
- **THEN** the pinned entry SHALL still appear in the Pins panel
- **THEN** the pin icon on the original message SHALL appear in its active state if that message is still in view

#### Scenario: Un-pin removes entry from localStorage
- **WHEN** the user un-pins a response
- **THEN** the entry SHALL be removed from the `pins_<course_id>` localStorage key

### Requirement: Pins panel listing
The system SHALL render a Pins panel section below the chat messages area, within the same right-hand column. The panel SHALL list all saved pins for the current course.

#### Scenario: Pins panel shows pinned entries
- **WHEN** there is at least one pinned response for the active course
- **THEN** the Pins panel SHALL list each pin with: Chat Name, Model Name, 4–5 word AI summary, date formatted as `mm/dd hh:mm TZ`, and a chevron icon

#### Scenario: Pins panel is empty state
- **WHEN** there are no pinned responses for the active course
- **THEN** the Pins panel SHALL display a placeholder message such as "No saved pins yet."

### Requirement: Pin row summary derivation
The system SHALL derive the 4–5 word summary by taking the first 5 words of the AI response content, appended with an ellipsis if the content is longer.

#### Scenario: Summary is truncated to 5 words
- **WHEN** an AI response has more than 5 words
- **THEN** the summary displayed in the pin row SHALL be the first 5 words followed by "…"

#### Scenario: Short response uses full content
- **WHEN** an AI response has 5 words or fewer
- **THEN** the summary SHALL display the full response text without ellipsis

### Requirement: Expandable pin card
The system SHALL allow users to expand a pin row to reveal a card containing the original user message and the AI reply, styled identically to the chat message bubbles. Clicking the chevron icon (or the row) again while expanded SHALL collapse the card.

#### Scenario: Clicking a pin row expands the card
- **WHEN** the user clicks a collapsed pin row or its chevron icon
- **THEN** the card SHALL expand below the row showing the user message bubble and AI reply bubble

#### Scenario: Clicking an expanded row collapses the card
- **WHEN** the user clicks an already-expanded pin row or its chevron icon
- **THEN** the card SHALL collapse and the chat bubbles SHALL no longer be visible

#### Scenario: Chevron icon orientation matches open state
- **WHEN** the pin row is collapsed
- **THEN** the chevron icon SHALL point downward (▼)
- **WHEN** the pin row is expanded
- **THEN** the chevron icon SHALL point upward (▲)
