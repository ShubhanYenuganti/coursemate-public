# Generation-Ready Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notify users (Web Push + in-app) when an async quiz/flashcards/report finishes, deep-linking to the viewer, without keeping the tab open.

**Architecture:** Pure `notification_payload` builder + `notifications`/`push_subscriptions` tables; worker `ready`/`failed` transitions call a shared best-effort notify helper; a service worker + subscribe flow + bell badge on the client.

**Tech Stack:** Python serverless + Lambda, Neon Postgres, Web Push (VAPID), React + service worker, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-generation-notifications-design.md`

---

### Task 1: Pure payload builder

**Files:**
- Create: `api/services/notifications.py`
- Test: `tests/test_notification_payload.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notification_payload.py
from api.services.notifications import notification_payload

def test_ready_quiz_links_to_quiz_route():
    p = notification_payload('quiz', 'Week 3', 'ready', 7, 42)
    assert p['title'] == 'Your quiz is ready'
    assert p['link'] == '/course/7/quiz/42'
    assert p['type'] == 'generation_ready'

def test_ready_report_uses_reports_route():
    p = notification_payload('report', 'SLAM survey', 'ready', 7, 99)
    assert p['link'] == '/course/7/reports/99'

def test_failed_type_and_title():
    p = notification_payload('flashcards', 'Kinematics', 'failed', 1, 2)
    assert p['type'] == 'generation_failed'
    assert 'failed' in p['title']
    assert p['link'] == '/course/1/flashcards/2'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notification_payload.py -v` — FAIL.

- [ ] **Step 3: Implement** (function body from the spec into `api/services/notifications.py`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_notification_payload.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/notifications.py tests/test_notification_payload.py
git commit -m "feat: add notification payload builder"
```

---

### Task 2: Migration for notifications + push subscriptions

**Files:**
- Create: `migrations/014_notification_jobs.sql`

- [ ] **Step 1: Write the migration** (both tables from the spec).

- [ ] **Step 2: Apply**

Run: `psql "$DATABASE_URL" -f migrations/014_notification_jobs.sql` — two `CREATE TABLE` + index.

- [ ] **Step 3: Commit**

```bash
git add migrations/014_notification_jobs.sql
git commit -m "feat: add notifications and push_subscriptions tables"
```

---

### Task 3: Shared notify helper + worker hooks

**Files:**
- Modify: `api/services/notifications.py` (add `notify_generation(conn_or_db, user_id, payload)` + a VAPID push sender)
- Modify: `lambda/quiz_generate/handler.py` (terminal-status sites ~400 ready, ~329 failed), and the equivalent terminal-status sites in `lambda/flashcards_generate/` and `lambda/reports_generate/`
- Test: `tests/test_notify_generation.py`

- [ ] **Step 1: Write the failing test (insert + best-effort push)**

```python
# tests/test_notify_generation.py
from api.services import notifications as n

def test_notify_inserts_row_and_swallows_push_errors(monkeypatch):
    inserted = {}
    monkeypatch.setattr(n, '_insert_notification', lambda uid, p: inserted.update({'uid': uid, 'p': p}))
    monkeypatch.setattr(n, '_send_web_push_all', lambda uid, p: (_ for _ in ()).throw(RuntimeError('push down')))
    # must not raise even though push fails
    n.notify_generation(user_id=5, payload={'title': 't', 'body': 'b', 'link': '/x', 'type': 'generation_ready'})
    assert inserted['uid'] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notify_generation.py -v` — FAIL.

- [ ] **Step 3: Implement the helper**

```python
def notify_generation(user_id: int, payload: dict) -> None:
    try:
        _insert_notification(user_id, payload)
    except Exception:
        pass
    try:
        _send_web_push_all(user_id, payload)
    except Exception:
        pass  # push is best-effort; never break the worker
```

Implement `_insert_notification` (INSERT into `notifications`) and `_send_web_push_all` (load
`push_subscriptions` for the user; send via VAPID using env `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`;
drop 410/404 subscriptions). Keep dependencies minimal so each Lambda can import it.

- [ ] **Step 4: Wire into the workers**

At each worker's `ready` transition, after the status UPDATE:

```python
from services.notifications import notify_generation, notification_payload
payload = notification_payload(generation_type, title, 'ready', course_id, generation_id)
notify_generation(user_id, payload)
```

Do the same at the `failed` site with `'failed'`. Pull `user_id`/`course_id`/`title` from the job
context already available at those sites. Ensure `services/notifications.py` is packaged with each
Lambda's deploy bundle (mirror how the workers already import shared `services` modules).

- [ ] **Step 5: Run test to verify it passes + worker tests**

Run: `pytest tests/test_notify_generation.py -v` — PASS. Run any existing quiz/flashcards/reports
worker tests to confirm no regression.

- [ ] **Step 6: Commit**

```bash
git add api/services/notifications.py lambda/quiz_generate/handler.py lambda/flashcards_generate lambda/reports_generate tests/test_notify_generation.py
git commit -m "feat: notify users when generations finish"
```

---

### Task 4: Subscribe + list notifications API

**Files:**
- Create: `api/notifications.py` (`action=subscribe` POST, `action=list` GET, `action=mark_read` POST)
- Test: `tests/test_notifications_api.py`

- [ ] **Step 1: Write the failing test (subscribe validation)**

```python
# tests/test_notifications_api.py
from api.notifications import validate_subscription

def test_valid_subscription():
    ok, _ = validate_subscription({'endpoint': 'https://x', 'keys': {'p256dh': 'a', 'auth': 'b'}})
    assert ok is True

def test_invalid_subscription():
    ok, err = validate_subscription({'endpoint': 'https://x'})
    assert ok is False and 'keys' in err
```

- [ ] **Step 2: Run → FAIL**, then implement the handler modeled on `api/sharing.py` with
`validate_subscription`, persisting to `push_subscriptions` (upsert on `(user_id, endpoint)`), a
`list` returning recent `notifications`, and `mark_read` setting `read_at`.

- [ ] **Step 3: Run → PASS.**

- [ ] **Step 4: Commit**

```bash
git add api/notifications.py tests/test_notifications_api.py
git commit -m "feat: notifications subscribe/list/mark-read API"
```

---

### Task 5: Service worker + subscribe flow + bell

**Files:**
- Create: `public/sw.js`
- Modify: `src/App.jsx` (register SW), generation kickoff sites (request permission), header (bell badge)

- [ ] **Step 1: Service worker**

```js
// public/sw.js
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || 'CourseMate', {
    body: data.body || '', data: { link: data.link || '/dashboard' },
  }));
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.link));
});
```

- [ ] **Step 2: Register + subscribe**

Register `sw.js` in `src/App.jsx` on load. After a user starts a generation (quiz/flashcards/reports
kickoff handlers), call a helper that requests `Notification.requestPermission()`, subscribes via
`registration.pushManager.subscribe({ applicationServerKey: VAPID_PUBLIC_KEY })`, and POSTs the
subscription to `/api/notifications?action=subscribe`.

- [ ] **Step 3: Bell badge**

Add a header bell that GETs `/api/notifications?action=list`, shows the unread count, and links each
item to its `link`; mark read on open.

- [ ] **Step 4: Manually verify**

Run: `npm run build && npm run preview` (push needs HTTPS/localhost). Start a generation, grant push,
close the tab → receive a push on ready; click opens the viewer; bell shows the item.

- [ ] **Step 5: Commit**

```bash
git add public/sw.js src/App.jsx src/Quiz.jsx src/Flashcards.jsx src/Reports.jsx
git commit -m "feat: web push subscribe flow and in-app notification bell"
```

---

## Self-Review

- **Spec coverage:** payload builder (T1), tables (T2), worker hooks + best-effort notify (T3),
  subscribe/list API (T4), SW + bell (T5). ✓
- **Robustness:** `notify_generation` swallows both insert and push errors so a worker job never
  fails because of notifications. ✓
- **Future channel:** rows are the source of truth, so email can be added later as another delivery
  over the same `notifications` table. ✓
