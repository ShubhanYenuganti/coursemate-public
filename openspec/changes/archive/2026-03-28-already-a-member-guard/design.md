## Context

The course sharing feature allows owners to invite collaborators by email. Membership is tracked in two places: the `course_members` table (join table) and a `co_creator_ids` JSONB array on the `courses` row. The `add_member` method does an `INSERT ... ON CONFLICT DO NOTHING`, which silently succeeds when the user is already a member, returning `True` regardless. The `remove_member` method already uses `cursor.rowcount` to distinguish "deleted" from "not found" — we just need to apply the same pattern to `add_member`.

## Goals / Non-Goals

**Goals:**
- Return a meaningful error to the caller when an invite targets an existing member
- Keep the fix minimal — no new queries, no new methods

**Non-Goals:**
- Changing the DB schema or constraint behavior
- Adding frontend changes (error surfaces already work correctly)
- Handling the case where the owner invites themselves (already caught earlier in `do_POST`)

## Decisions

### Decision: Use `cursor.rowcount` instead of a pre-check query

`cursor.rowcount` after `INSERT ... ON CONFLICT DO NOTHING` is 0 when the row already exists and 1 when it was inserted. This is idiomatic Postgres — no extra round-trip, no TOCTOU race. The same pattern is already used in `remove_member` (line 750 in courses.py).

**Alternative considered**: SELECT before INSERT to check membership. Rejected — adds a round-trip and introduces a race condition between check and insert.

**Alternative considered**: Add a new `is_member()` method. Rejected — unnecessary abstraction for a one-liner fix.

### Decision: Return 409 Conflict from the API

HTTP 409 is the correct status for "the request cannot be completed due to a conflict with the current state of the resource." The frontend's existing `if (!res.ok) throw new Error(data.error)` path already surfaces this to the user.

## Risks / Trade-offs

- `add_co_creator` is still called even when `rowcount == 0` in the current code path. After the fix, we skip it when `rowcount == 0`, which is safe — the user is already in `co_creator_ids` if they're already a member.

## Open Questions

None — this is a narrow, well-understood fix.
