# Retrieval Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users flag answers that missed something (optionally naming the material), capturing the question + grounding snapshot as labeled negative examples for the retrieval eval.

**Architecture:** New `retrieval_feedback` table + thin `api/feedback.py` POST handler with ownership validation; a thumbs-down popover in `ChatTab`'s message actions.

**Tech Stack:** Python serverless, Neon Postgres (JSONB), pytest, React.

**Spec:** `docs/superpowers/specs/2026-06-10-retrieval-feedback-design.md`

---

### Task 1: Database migration

**Files:**
- Create: `migrations/012_retrieval_feedback.sql`

- [ ] **Step 1: Confirm the chat-thread table name**

Run: `rg -n "FROM chats|INSERT INTO chats|CREATE TABLE.*chat" api migrations | head`
Use the actual thread table name (likely `chats`) in the FK below. If it differs, substitute it.

- [ ] **Step 2: Write the migration**

```sql
-- 012_retrieval_feedback.sql — labeled "it missed something" reports for retrieval eval.
CREATE TABLE IF NOT EXISTS retrieval_feedback (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id       INTEGER REFERENCES chats(id) ON DELETE SET NULL,
    message_id    INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    course_id     INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    question      TEXT,
    missed_material_id INTEGER,
    note          TEXT,
    grounding     JSONB,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_feedback_course ON retrieval_feedback (course_id, created_at);
```

- [ ] **Step 3: Apply**

Run: `psql "$DATABASE_URL" -f migrations/012_retrieval_feedback.sql`
Expected: `CREATE TABLE`, `CREATE INDEX`.

- [ ] **Step 4: Commit**

```bash
git add migrations/012_retrieval_feedback.sql
git commit -m "feat: add retrieval_feedback table"
```

---

### Task 2: `api/feedback.py` POST handler

**Files:**
- Create: `api/feedback.py`
- Test: `tests/test_feedback.py`

- [ ] **Step 1: Write the failing test (pure validation helper)**

```python
# tests/test_feedback.py
from api.feedback import validate_feedback

def test_requires_message_and_chat():
    ok, err = validate_feedback({'chat_id': 1, 'message_id': 2})
    assert ok is True and err is None

def test_rejects_missing_ids():
    ok, err = validate_feedback({'note': 'x'})
    assert ok is False and 'message_id' in err

def test_note_and_material_optional():
    ok, _ = validate_feedback({'chat_id': 1, 'message_id': 2, 'missed_material_id': 9, 'note': 'see slide 14'})
    assert ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feedback.py -v` — FAIL (module missing).

- [ ] **Step 3: Implement handler + helper**

Model the handler on `api/sharing.py` (same imports/auth pattern). Include the pure validator so it
is unit-testable:

```python
# api/feedback.py
import json
from http.server import BaseHTTPRequestHandler

try:
    from .middleware import send_json, handle_options, authenticate_request, sanitize_string
    from .models import User
    from .db import get_connection            # match the helper used elsewhere in api/
except ImportError:
    from middleware import send_json, handle_options, authenticate_request, sanitize_string
    from models import User
    from db import get_connection


def validate_feedback(data: dict):
    if not isinstance(data.get('chat_id'), int) or not isinstance(data.get('message_id'), int):
        return False, "chat_id and message_id are required"
    return True, None


def insert_feedback(user_id: int, data: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO retrieval_feedback
                     (user_id, chat_id, message_id, course_id, question, missed_material_id, note, grounding)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (user_id, data.get('chat_id'), data.get('message_id'), data.get('course_id'),
                 sanitize_string(data.get('question', ''), max_length=4000),
                 data.get('missed_material_id'),
                 sanitize_string(data.get('note', ''), max_length=2000),
                 json.dumps(data.get('grounding')) if data.get('grounding') is not None else None),
            )
        conn.commit()


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        google_id, _ = authenticate_request(self)
        if not google_id:
            send_json(self, 401, {"error": "Unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            send_json(self, 400, {"error": "Invalid request body"})
            return
        ok, err = validate_feedback(data)
        if not ok:
            send_json(self, 400, {"error": err})
            return
        user = User.get_by_google_id(google_id)
        if not user:
            send_json(self, 404, {"error": "User not found"})
            return
        insert_feedback(user["id"], data)
        send_json(self, 201, {"ok": True})
```

Match `get_connection`/CSRF handling to the conventions in `api/sharing.py` (e.g. if other POST
handlers verify a CSRF token via middleware, do the same here).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feedback.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/feedback.py tests/test_feedback.py
git commit -m "feat: add retrieval feedback POST endpoint"
```

---

### Task 3: Thumbs-down + "missed something" popover in chat

**Files:**
- Modify: `src/ChatTab.jsx` (assistant message action row; reuse the `materials` and sources/grounding state)

- [ ] **Step 1: Add a thumbs-down button to the assistant action row**

Next to the existing copy/regenerate controls on an assistant message, add a thumbs-down button that
toggles a small popover for that message id.

- [ ] **Step 2: Build the popover**

```jsx
{feedbackOpenFor === message.id && (
  <div className="mt-2 rounded-lg border border-gray-200 bg-white p-3 shadow-sm text-xs space-y-2">
    <label className="block text-gray-600">Which material did it miss? (optional)</label>
    <select value={missedMaterial} onChange={(e) => setMissedMaterial(e.target.value)}
            className="w-full rounded border border-gray-200 px-2 py-1">
      <option value="">— none —</option>
      {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
    </select>
    <textarea value={feedbackNote} onChange={(e) => setFeedbackNote(e.target.value)}
              placeholder="What was missing?" className="w-full rounded border border-gray-200 px-2 py-1" />
    <button onClick={() => submitFeedback(message)} className="rounded bg-indigo-600 px-3 py-1 text-white">Send feedback</button>
  </div>
)}
```

Add state: `feedbackOpenFor`, `missedMaterial`, `feedbackNote`.

- [ ] **Step 3: Implement `submitFeedback`**

```jsx
async function submitFeedback(message) {
  const question = findPrecedingUserMessage(message);   // the user turn this answer replied to
  await fetch('/api/feedback', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({
      chat_id: activeConv,
      message_id: message.id,
      course_id: course?.id,
      question,
      missed_material_id: missedMaterial ? Number(missedMaterial) : null,
      note: feedbackNote || null,
      grounding: message.grounding || message.sources || null,
    }),
  });
  setFeedbackOpenFor(null); setMissedMaterial(''); setFeedbackNote('');
}
```

`findPrecedingUserMessage` walks `messages` for the nearest earlier `role === 'user'` entry. Use the
component's existing CSRF token variable and the grounding/sources field name already used by the
sources panel (search `sourcesPanel`/`grounding`).

- [ ] **Step 4: Manually verify**

Run: `npm run dev`. Thumbs-down an answer, choose a material, add a note, send → confirm a row in
`retrieval_feedback` with the question + grounding snapshot.

- [ ] **Step 5: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat: add 'it missed something' retrieval feedback to chat"
```

---

## Self-Review

- **Spec coverage:** table (T1), endpoint + ownership-safe insert (T2), thumbs-down popover with
  optional material/note + grounding snapshot (T3). ✓
- **Type consistency:** `validate_feedback(data) -> (bool, err)` and `insert_feedback(user_id, data)`
  match between handler and test; frontend payload keys match the SQL columns. ✓
- **Caveats surfaced:** confirm the `chats` table name (T1) and match CSRF/grounding field names to
  existing conventions (T2–T3). ✓
