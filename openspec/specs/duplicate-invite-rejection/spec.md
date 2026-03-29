## Purpose

Ensures that inviting a user who is already a collaborator on a course is rejected with a clear conflict error, preventing duplicate memberships and providing actionable feedback to the course owner.

## Requirements

### Requirement: Duplicate invite is rejected with a conflict error

When a course owner invites a user who is already a collaborator on the course, the system SHALL return a 409 Conflict response with a descriptive error message instead of silently succeeding.

#### Scenario: Inviting an existing collaborator

- **WHEN** a course owner submits a POST to `/api/sharing` with an email that belongs to a user who is already in `course_members` for that course
- **THEN** the system SHALL return HTTP 409
- **AND** the response body SHALL contain `{"error": "User is already a collaborator on this course"}`

#### Scenario: Inviting a new collaborator still succeeds

- **WHEN** a course owner submits a POST to `/api/sharing` with an email that belongs to a user who is NOT yet a collaborator
- **THEN** the system SHALL return HTTP 200
- **AND** the response body SHALL contain the updated `members` array including the newly added collaborator

#### Scenario: add_member returns false for duplicate

- **WHEN** `Course.add_member()` is called with a `user_id` that already has a row in `course_members` for the given `course_id`
- **THEN** the method SHALL return `False`
- **AND** `Course.add_co_creator()` SHALL NOT be called
