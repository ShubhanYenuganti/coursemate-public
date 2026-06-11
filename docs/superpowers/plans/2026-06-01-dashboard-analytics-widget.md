# Dashboard Analytics Widget — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show per-course usage at a glance: materials processed, generations by type (quiz/flashcard/report), and chat activity.

**Architecture:** One read-only stats endpoint runs a few `COUNT` queries scoped to a course; a small widget renders the numbers on the course page.

**Tech Stack:** PostgreSQL `COUNT`, `api/course.py`, React widget, pytest.

**Spec:** Roadmap P2. Confirmed unbuilt: `Dashboard.jsx` is the course-list landing page with no stat widgets; no stats endpoint exists. Data all lives in existing tables.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `api/course.py` | `action=stats` → per-course counts | Modify |
| `src/components/CourseStatsWidget.jsx` | Render the numbers | Create |
| `src/CoursePage.jsx` | Mount the widget | Modify |
| `tests/test_course_stats.py` | Endpoint shape test | Create |

---

## Task 1: Backend — per-course stats endpoint

**Files:**
- Modify: `api/course.py` (GET routing; add `_course_stats`)
- Test: `tests/test_course_stats.py` (Create)

> Confirm exact generation table names first: `cd /Users/shubhan/OneShotCourseMate && rg -n "INSERT INTO .*_generations|FROM .*_generations" api | sort -u`.

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

def test_stats_payload_shape():
    from course import _shape_stats
    out = _shape_stats(materials=12, quizzes=3, flashcards=5, reports=2, chats=7, messages=88)
    assert out == {
        "materials": 12,
        "generations": {"quiz": 3, "flashcards": 5, "reports": 2, "total": 10},
        "chats": 7,
        "messages": 88,
    }
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_course_stats.py -v`
Expected: FAIL — missing `_shape_stats`.

- [ ] **Step 3: Implement the shaper + endpoint**

In `api/course.py`:

```python
def _shape_stats(materials, quizzes, flashcards, reports, chats, messages) -> dict:
    return {
        "materials": materials,
        "generations": {
            "quiz": quizzes, "flashcards": flashcards, "reports": reports,
            "total": quizzes + flashcards + reports,
        },
        "chats": chats,
        "messages": messages,
    }
```

Add a GET handler `action=stats&course_id=<id>` that (after `Course.verify_access`) runs counts and returns `_shape_stats(...)`:

```python
def _course_stats(self, params, user):
    course_id = int(params.get('course_id', [0])[0])
    if not Course.verify_access(course_id, user['id']):
        send_json(self, 403, {"error": "Access denied"}); return
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM materials WHERE id = ANY(SELECT jsonb_array_elements_text(material_ids)::int FROM courses WHERE id=%s)", (course_id,))
        materials = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM quiz_generations WHERE course_id=%s", (course_id,)); quizzes = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM flashcard_generations WHERE course_id=%s", (course_id,)); flashcards = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM report_generations WHERE course_id=%s", (course_id,)); reports = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM chats WHERE course_id=%s", (course_id,)); chats = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM chat_messages cm JOIN chats c ON c.id=cm.chat_id WHERE c.course_id=%s AND cm.is_deleted=FALSE", (course_id,)); messages = cur.fetchone()["n"]
        cur.close()
    send_json(self, 200, _shape_stats(materials, quizzes, flashcards, reports, chats, messages))
```

Adjust table names per the confirming grep. Route `action == 'stats'` to `_course_stats`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_course_stats.py -v`
Expected: PASS

- [ ] **Step 5: Manual smoke**

`GET /api/course?action=stats&course_id=<id>` → JSON with `materials`, `generations.{quiz,flashcards,reports,total}`, `chats`, `messages`.

- [ ] **Step 6: Commit**

```bash
git add api/course.py tests/test_course_stats.py
git commit -m "feat(course): per-course stats endpoint"
```

---

## Task 2: Frontend — stats widget

**Files:**
- Create: `src/components/CourseStatsWidget.jsx`
- Modify: `src/CoursePage.jsx`

- [ ] **Step 1: Create the widget**

```jsx
import React, { useEffect, useState } from 'react';

function Stat({ label, value }) {
  return (
    <div className="flex flex-col items-center px-4 py-3">
      <span className="text-2xl font-semibold text-gray-900 tabular-nums">{value}</span>
      <span className="text-[11px] text-gray-500 uppercase tracking-wide">{label}</span>
    </div>
  );
}

export default function CourseStatsWidget({ courseId }) {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    if (!courseId) return;
    fetch(`/api/course?action=stats&course_id=${courseId}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .catch(() => {});
  }, [courseId]);
  if (!stats) return null;
  return (
    <div className="flex flex-wrap items-center divide-x divide-gray-100 rounded-xl border border-gray-100 bg-white/70">
      <Stat label="Materials" value={stats.materials} />
      <Stat label="Generations" value={stats.generations.total} />
      <Stat label="Chats" value={stats.chats} />
      <Stat label="Messages" value={stats.messages} />
    </div>
  );
}
```

- [ ] **Step 2: Mount it on the course page**

In `src/CoursePage.jsx`, render `<CourseStatsWidget courseId={course.id} />` in the course header/overview area. Locate a mount point:
`cd /Users/shubhan/OneShotCourseMate && rg -n "course.id|course\\.title|header|overview" src/CoursePage.jsx | head`

- [ ] **Step 3: Build + manual check**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Open a course → widget shows the four counts.

- [ ] **Step 4: Commit**

```bash
git add src/components/CourseStatsWidget.jsx src/CoursePage.jsx
git commit -m "feat(course): course stats widget"
```

---

## Self-Review Notes

- **Spec coverage:** materials processed (Task 1) ✓; generation counts by type (Task 1) ✓; chat activity (Task 1) ✓; widget surface (Task 2) ✓.
- **YAGNI:** counts only — no time-series charts, no cross-course rollup. Read-only.
- **Soft spots (grep steps):** exact generation table names (Task 1) and the materials-count query (depends on whether course→materials is via `courses.material_ids` JSONB or a `materials.course_id` FK — verify and use whichever exists).
```
