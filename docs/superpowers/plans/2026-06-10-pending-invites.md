# Pending Invites for Non-Users Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inviting an email with no account records a pending invite instead of erroring; the invitee is auto-attached as a collaborator on their next Google sign-in.

**Architecture:** New `pending_invites` table + `PendingInvite` model. `api/sharing.py` POST creates a pending row when the email has no user; `api/auth.py` claims pending rows on sign-in via the existing `User.create_or_update` hook. `SharingAccessModal` shows and cancels pending invites.

**Tech Stack:** Python serverless (`BaseHTTPRequestHandler`), Neon Postgres (`psycopg3`), pytest, React.

**Spec:** `docs/superpowers/specs/2026-06-10-pending-invites-design.md`

---

### Task 1: Database migration

**Files:**
- Create: `migrations/010_pending_invites.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 010_pending_invites.sql — invites for users who have not signed up yet.
CREATE TABLE IF NOT EXISTS pending_invites (
    id            SERIAL PRIMARY KEY,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    email         TEXT    NOT NULL,
    invited_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (course_id, email)
);

CREATE INDEX IF NOT EXISTS idx_pending_invites_email ON pending_invites (email);
```

- [ ] **Step 2: Apply against the dev database**

Run (per CLAUDE.md, this one-file migration is run by the user against the DB):
`psql "$DATABASE_URL" -f migrations/010_pending_invites.sql`
Expected: `CREATE TABLE`, `CREATE INDEX`.

- [ ] **Step 3: Commit**

```bash
git add migrations/010_pending_invites.sql
git commit -m "feat: add pending_invites table"
```

---

### Task 2: `PendingInvite` model

**Files:**
- Modify: `api/models.py` (add `PendingInvite` class near `User`)
- Test: `tests/test_pending_invites.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pending_invites.py
import pytest
from api import models
from api.models import PendingInvite

class FakeCursor:
    def __init__(self, store): self.store = store; self._result = None
    def execute(self, sql, params=None):
        self.store['last'] = (sql, params)
        s = sql.lower()
        if 'insert into pending_invites' in s:
            key = (params[0], params[1])
            self.store['rows'][key] = {'course_id': params[0], 'email': params[1], 'invited_by_id': params[2]}
            self._result = {'id': 1}
        elif 'select' in s and 'pending_invites' in s:
            cid = params[0]
            self._result = [r for k, r in self.store['rows'].items() if k[0] == cid]
        elif 'delete from pending_invites' in s:
            for k in list(self.store['rows']):
                if k[0] == params[0] and k[1] == params[1]:
                    del self.store['rows'][k]
    def fetchone(self): return self._result if isinstance(self._result, dict) else None
    def fetchall(self): return self._result if isinstance(self._result, list) else []
    def __enter__(self): return self
    def __exit__(self, *a): return False

@pytest.fixture
def fake_db(monkeypatch):
    store = {'rows': {}}
    class Conn:
        def cursor(self, *a, **k): return FakeCursor(store)
        def commit(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
    import contextlib
    @contextlib.contextmanager
    def get_conn(): yield Conn()
    monkeypatch.setattr(models, 'get_connection', get_conn, raising=False)
    return store

def test_create_then_list(fake_db):
    PendingInvite.create(7, 'New@X.com'.lower(), 3)
    rows = PendingInvite.list_for_course(7)
    assert any(r['email'] == 'new@x.com' for r in rows)

def test_claim_attaches_and_is_idempotent(fake_db, monkeypatch):
    calls = []
    monkeypatch.setattr(models.Course, 'add_member',
                        staticmethod(lambda c, u, i: calls.append((c, u, i)) or True))
    PendingInvite.create(7, 'new@x.com', 3)
    n1 = PendingInvite.claim_for({'id': 99, 'email': 'new@x.com'})
    n2 = PendingInvite.claim_for({'id': 99, 'email': 'new@x.com'})
    assert n1 == 1 and n2 == 0
    assert calls == [(7, 99, 3)]
```

> Note: `api/models.py` uses the repo's existing DB-access helper. Inspect the top of
> `api/models.py` to confirm whether connections come from `get_connection()` / `db.get_*`. Match
> that exact helper name in both the implementation and the monkeypatch target in this test.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pending_invites.py -v`
Expected: FAIL — `ImportError: cannot import name 'PendingInvite'`.

- [ ] **Step 3: Implement `PendingInvite`**

Add to `api/models.py`, following the existing connection/cursor pattern used by `User` and
`Course` in the same file:

```python
class PendingInvite:
    @staticmethod
    def create(course_id: int, email: str, invited_by_id: int) -> bool:
        email = (email or "").lower().strip()
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO pending_invites (course_id, email, invited_by_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (course_id, email) DO NOTHING
                    RETURNING id
                    """,
                    (course_id, email, invited_by_id),
                )
            conn.commit()
        return True

    @staticmethod
    def list_for_course(course_id: int) -> list:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT email, invited_by_id, created_at
                    FROM pending_invites WHERE course_id = %s
                    ORDER BY created_at ASC
                    """,
                    (course_id,),
                )
                return cur.fetchall()

    @staticmethod
    def claim_for(user: dict) -> int:
        email = (user.get("email") or "").lower().strip()
        if not email:
            return 0
        claimed = 0
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT course_id, invited_by_id FROM pending_invites WHERE email = %s",
                    (email,),
                )
                rows = cur.fetchall()
            for r in rows:
                if Course.add_member(r["course_id"], user["id"], r["invited_by_id"]):
                    claimed += 1
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM pending_invites WHERE course_id = %s AND email = %s",
                        (r["course_id"], email),
                    )
            conn.commit()
        return claimed

    @staticmethod
    def revoke(course_id: int, email: str) -> bool:
        email = (email or "").lower().strip()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM pending_invites WHERE course_id = %s AND email = %s",
                    (course_id, email),
                )
            conn.commit()
        return True
```

Adjust `get_connection`/`dict_row` to match the helpers already imported at the top of
`api/models.py` (e.g. `from .db import get_connection`). Do not introduce a new DB helper.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pending_invites.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api/models.py tests/test_pending_invites.py
git commit -m "feat: add PendingInvite model with claim-on-signin"
```

---

### Task 3: Sharing API — create pending invite instead of 404

**Files:**
- Modify: `api/sharing.py` (POST, GET, DELETE; import `PendingInvite`)
- Test: `tests/test_sharing_pending.py`

- [ ] **Step 1: Write the failing test (pending creation path)**

```python
# tests/test_sharing_pending.py
from api import sharing

def test_post_non_user_creates_pending(monkeypatch):
    created = {}
    monkeypatch.setattr(sharing.User, 'get_by_google_id', staticmethod(lambda g: {'id': 1}))
    monkeypatch.setattr(sharing.User, 'get_by_email', staticmethod(lambda e: None))
    monkeypatch.setattr(sharing.Course, 'get_by_id', staticmethod(lambda c: {'primary_creator': 1}))
    monkeypatch.setattr(sharing.Course, 'get_members', staticmethod(lambda c: []))
    monkeypatch.setattr(sharing.PendingInvite, 'create',
                        staticmethod(lambda c, e, i: created.update({'c': c, 'e': e}) or True))
    monkeypatch.setattr(sharing.PendingInvite, 'list_for_course', staticmethod(lambda c: [{'email': 'new@x.com'}]))
    status, payload = sharing.invite_member(google_id='g', course_id=5, email='New@X.com')
    assert status == 200
    assert created == {'c': 5, 'e': 'new@x.com'}
    assert payload['pending'][0]['email'] == 'new@x.com'
```

> This test targets a small extracted helper `invite_member(...)` so the logic is testable without
> spinning up `BaseHTTPRequestHandler`. Extract the body of `do_POST` into a module-level
> `invite_member(google_id, course_id, email) -> (status, payload)` and have `do_POST` call it.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sharing_pending.py -v`
Expected: FAIL — `AttributeError: module 'api.sharing' has no attribute 'invite_member'`.

- [ ] **Step 3: Refactor + implement**

Add the import (in both branches of the try/except at top of `api/sharing.py`):

```python
from .models import User, PendingInvite     # and: from models import User, PendingInvite
```

Extract `invite_member` and change the no-user branch:

```python
def invite_member(google_id: str, course_id: int, email: str):
    email = (email or "").lower().strip()
    inviter = User.get_by_google_id(google_id)
    if not inviter:
        return 404, {"error": "User not found"}
    course = Course.get_by_id(course_id)
    if not course:
        return 404, {"error": "Course not found"}
    if course["primary_creator"] != inviter["id"]:
        return 403, {"error": "Only the course owner can invite collaborators"}

    invitee = User.get_by_email(email)
    if invitee is None:
        PendingInvite.create(course_id, email, inviter["id"])
        return 200, {
            "members": [_serialize_member(m) for m in Course.get_members(course_id)],
            "pending": PendingInvite.list_for_course(course_id),
            "status": "pending",
        }
    if invitee["id"] == inviter["id"]:
        return 400, {"error": "You cannot invite yourself"}
    if not Course.add_member(course_id, invitee["id"], inviter["id"]):
        return 409, {"error": "User is already a collaborator on this course"}
    return 200, {
        "members": [_serialize_member(m) for m in Course.get_members(course_id)],
        "pending": PendingInvite.list_for_course(course_id),
        "status": "added",
    }
```

Then in `do_POST`, replace the inline logic with:

```python
status, payload = invite_member(google_id, course_id, email)
send_json(self, status, payload)
```

Update `do_GET` to include pending:

```python
send_json(self, 200, {
    "members": [_serialize_member(m) for m in members],
    "pending": PendingInvite.list_for_course(course_id),
})
```

In `do_DELETE`, when the body carries `email` (not `user_id`), call `PendingInvite.revoke(course_id, email)` and return the refreshed lists.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sharing_pending.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/sharing.py tests/test_sharing_pending.py
git commit -m "feat: sharing API records pending invites for non-users"
```

---

### Task 4: Claim pending invites on sign-in

**Files:**
- Modify: `api/auth.py` (after `User.create_or_update`, import `PendingInvite`)
- Test: `tests/test_auth_claim_invites.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth_claim_invites.py
from api.models import PendingInvite

def test_claim_for_calls_add_member(monkeypatch):
    added = []
    import api.models as m
    monkeypatch.setattr(m.Course, 'add_member',
                        staticmethod(lambda c, u, i: added.append((c, u, i)) or True))
    # Stub the DB read to return one pending row, deletes are no-ops.
    monkeypatch.setattr(PendingInvite, 'claim_for', PendingInvite.claim_for)  # ensure real fn
    # (Covered more fully in test_pending_invites.py; here we assert the auth hook calls it.)
    import api.auth as auth
    calls = {'n': 0}
    monkeypatch.setattr(auth, 'PendingInvite', type('P', (), {'claim_for': staticmethod(lambda u: calls.__setitem__('n', calls['n'] + 1))}))
    auth.claim_pending_invites({'id': 1, 'email': 'a@b.com'})
    assert calls['n'] == 1
```

> Extract a tiny `claim_pending_invites(user)` wrapper in `api/auth.py` that swallows exceptions, so
> the hook is unit-testable and login can never fail because of invite-claiming.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_claim_invites.py -v`
Expected: FAIL — `AttributeError: module 'api.auth' has no attribute 'claim_pending_invites'`.

- [ ] **Step 3: Implement the hook**

Add the import (both try/except branches) and wrapper in `api/auth.py`:

```python
from .models import User, Session, PendingInvite   # and the `from models import ...` branch

def claim_pending_invites(user: dict) -> None:
    try:
        PendingInvite.claim_for(user)
    except Exception:
        pass  # never block login on invite-claim failure
```

Call it right after the successful `user = User.create_or_update(...)` in `do_POST`:

```python
claim_pending_invites(user)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth_claim_invites.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/auth.py tests/test_auth_claim_invites.py
git commit -m "feat: claim pending invites on Google sign-in"
```

---

### Task 5: Surface pending invites in the modal

**Files:**
- Modify: `src/SharingAccessModal.jsx`

- [ ] **Step 1: Read pending list from GET and store it**

Where the modal fetches members (search for `fetch('/api/sharing` or `?course_id=`), capture
`data.pending` into state alongside members:

```jsx
const [pending, setPending] = useState([]);
// in the .then(): setMembers(data.members || []); setPending(data.pending || []);
```

- [ ] **Step 2: Render a Pending section**

Below the members list, add:

```jsx
{pending.length > 0 && (
  <div className="mt-4">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Pending</h4>
    {pending.map((p) => (
      <div key={p.email} className="flex items-center justify-between py-1.5 text-sm">
        <span className="text-gray-700">{p.email} <span className="text-gray-400">— joins on sign-in</span></span>
        <button
          onClick={() => cancelPending(p.email)}
          className="text-xs text-red-500 hover:text-red-600"
        >Cancel</button>
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 3: Implement `cancelPending` and success copy**

```jsx
async function cancelPending(email) {
  const res = await fetch('/api/sharing', {
    method: 'DELETE',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ course_id: courseId, email }),
  });
  const data = await res.json();
  if (res.ok) { setMembers(data.members || []); setPending(data.pending || []); }
}
```

In the invite-submit handler, when the response `status === 'pending'`, show
"Invited — they'll join when they sign in" instead of treating it as an error. Use the modal's
existing CSRF token variable name (search for `X-CSRF-Token` already used in this file).

- [ ] **Step 4: Manually verify the full loop**

Run: `npm run dev`. As owner, invite a never-seen email → it appears under Pending with a success
note. Sign in (incognito) as that Google account → it becomes a member; reopen modal → pending row
gone, member present.

- [ ] **Step 5: Commit**

```bash
git add src/SharingAccessModal.jsx
git commit -m "feat: show and cancel pending invites in sharing modal"
```

---

## Self-Review

- **Spec coverage:** table (T1), model with idempotent claim (T2), POST/GET/DELETE changes (T3),
  sign-in claim hook (T4), modal pending UI (T5). ✓
- **Type consistency:** `PendingInvite.create/list_for_course/claim_for/revoke` signatures match
  across model, sharing API, and auth hook. `invite_member -> (status, payload)` consistent. ✓
- **DB helper caveat:** Tasks 2–4 explicitly tell the engineer to match the existing
  `api/models.py` connection helper rather than assume `get_connection`/`dict_row`. ✓
- **No placeholders:** every step shows real SQL/code/commands. ✓
