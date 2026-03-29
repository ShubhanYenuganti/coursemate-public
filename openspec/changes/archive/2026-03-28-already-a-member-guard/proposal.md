## Why

When a course owner invites someone who is already a collaborator, the API silently succeeds with a 200 and the UI shows a false "added as a collaborator" confirmation. The invite did nothing, but the owner has no way to know that.

## What Changes

- `Course.add_member()` now returns `False` when the invitee is already a member (INSERT did nothing), instead of always returning `True`
- `POST /api/sharing` returns `409 Conflict` with a clear error message when `add_member` returns `False`
- The frontend already surfaces API errors via `data.error` — no frontend changes needed

## Capabilities

### New Capabilities

- `duplicate-invite-rejection`: Detect and reject invitations to users who are already collaborators on a course, returning a meaningful error instead of silently succeeding

### Modified Capabilities

<!-- No existing spec-level requirements are changing -->

## Impact

- `api/courses.py`: `Course.add_member()` — check `cursor.rowcount` after INSERT to detect DO NOTHING
- `api/sharing.py`: `do_POST` — return 409 when `add_member` returns `False`
