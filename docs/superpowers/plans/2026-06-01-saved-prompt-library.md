# Saved Prompt Library — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save reusable prompts and insert them into the chat compose box with one click.

**Architecture:** A user-scoped `saved_prompts` table, a small CRUD endpoint, and a compose-bar picker that inserts the selected prompt text into the chat input.

**Tech Stack:** PostgreSQL, a new `api/prompts.py` handler, React (`src/ChatTab.jsx` + a picker component), pytest.

**Spec:** Roadmap P3. Confirmed unbuilt (no `saved_prompt*` references anywhere).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| DB `saved_prompts` | Persist user prompts | Migration |
| `api/prompts.py` | List / create / delete | Create |
| `src/components/PromptLibrary.jsx` | Picker + manage UI | Create |
| `src/ChatTab.jsx` | Open picker; insert into compose | Modify |
| `tests/test_prompts.py` | Handler validation test | Create |

---

## Task 1: Migration

- [ ] **Step 1: Run the migration SQL**

```sql
CREATE TABLE IF NOT EXISTS saved_prompts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_saved_prompts_user ON saved_prompts(user_id, created_at DESC);
```

- [ ] **Step 2: Verify**

```sql
SELECT COUNT(*) FROM saved_prompts;
```
Expected: `0` (table exists).

---

## Task 2: Backend — prompts CRUD

**Files:**
- Create: `api/prompts.py` (follow the pattern of an existing simple handler, e.g. the GET/POST/DELETE shape used in `api/course.py`)
- Test: `tests/test_prompts.py` (Create)

> First read a sibling handler for the auth + routing pattern: `cd /Users/shubhan/OneShotCourseMate && sed -n '1,40p' api/course.py` (authenticate_request, User lookup, send_json).

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

def test_validate_prompt_payload():
    from prompts import _validate_prompt
    assert _validate_prompt({"title": "Summarize", "body": "Summarize this lecture"}) == ("Summarize", "Summarize this lecture")
    err1 = None
    try:
        _validate_prompt({"title": "", "body": "x"})
    except ValueError as e:
        err1 = str(e)
    assert err1 and "title" in err1.lower()
    err2 = None
    try:
        _validate_prompt({"title": "t", "body": "  "})
    except ValueError as e:
        err2 = str(e)
    assert err2 and "body" in err2.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_prompts.py -v`
Expected: FAIL — module/function missing.

- [ ] **Step 3: Implement the handler**

`api/prompts.py` — endpoints:
- `GET  /api/prompts` → list the authed user's prompts (newest first).
- `POST /api/prompts` `{title, body}` → create, return the row.
- `DELETE /api/prompts?id=<id>` → delete if owned by user.

Include the validator:

```python
def _validate_prompt(body: dict) -> tuple:
    title = (body.get('title') or '').strip()
    text = (body.get('body') or '').strip()
    if not title:
        raise ValueError("title is required")
    if not text:
        raise ValueError("body is required")
    return (title, text)
```

Mirror the auth/`send_json` pattern from `api/course.py`. Queries:
`INSERT INTO saved_prompts (user_id, title, body) VALUES (%s,%s,%s) RETURNING id, title, body, created_at`;
`SELECT id, title, body, created_at FROM saved_prompts WHERE user_id=%s ORDER BY created_at DESC`;
`DELETE FROM saved_prompts WHERE id=%s AND user_id=%s`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_prompts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/prompts.py tests/test_prompts.py
git commit -m "feat(prompts): saved prompt library CRUD endpoint"
```

---

## Task 3: Frontend — picker + insert into compose

**Files:**
- Create: `src/components/PromptLibrary.jsx`
- Modify: `src/ChatTab.jsx`

- [ ] **Step 1: Create the picker component**

`src/components/PromptLibrary.jsx`: a small popover that lists prompts (fetched from `/api/prompts`), with a "＋ New" form (title + body), a delete (×) per row, and an `onInsert(body)` callback when a prompt is clicked.

```jsx
import React, { useEffect, useState } from 'react';

export default function PromptLibrary({ onInsert, onClose }) {
  const [prompts, setPrompts] = useState([]);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');

  const load = () => fetch('/api/prompts', { credentials: 'include' })
    .then((r) => r.ok ? r.json() : []).then(setPrompts).catch(() => {});
  useEffect(() => { load(); }, []);

  async function create() {
    if (!title.trim() || !body.trim()) return;
    await fetch('/api/prompts', { method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, body }) });
    setTitle(''); setBody(''); load();
  }
  async function remove(id) {
    await fetch(`/api/prompts?id=${id}`, { method: 'DELETE', credentials: 'include' });
    load();
  }

  return (
    <div className="absolute bottom-14 left-0 w-80 max-h-96 overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg p-3 z-30">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-500 uppercase">Saved Prompts</span>
        <button type="button" onClick={onClose} className="text-gray-400">✕</button>
      </div>
      {prompts.map((p) => (
        <div key={p.id} className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-indigo-50">
          <button type="button" className="flex-1 text-left" onClick={() => { onInsert(p.body); onClose(); }}>
            <div className="text-sm text-gray-800">{p.title}</div>
            <div className="text-[11px] text-gray-400 truncate">{p.body}</div>
          </button>
          <button type="button" onClick={() => remove(p.id)} className="text-gray-300 hover:text-rose-500">×</button>
        </div>
      ))}
      <div className="mt-2 border-t border-gray-100 pt-2 space-y-1">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title"
          className="w-full text-sm border border-gray-200 rounded px-2 py-1" />
        <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Prompt text"
          className="w-full text-sm border border-gray-200 rounded px-2 py-1" rows={2} />
        <button type="button" onClick={create}
          className="w-full text-sm bg-indigo-600 text-white rounded py-1">Save prompt</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into ChatTab compose**

In `src/ChatTab.jsx`: add `const [promptLibOpen, setPromptLibOpen] = useState(false);`, a compose-bar button to toggle it, and render `<PromptLibrary onInsert={(text) => setInput((v) => v ? `${v}\n${text}` : text)} onClose={() => setPromptLibOpen(false)} />` when open. Use the actual compose input setter name — confirm with:
`cd /Users/shubhan/OneShotCourseMate && rg -n "useState\\(''\\)|setInput|const \\[input|composeValue|message, setMessage" src/ChatTab.jsx | head`

- [ ] **Step 3: Build + manual check**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Save a prompt → reopen picker → click it → text appears in the compose box → delete it → it's gone.

- [ ] **Step 4: Commit**

```bash
git add src/components/PromptLibrary.jsx src/ChatTab.jsx
git commit -m "feat(prompts): compose-bar prompt library picker"
```

---

## Self-Review Notes

- **Spec coverage:** save prompts (Tasks 1–2) ✓; insert into compose (Task 3) ✓; manage/delete (Tasks 2–3) ✓.
- **YAGNI:** user-scoped only (no course scoping, no sharing, no variables/placeholders). Add later if needed.
- **Soft spot (grep step):** the compose input state setter name in ChatTab (Task 3 Step 2).
- **Pattern reuse:** `api/prompts.py` follows the existing handler auth/routing pattern (read `api/course.py` first) rather than inventing a new one.
```
