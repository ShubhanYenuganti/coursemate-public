# Pending Invites for Non-Users — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 1.3 (incomplete surfaced feature) + 2.4 (consumer improvement)
**Scope:** `api/sharing.py`, `api/auth.py` sign-in path, new `pending_invites` table, `src/SharingAccessModal.jsx`. No email provider work in v1 (none exists in the repo).

## Problem

`POST /api/sharing` looks up the invitee with `User.get_by_email(email)` and returns
`404 "No user found with that email address"` when they have never signed in
(`api/sharing.py`, do_POST). A course owner therefore cannot invite a classmate who hasn't yet
created an account — the exact viral path a student product needs.

## Goal

Inviting an email that has no account **succeeds** and records a pending invite. When that person
later signs in with Google using the same email, they are **auto-attached** as a collaborator on
every course they were invited to. Existing-user invites keep working exactly as today.

## Decisions

1. **New table `pending_invites`**, keyed by lowercased email + course. Stores who invited and
   when. A unique constraint on `(course_id, email)` makes re-inviting idempotent.
2. **Claim on sign-in.** `User.create_or_update` already runs on every Google login
   (`api/auth.py`). Immediately after it, call a new `PendingInvite.claim_for(user)` that converts
   every matching pending row into a real membership via the existing `Course.add_member`, then
   deletes the claimed rows. This is the only place new accounts are created, so it is the correct
   single hook.
3. **No email send in v1.** The repo has no transactional-email provider. v1 delivers the invite
   through the product: the owner sees "Pending" rows in `SharingAccessModal`, and the invitee is
   attached the moment they sign in. A future item can layer an email/notification on top of the
   same table (see `generation-notifications` and `free-tier` for where an email provider would
   land).
4. **Owner-only, same as today.** Only `course.primary_creator` may invite; same guard as the
   existing path.
5. **Members list shows pending invites** so the owner has feedback. `GET /api/sharing` returns a
   `pending` array alongside `members`.

## Schema — `migrations/010_pending_invites.sql`

```sql
CREATE TABLE IF NOT EXISTS pending_invites (
    id            SERIAL PRIMARY KEY,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    email         TEXT    NOT NULL,                 -- always stored lowercased
    invited_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (course_id, email)
);

CREATE INDEX IF NOT EXISTS idx_pending_invites_email ON pending_invites (email);
```

## Model — `PendingInvite` (in `api/models.py`)

```python
class PendingInvite:
    @staticmethod
    def create(course_id: int, email: str, invited_by_id: int) -> bool:
        # INSERT ... ON CONFLICT (course_id, email) DO NOTHING; returns True if a row now exists.

    @staticmethod
    def list_for_course(course_id: int) -> list:
        # SELECT email, invited_by_id, created_at WHERE course_id = %s ORDER BY created_at.

    @staticmethod
    def claim_for(user: dict) -> int:
        # For each pending row matching lower(user['email']):
        #   Course.add_member(course_id, user['id'], invited_by_id)
        #   DELETE the row.
        # Returns number of memberships created. Idempotent.

    @staticmethod
    def revoke(course_id: int, email: str) -> bool:
        # DELETE WHERE course_id AND email. For the owner's "cancel pending invite".
```

## API changes — `api/sharing.py`

- **POST**: when `User.get_by_email(email)` is `None`, instead of 404, call
  `PendingInvite.create(course_id, email, inviter['id'])` and return 200 with the refreshed
  members + pending lists (status `"pending"`).
- **GET**: return `{ "members": [...], "pending": PendingInvite.list_for_course(course_id) }`.
- **DELETE**: accept either `user_id` (existing member removal) or `email` (cancel a pending
  invite → `PendingInvite.revoke`).

## Auth change — `api/auth.py`

After the successful `User.create_or_update(...)` call and before/after `Session.create`, add:

```python
try:
    PendingInvite.claim_for(user)
except Exception:
    pass  # never block login on invite-claim failure
```

## Frontend — `src/SharingAccessModal.jsx`

- Render a "Pending" section listing pending emails with a "Cancel" button (calls
  `DELETE /api/sharing` with `{ course_id, email }`).
- On successful invite of a non-user, surface "Invited — they'll join when they sign in" instead of
  an error.

## Verification

- pytest: inviting a non-existent email creates a pending row (not 404); `claim_for` attaches the
  user on a simulated sign-in and is idempotent on a second call.
- Manual: owner invites `new@x.com` → appears under Pending → that user signs in with Google →
  becomes a collaborator, pending row gone.
