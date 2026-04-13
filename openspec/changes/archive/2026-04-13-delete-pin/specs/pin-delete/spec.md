## ADDED Requirements

### Requirement: DELETE endpoint removes a pin by assistant message ID
The system SHALL accept `DELETE /api/chat` with body `{ resource: 'pin', assistant_message_id: <int> }` and delete the matching row from `pinned_messages` where `user_id` matches the authenticated user.

#### Scenario: Successful deletion
- **WHEN** an authenticated user sends `DELETE /api/chat` with a valid `assistant_message_id` they own
- **THEN** the server deletes the pin row and returns `{ deleted: true }`

#### Scenario: Pin not found or not owned
- **WHEN** an authenticated user sends `DELETE /api/chat` with an `assistant_message_id` that does not exist or belongs to another user
- **THEN** the server returns `{ deleted: false }` with HTTP 200

#### Scenario: Missing assistant_message_id
- **WHEN** the request body omits `assistant_message_id` or provides a non-integer value
- **THEN** the server returns HTTP 400 with an error message

### Requirement: Trash icon in PinsPanel deletes a pin
The PinsPanel SHALL display a trash icon button to the right of the expand/collapse chevron for each pin row. Clicking it SHALL delete the pin from the database and remove it from the client-side pin list.

#### Scenario: User clicks trash icon
- **WHEN** the user clicks the trash icon on a pin row
- **THEN** `DELETE /api/chat` is called with the pin's `assistant_message_id`, the pin is removed from `pinnedResponses` state, and the assistant message in the chat log is no longer marked as pinned

#### Scenario: Trash click does not expand/collapse the pin row
- **WHEN** the user clicks the trash icon
- **THEN** the row's expand/collapse state is NOT toggled

### Requirement: Chat log pin state reflects deletion
The system SHALL derive the `isPinned` flag for assistant messages in the chat log from `pinnedResponses` state; removing a pin from `pinnedResponses` SHALL automatically unmark the corresponding message.

#### Scenario: Pin deleted from PinsPanel while chat is open
- **WHEN** a pin is deleted via the trash icon while the originating chat is active
- **THEN** the pin icon on the assistant message in the chat log changes to the unpinned (hollow) state without a page reload
