# Retrieval Feedback Loop — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 2.7
**Scope:** New `retrieval_feedback` table, new `api/feedback.py` endpoint, feedback affordance in `src/ChatTab.jsx` message actions. Feeds the QASPER-style eval set.

## Problem

Recall@5 is 0.654 and a Jun 10 session documented the agent missing sections that ChatGPT found
with the same sources. The retrieval-budget-frontier work targets this, but there is no way for real
users to report "you missed something," and no accumulating set of labeled failure cases to grow the
eval from production traffic.

## Goal

On any assistant answer, the user can:
1. Thumbs-down the answer, and optionally
2. Say "it missed something in [material]" (pick a material from the chat's set) with a free-text
   note.

Each report is stored with the question, the answer's grounding metadata (which pages were fetched),
and the named material — a labeled negative example the team can fold into the retrieval eval.

## Decisions

1. **Separate `retrieval_feedback` table**, not a column on `chat_messages`. Feedback is sparse and
   analytical; keeping it separate avoids bloating the hot chat table and lets it carry a metadata
   snapshot.
2. **Snapshot grounding at report time.** Store the fetched-pages / citation metadata that already
   exists on the assistant message (`grounding`/sources) so the eval example is self-contained even
   if the chat is later edited or deleted (`ON DELETE SET NULL` on `message_id`).
3. **Material is optional.** Plain thumbs-down (no material, no note) is still useful signal;
   "missed something in X" is the high-value labeled case.
4. **New thin endpoint `api/feedback.py`**, following the existing handler pattern, rather than
   overloading `chat.py`. POST creates a row; that's all v1 needs (analysis is offline SQL).
5. **No moderation/abuse surface** — feedback is private to the owning user's data and only consumed
   internally; YAGNI for v1.

## Schema — `migrations/012_retrieval_feedback.sql`

```sql
CREATE TABLE IF NOT EXISTS retrieval_feedback (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id       INTEGER REFERENCES chats(id) ON DELETE SET NULL,
    message_id    INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    course_id     INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    question      TEXT,                       -- the user turn this answer responded to
    missed_material_id INTEGER,               -- nullable: "missed something in this material"
    note          TEXT,                       -- nullable free text
    grounding     JSONB,                      -- snapshot of fetched pages / citations at report time
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_feedback_course ON retrieval_feedback (course_id, created_at);
```

> Confirm the real `chats` table name (the chat-thread table) against `api/chat.py` before applying;
> adjust the FK if it differs.

## API — `api/feedback.py`

`POST /api/feedback` body:
```json
{
  "chat_id": 12, "message_id": 345, "course_id": 7,
  "question": "How does EKF handle nonlinearity?",
  "missed_material_id": 88, "note": "Lecture 6 slide 14 covers it",
  "grounding": { "...": "snapshot from the assistant message" }
}
```
Auth + CSRF as in other POST handlers. Validates `message_id`/`chat_id` belong to the user, inserts a
row, returns `201 {"ok": true}`.

## Frontend — `src/ChatTab.jsx`

- Add a thumbs-down to the assistant message action row (next to existing copy/regenerate controls).
- Clicking it opens a small popover: optional "Which material did it miss?" select (populated from
  the chat's `materials` state already loaded) + an optional note + Submit.
- On submit, POST to `/api/feedback` with the message's `question` (preceding user turn) and the
  message's grounding/sources object (already in component state for the sources panel).

## Verification

- pytest: `api/feedback.py` validates ownership and inserts; rejects a `message_id` not owned by the
  caller.
- Manual: thumbs-down an answer, pick a material, add a note, submit → row appears in
  `retrieval_feedback` with the question + grounding snapshot.
- Offline: a sample SQL query returns `(question, missed_material_id, note)` rows for eval triage.
