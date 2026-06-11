# Per-Course Model Default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each course remember a default AI provider/model, used to seed the chat model selector when the user has no explicit choice.

**Architecture:** Add nullable `default_ai_provider`/`default_ai_model` columns to `courses`, expose them on course read/update, and have `ChatTab` use the course default as the initial selection when `localStorage` has no override.

**Tech Stack:** PostgreSQL, `api/course.py`, `src/ChatTab.jsx` (+ course settings UI), pytest.

**Spec:** Roadmap P2. Confirmed unbuilt: `courses` has no default-model columns; chat selection is global `localStorage` only (`chat_selected_provider`/`chat_selected_model_id`).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| DB `courses` | Store course default provider/model | Migration |
| `api/course.py` | Read/update default fields | Modify |
| `src/ChatTab.jsx` | Seed selection from course default | Modify |
| course settings UI (where course is edited) | Pick the default | Modify |

---

## Task 1: Migration

- [ ] **Step 1: Run the migration SQL**

```sql
ALTER TABLE courses ADD COLUMN IF NOT EXISTS default_ai_provider TEXT;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS default_ai_model   TEXT;
```

- [ ] **Step 2: Verify**

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='courses' AND column_name LIKE 'default_ai%';
```
Expected: two rows.

---

## Task 2: Backend — expose + persist the fields

**Files:**
- Modify: `api/course.py` (course serialization; the update handler)
- Test: `tests/test_course_default_model.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

def test_course_default_model_update_payload():
    from course import _extract_default_model_fields  # to add
    out = _extract_default_model_fields({"default_ai_provider": "claude", "default_ai_model": "claude-sonnet-4-6"})
    assert out == ("claude", "claude-sonnet-4-6")
    assert _extract_default_model_fields({}) == (None, None)
    assert _extract_default_model_fields({"default_ai_provider": "  "}) == (None, None)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_course_default_model.py -v`
Expected: FAIL — missing helper.

- [ ] **Step 3: Implement**

In `api/course.py`:

```python
def _extract_default_model_fields(body: dict) -> tuple:
    p = (body.get('default_ai_provider') or '').strip() or None
    m = (body.get('default_ai_model') or '').strip() or None
    return (p, m)
```

- Include `default_ai_provider`, `default_ai_model` in the course SELECT/serialization so they are returned on course read.
- In the course update handler, call `_extract_default_model_fields(body)` and `UPDATE courses SET default_ai_provider=%s, default_ai_model=%s WHERE id=%s` (only when the keys are present in the payload, to avoid clobbering on unrelated updates).

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_course_default_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/course.py tests/test_course_default_model.py
git commit -m "feat(course): store and expose default AI provider/model"
```

---

## Task 3: Frontend — seed chat selection from course default

**Files:**
- Modify: `src/ChatTab.jsx` (initial model selection, lines ~1471–1520)

- [ ] **Step 1: Use the course default as fallback**

Where the initial provider/model is resolved from `localStorage` (lines ~1471–1472), fall back to the course default when localStorage is empty:

```jsx
const savedProvider = localStorage.getItem('chat_selected_provider')
  || course?.default_ai_provider || DEFAULT_AI_PROVIDER;
const savedModelId = localStorage.getItem('chat_selected_model_id')
  || course?.default_ai_model || null;
```

Precedence: explicit user choice (localStorage) > course default > global default. (Course default seeds, it does not override an explicit pick.)

- [ ] **Step 2: Build check**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(chat): seed model selection from course default"
```

---

## Task 4: Course settings UI to set the default

**Files:**
- Modify: the course edit/settings component (locate it)

- [ ] **Step 1: Locate the course settings form**

Run: `cd /Users/shubhan/OneShotCourseMate && rg -ln "title.*course|updateCourse|/api/course.*update|action.*update.*course|CourseSettings|EditCourse" src/ | head`

- [ ] **Step 2: Add a model picker**

Add a provider/model dropdown (reuse the same `PROVIDER_MODELS` list ChatTab uses) bound to `default_ai_provider`/`default_ai_model`, included in the course update payload. Allow "None (use global default)".

- [ ] **Step 3: Build + manual check**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Set a course default → enter that course's chat with cleared localStorage → selector starts on the course default.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(course): UI to set default AI model"
```

---

## Self-Review Notes

- **Spec coverage:** per-course default stored (Tasks 1–2) ✓; used as chat default (Task 3) ✓; settable in UI (Task 4) ✓.
- **Precedence is explicit:** localStorage > course default > global — avoids surprising override of a user's deliberate pick.
- **YAGNI:** no per-course generation-model default (chat only), no migration backfill (nullable).
```
