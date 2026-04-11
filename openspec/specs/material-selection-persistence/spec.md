# material-selection-persistence Specification

## Purpose
TBD - created by archiving change notion-integration. Update Purpose after archive.
## Requirements
### Requirement: Material selections are persisted per user, course, and context
A `material_selections` table stores each user's explicit selection state per material per context. When no row exists for a (user, course, material, context) tuple, the default is derived from ownership: own materials default to selected, collaborator materials default to unselected. Toggling a material upserts a row.

```sql
CREATE TABLE material_selections (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses(id)    ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES materials(id)  ON DELETE CASCADE,
    context     VARCHAR(30) NOT NULL,   -- 'chat' | 'quiz' | 'flashcards' | 'report'
    provider    VARCHAR(50),            -- NULL = manual upload, 'notion', 'google_drive'
    selected    BOOLEAN NOT NULL DEFAULT true,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, material_id, context)
);
```

FK `ON DELETE CASCADE` on `material_id` ensures removed materials are automatically dropped from all selection rows — no stale references.

#### Scenario: First load — own materials auto-selected
- **WHEN** a user opens a course context (chat, quiz, etc.) for the first time
- **AND** they have uploaded materials in that course
- **THEN** those materials appear as selected without any `material_selections` row existing
- **AND** the effective selection is computed as: `uploaded_by = user_id` → selected

#### Scenario: First load — collaborator materials unselected
- **WHEN** a collaborator has public materials in the course
- **AND** no `material_selections` row exists for the current user + those materials
- **THEN** those materials appear in the "From collaborators" section as unselected

#### Scenario: Explicit toggle persists across sessions
- **WHEN** a user deselects one of their own materials in chat context
- **THEN** a row is upserted: `{ user_id, course_id, material_id, context='chat', selected=false }`
- **AND** on next load, that material remains deselected
- **WHEN** the user re-selects it
- **THEN** the row is updated to `selected=true`

#### Scenario: Material deleted — selection cleans up automatically
- **WHEN** a material is deleted (by owner or course admin)
- **THEN** all `material_selections` rows referencing that `material_id` are deleted via FK cascade
- **AND** no orphaned selection state remains

### Requirement: Material pickers default to own materials; collaborator materials are opt-in
In ChatTab, Quiz, Flashcards, and Reports, the material picker SHALL show two sections:
1. **My materials** — all materials `uploaded_by = current_user` in the course, selected by default (unless explicitly deselected)
2. **From collaborators** — materials `uploaded_by ≠ current_user` AND `visibility = 'public'`, unselected by default

#### Scenario: Collaborator public material added to selection
- **WHEN** the user checks a collaborator's material in the "From collaborators" section
- **THEN** a row is upserted: `{ ..., material_id, context, selected=true }`
- **AND** that material is included in the active context for that session and future sessions

#### Scenario: Private collaborator materials not shown
- **WHEN** a collaborator's material has `visibility='private'`
- **THEN** it does NOT appear in the "From collaborators" section for any other user
- **REGARDLESS** of whether a `material_selections` row exists

### Requirement: Hover tooltip shows full collaborator metadata
In the "From collaborators" section, hovering over any material item SHALL display a tooltip with three lines:
- Line 1: Collaborator's display name
- Line 2: Full material title (untruncated)
- Line 3: Collaborator's email address

#### Scenario: Tooltip on collaborator material
- **WHEN** the user hovers over "Notion: Wk3 Dyn..." in the collaborator section
- **THEN** a tooltip appears showing:
  ```
  Alice Kim
  Notion: Week 3 Dynamics Notes
  alice@university.edu
  ```

### Requirement: `provider` field enables bulk selection operations
The `provider` column on `material_selections` SHALL be populated when a material is added via `POST /api/notion?action=...` or the integration poller. This enables future bulk operations such as "deselect all Notion materials for this course" by querying `WHERE provider='notion'` without joining `materials`.

#### Scenario: Bulk deselect by provider (future-facing)
- **WHEN** a future "Disconnect Notion" flow optionally deselects all Notion materials in context
- **THEN** `UPDATE material_selections SET selected=false WHERE user_id=X AND provider='notion'` is sufficient with no join required

### Requirement: Selection state is loaded from DB on component mount
Each of ChatTab, Quiz, Flashcards, and Reports SHALL call `GET /api/materials?action=selections&course_id=<id>&context=<context>` on mount. The API SHALL return all materials for the course (with visibility filtering applied) annotated with `selected: true/false` per the DB state and default logic.

#### Scenario: API returns merged selection state
- **WHEN** `GET /api/materials?action=selections&course_id=3&context=chat`
- **THEN** the response includes all accessible materials with `selected` field:
  ```json
  [
    { "id": 1, "name": "My notes.pdf", "uploaded_by_me": true, "selected": true },
    { "id": 2, "name": "Notion: Lecture 4", "uploaded_by_me": true, "selected": true },
    { "id": 5, "name": "Alice — Notion: HW1", "uploaded_by_me": false, "selected": false,
      "collaborator": { "name": "Alice Kim", "email": "alice@uni.edu" } }
  ]
  ```
- **AND** `selected` for materials without a DB row is derived from `uploaded_by_me`

