# Spec: Chat Search

## Purpose

Enables users to search across their chats by title and message content within a course. Provides a modal UI with debounced querying, ranked results split into title matches and content matches, and direct navigation to a selected chat.

---

## Requirements

### Requirement: chat_search endpoint returns title and content matches in a single response
The system SHALL accept `GET /api/chat?resource=chat_search&q=<query>&course_id=<id>` and return `{ title_matches, content_matches }` where title matches are chats whose title satisfies the FTS query and content matches are chats (not already in title matches) that have at least one message satisfying the FTS query.

#### Scenario: Query matches some chat titles and some message content
- **WHEN** an authenticated user queries `resource=chat_search` with a non-empty `q`
- **THEN** the response contains `title_matches` (chats whose title FTS-matches the query, ordered by `ts_rank DESC`) and `content_matches` (remaining chats with at least one matching message, ordered by aggregated hit score DESC), with no chat appearing in both lists

#### Scenario: Query matches only titles
- **WHEN** the query matches chat titles but no message content in any unmatched chat
- **THEN** `title_matches` is non-empty and `content_matches` is an empty array

#### Scenario: Query matches only message content
- **WHEN** the query does not match any chat title but matches message content in several chats
- **THEN** `title_matches` is an empty array and `content_matches` is non-empty

#### Scenario: Query matches nothing
- **WHEN** the query matches neither any chat title nor any message content
- **THEN** both `title_matches` and `content_matches` are empty arrays

#### Scenario: Results are capped
- **WHEN** more than 20 chats match by title or more than 20 match by content
- **THEN** each list is capped at 20 results

#### Scenario: Archived chats are excluded
- **WHEN** a matching chat has `is_archived = TRUE`
- **THEN** it does not appear in either `title_matches` or `content_matches`

#### Scenario: Missing or invalid course_id
- **WHEN** `course_id` is absent or non-integer
- **THEN** the server returns HTTP 400 with an error message

#### Scenario: Access denied
- **WHEN** the authenticated user does not have access to the given `course_id`
- **THEN** the server returns HTTP 403

---

### Requirement: Title matches are ranked above content matches
Title matches SHALL receive a score boost (≥ 3× the raw `ts_rank` value) so that a chat whose title directly matches the query always appears in the title section rather than the content section, regardless of how many message hits it has.

#### Scenario: Chat matches both title and message content
- **WHEN** a chat's title satisfies the FTS query and its messages also contain the query terms
- **THEN** the chat appears only in `title_matches`, not in `content_matches`

---

### Requirement: Content match score uses logarithmic hit dampening
Content match score SHALL be computed as `(1 + ln(hit_count)) × best_message_rank` so that a chat with many low-quality hits does not outrank a chat with fewer but higher-ranked hits.

#### Scenario: High hit count vs. high relevance
- **WHEN** chat A has 50 weak hits and chat B has 5 highly-ranked hits
- **THEN** chat B may rank above chat A depending on `best_message_rank` values

---

### Requirement: Search modal opens from the sidebar search icon
The system SHALL render a centered overlay modal when the user clicks the search icon in the ChatTab sidebar header. The modal SHALL cover the full viewport with a semi-transparent backdrop.

#### Scenario: User clicks search icon
- **WHEN** the user clicks the magnifying-glass button in the sidebar header
- **THEN** the search modal appears centered on screen with a backdrop, and the search input is focused

#### Scenario: User dismisses via backdrop click
- **WHEN** the user clicks outside the modal (on the backdrop)
- **THEN** the modal closes and the chat view is restored

#### Scenario: User dismisses via Escape key
- **WHEN** the modal is open and the user presses Escape
- **THEN** the modal closes

---

### Requirement: Empty query shows all chats sorted by recency
When the search input is empty the modal SHALL display all currently-loaded chats (from ChatTab state) sorted by `last_message_at DESC` as a flat list with no section headers, without making a network request.

#### Scenario: Modal opens with no prior query
- **WHEN** the modal opens with an empty input
- **THEN** all chats are listed immediately (no loading state) in recency order

#### Scenario: User clears a previous query
- **WHEN** the user deletes all text from the input after having typed a query
- **THEN** the results revert to the full recency-sorted chat list without a new fetch

---

### Requirement: Typing triggers a debounced search
The modal SHALL wait 300 ms after the user stops typing before issuing `GET /api/chat?resource=chat_search&q=…`. Intermediate keystrokes SHALL NOT trigger additional requests.

#### Scenario: User types quickly
- **WHEN** the user types several characters in under 300 ms
- **THEN** only one request is made (for the final value), not one per keystroke

---

### Requirement: Results render in two labeled sections
When a non-empty query is active the modal SHALL display results in two visually distinct sections separated by sticky section headers: "TITLE MATCHES" above and "IN CONVERSATION" below. A section is omitted entirely if it has no results.

#### Scenario: Both sections have results
- **WHEN** `title_matches` and `content_matches` are both non-empty
- **THEN** both section headers and their rows are rendered in order

#### Scenario: Only title matches
- **WHEN** `content_matches` is empty
- **THEN** only the "TITLE MATCHES" header and its rows are shown; "IN CONVERSATION" is not rendered

#### Scenario: Only content matches
- **WHEN** `title_matches` is empty
- **THEN** only the "IN CONVERSATION" header and its rows are shown

#### Scenario: No results
- **WHEN** both arrays are empty
- **THEN** a "No chats found" empty state is displayed instead of section headers

---

### Requirement: Clicking a result navigates to that chat and closes the modal
Each result row SHALL be clickable. Clicking a row SHALL select that chat (equivalent to clicking it in the sidebar list) and close the search modal.

#### Scenario: User clicks a result
- **WHEN** the user clicks any row in the results list
- **THEN** the corresponding chat becomes active in the chat view and the modal closes
