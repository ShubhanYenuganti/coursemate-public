# pinned-messages-backend Specification

## Purpose
TBD - created by archiving change pin-ai-responses. Update Purpose after archive.
## Requirements
### Requirement: pinned_messages table
The system SHALL create a `pinned_messages` table with the following columns:

```sql
CREATE TABLE public.pinned_messages (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id             INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chat_id               INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_message_id       INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    assistant_message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    ai_summary            VARCHAR(300),
    pinned_at             TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pinned_messages_unique_pin UNIQUE (user_id, assistant_message_id)
);

CREATE INDEX idx_pinned_messages_course_user
    ON public.pinned_messages (course_id, user_id);
```

`ai_summary` stores the pre-computed 4–5 word summary derived from the AI response content at pin time. The UNIQUE constraint on `(user_id, assistant_message_id)` prevents duplicate pins of the same AI reply.

#### Scenario: Table creation migration
- **WHEN** the migration SQL is run against the database
- **THEN** `pinned_messages` SHALL exist with all columns, constraints, and index as specified above

#### Scenario: Cascade delete on message deletion
- **WHEN** a `chat_messages` row referenced by `user_message_id` or `assistant_message_id` is deleted
- **THEN** the corresponding `pinned_messages` row SHALL be automatically deleted via ON DELETE CASCADE

#### Scenario: Duplicate pin prevented at DB level
- **WHEN** an INSERT is attempted for a `(user_id, assistant_message_id)` pair that already exists
- **THEN** the database SHALL raise a unique-constraint violation

### Requirement: Pin API via resource=pin branch in api/chat.py
The system SHALL handle pin operations by adding a `resource == 'pin'` branch to the existing `api/chat.py` handler, consistent with how `resource == 'message'` and `resource == 'chat'` are already handled. No new handler file SHALL be created.

All actions SHALL require an authenticated session. Requests from unauthenticated users SHALL receive HTTP 401.

#### Scenario: Pin action inserts a row
- **WHEN** a POST to `/api/chat` is made with `{ resource: "pin", action: "pin", user_message_id, assistant_message_id, course_id, chat_id, ai_summary }`
- **THEN** a new row SHALL be inserted into `pinned_messages`
- **THEN** the response SHALL be HTTP 200 with `{ pin: { id, pinned_at } }`
- **WHEN** the same pair is already pinned
- **THEN** the endpoint SHALL return HTTP 200 with the existing pin (idempotent, using `ON CONFLICT DO NOTHING`)

#### Scenario: Unpin action deletes a row
- **WHEN** a POST to `/api/chat` is made with `{ resource: "pin", action: "unpin", assistant_message_id }`
- **THEN** the row for the authenticated user and that `assistant_message_id` SHALL be deleted
- **THEN** the response SHALL be HTTP 200 with `{ deleted: true }`
- **WHEN** no such pin exists
- **THEN** the endpoint SHALL return HTTP 200 with `{ deleted: false }` (idempotent)

#### Scenario: List action returns pins for a course
- **WHEN** a GET to `/api/chat?resource=pin&course_id=<id>` is made by an authenticated user
- **THEN** the response SHALL be HTTP 200 with `{ pins: [ ... ] }` ordered by `pinned_at DESC`
- **THEN** each pin entry SHALL include: `id`, `chat_id`, `user_message_id`, `assistant_message_id`, `ai_summary`, `pinned_at`
- **THEN** only pins belonging to the authenticated user SHALL be returned

### Requirement: Backend ownership enforcement
The system SHALL verify that the authenticated user owns both the `user_message_id` and `assistant_message_id` rows before inserting a pin (i.e., `chat_messages.user_id = session.user_id`).

#### Scenario: Pin rejected for another user's message
- **WHEN** a POST to `/api/pin` with `action: "pin"` references a `chat_messages.id` that belongs to a different user
- **THEN** the endpoint SHALL return HTTP 403 and SHALL NOT insert a row

#### Scenario: Pin accepted for own message
- **WHEN** a POST to `/api/pin` with `action: "pin"` references messages that belong to the authenticated user
- **THEN** the endpoint SHALL insert the pin and return HTTP 200

### Requirement: Frontend uses API instead of localStorage
The system SHALL replace all localStorage pin reads/writes in `ChatTab.jsx` with API calls to `/api/chat?resource=pin`. On mount, the component SHALL fetch the pin list for the current course. Pin/unpin user actions SHALL trigger POST requests to the same endpoint.

#### Scenario: Pins load from API on mount
- **WHEN** `ChatTab` mounts with a valid `course.id`
- **THEN** it SHALL fetch `GET /api/chat?resource=pin&course_id=<id>` and populate `pinnedResponses` state

#### Scenario: Pin action calls API
- **WHEN** the user clicks the pin icon on an AI response
- **THEN** `ChatTab` SHALL POST `{ resource: "pin", action: "pin", ... }` to `/api/chat`
- **THEN** on success it SHALL add the returned pin entry to `pinnedResponses` state

#### Scenario: Unpin action calls API
- **WHEN** the user clicks the pin icon on an already-pinned AI response
- **THEN** `ChatTab` SHALL POST `{ resource: "pin", action: "unpin", assistant_message_id }` to `/api/chat`
- **THEN** on success it SHALL remove the entry from `pinnedResponses` state

