# Generation-Ready Notifications — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 3.2
**Scope:** Notify users when an async quiz/flashcards/report finishes, so they don't have to keep the tab open. Web Push in v1; the same hook supports email later.

## Problem

Generation is async (SQS + worker Lambdas) and the frontend polls `get_generation_status`. If the
user closes the tab, they never learn it's ready. The worker already sets `status='ready'`
(`lambda/quiz_generate/handler.py:400`, and the parallel flashcards/reports workers) — the perfect
hook to fire a notification with a deep link to the existing viewer route
(`/course/:id/quiz/:generationId`).

## Goal

When a generation transitions to `ready` (or `failed`), the user receives a notification:
- **Web Push** (works when the tab is closed, if they granted permission): "Your quiz 'Week 3' is
  ready" → clicking opens the viewer.
- Stored as an in-app notification row too, so a bell/badge can show it on next visit.

## Decisions

1. **Notification on the worker `ready`/`failed` transition.** Add a single call where the worker
   sets terminal status. Keep it best-effort — a notification failure must never fail the job.
2. **In-app row is the source of truth; Web Push is the delivery.** A `notifications` table records
   `(user_id, type, title, body, link, read_at)`. Web Push is a best-effort push of the same payload.
   This makes email a later delivery channel over the same rows.
3. **Web Push via VAPID.** Standard browser Push API + a stored `push_subscriptions` row per
   device. The worker (or a tiny notify endpoint it calls) sends the push using a VAPID key pair
   (new env vars). No third-party push service.
4. **Pure payload builder.** `notification_payload(generation_type, title, status, course_id,
   generation_id)` → `{title, body, link}` is the TDD core.
5. **Permission is opt-in and non-blocking.** The app requests Push permission contextually (after a
   user kicks off a generation), never on first load.

## Schema — `migrations/014_notification_jobs.sql`

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,                 -- 'generation_ready' | 'generation_failed'
    title       TEXT NOT NULL,
    body        TEXT,
    link        TEXT,
    read_at     TIMESTAMP,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint    TEXT NOT NULL,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, endpoint)
);
```

## Payload builder — `api/services/notifications.py`

```python
_LABELS = {"quiz": "quiz", "flashcards": "flashcards", "report": "report"}

def notification_payload(generation_type, title, status, course_id, generation_id):
    kind = _LABELS.get(generation_type, "study set")
    route = {"quiz": "quiz", "flashcards": "flashcards", "report": "reports"}.get(generation_type, "quiz")
    link = f"/course/{course_id}/{route}/{generation_id}"
    if status == "ready":
        return {"title": f"Your {kind} is ready", "body": title or "", "link": link, "type": "generation_ready"}
    return {"title": f"Your {kind} failed to generate", "body": title or "", "link": link, "type": "generation_failed"}
```

## Worker hook

Where each worker sets terminal status (e.g. `lambda/quiz_generate/handler.py:400` for `ready`,
`:329`/`_mark_generation_failed` for failed), call a shared notify helper that:
1. builds the payload,
2. inserts a `notifications` row,
3. best-effort Web Push to all of the user's `push_subscriptions`.

The notify helper lives in a shared module importable by all three workers (they each have their own
deps; keep it dependency-light — `pywebpush` or a minimal VAPID sender).

## Frontend

- Service worker (`public/sw.js`) handles `push` → `showNotification`, and `notificationclick` →
  focus/open the `link`.
- A small subscribe flow: after the user starts a generation, request permission and POST the
  `PushSubscription` to `/api/notifications?action=subscribe`.
- A bell/badge reading unread `notifications` (GET) for in-app display.

## Verification

- pytest: `notification_payload` table (ready/failed × quiz/flashcards/report → correct title +
  link route).
- Manual: start a generation, grant push, close the tab → receive a push when ready; clicking opens
  the viewer; the bell shows the unread item.
