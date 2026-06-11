# Study Planner / Mastery Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggregate existing quiz-attempt results into per-topic mastery, surface weak topics worst-first, and let the student jump straight into a targeted generation.

**Architecture:** Pure `mastery_by_topic` aggregator over a single SQL join of existing attempt tables; a `mastery` read endpoint; a WeakTopics widget that pre-fills the existing quiz/flashcards generation form. No schema change.

**Tech Stack:** Python serverless, Neon Postgres, pytest, React.

**Spec:** `docs/superpowers/specs/2026-06-10-mastery-tracking-design.md`

---

### Task 1: Pure mastery aggregator

**Files:**
- Create: `api/services/mastery.py`
- Test: `tests/test_mastery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mastery.py
from api.services.mastery import mastery_by_topic

def test_worst_first_ordering():
    rows = [('EKF', False), ('EKF', False), ('EKF', True),
            ('SLAM', True), ('SLAM', True)]
    out = mastery_by_topic(rows)
    assert out[0]['topic'] == 'EKF'
    assert out[0]['accuracy'] == round(1/3, 3)
    assert out[-1]['topic'] == 'SLAM' and out[-1]['accuracy'] == 1.0

def test_none_topic_becomes_general():
    out = mastery_by_topic([(None, True), (None, False)])
    assert out[0]['topic'] == 'General' and out[0]['attempted'] == 2

def test_empty():
    assert mastery_by_topic([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mastery.py -v` — FAIL.

- [ ] **Step 3: Implement** (function body from the spec into `api/services/mastery.py`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mastery.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/mastery.py tests/test_mastery.py
git commit -m "feat: add pure mastery-by-topic aggregator"
```

---

### Task 2: `mastery` read endpoint

**Files:**
- Modify: `api/quiz.py` (add GET `action=mastery`; import aggregator)
- Test: `tests/test_quiz_mastery.py`

- [ ] **Step 1: Confirm the join columns**

Run: `rg -n "quiz_attempt_answers|quiz_questions|quiz_generations|topic|is_correct" api/quiz.py migrations | head -20`
Confirm the real table/column names linking an answer → its question → its generation → `topic` and
`course_id`, and how attempts are scoped to a user. Build the join from those.

- [ ] **Step 2: Write the failing test (SQL builder)**

```python
# tests/test_quiz_mastery.py
from api.quiz import mastery_query_sql

def test_mastery_query_joins_and_filters():
    sql = mastery_query_sql().lower()
    assert 'quiz_attempt_answers' in sql
    assert 'is_correct' in sql
    assert 'topic' in sql
    assert 'course_id' in sql
```

- [ ] **Step 3: Run → FAIL**, then implement `mastery_query_sql()` returning the join (adjust names to
the confirmed schema), and an `_mastery` handler:

```python
def mastery_query_sql() -> str:
    return (
        "SELECT g.topic AS topic, a.is_correct AS is_correct "
        "FROM quiz_attempt_answers a "
        "JOIN quiz_attempts at ON at.id = a.attempt_id "
        "JOIN quiz_questions q ON q.id = a.question_id "
        "JOIN quiz_generations g ON g.id = q.generation_id "
        "WHERE g.course_id = %s AND at.user_id = %s"
    )

def _mastery(self, params, user):
    course_id = int(params.get('course_id'))      # match this file's param parsing
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(mastery_query_sql(), (course_id, user['id']))
            rows = cur.fetchall()
    from .services.mastery import mastery_by_topic
    send_json(self, 200, {"topics": mastery_by_topic([(r[0], r[1]) for r in rows])})
```

Wire `action == 'mastery'` into the GET dispatch. Match `get_db_connection`/param parsing to the
file's conventions.

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit**

```bash
git add api/quiz.py tests/test_quiz_mastery.py
git commit -m "feat: add quiz mastery-by-topic endpoint"
```

---

### Task 3: Weak topics widget + "Drill this"

**Files:**
- Create: `src/components/WeakTopicsWidget.jsx`
- Modify: `src/Dashboard.jsx` or `src/CoursePage.jsx` (render it); `src/Quiz.jsx` / `src/Flashcards.jsx` (accept a pre-filled topic)

- [ ] **Step 1: Build the widget**

```jsx
// src/components/WeakTopicsWidget.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function WeakTopicsWidget({ courseId }) {
  const [topics, setTopics] = useState([]);
  const navigate = useNavigate();
  useEffect(() => {
    fetch(`/api/quiz?action=mastery&course_id=${courseId}`, { credentials: 'include' })
      .then((r) => r.json()).then((d) => setTopics(d.topics || [])).catch(() => {});
  }, [courseId]);
  if (!topics.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <h3 className="text-sm font-semibold mb-2">Weak topics</h3>
      {topics.slice(0, 5).map((t) => (
        <div key={t.topic} className="flex items-center justify-between py-1 text-sm">
          <span>{t.topic} <span className="text-gray-400">{Math.round(t.accuracy * 100)}%</span></span>
          <button
            onClick={() => navigate(`/course/${courseId}?drill=${encodeURIComponent(t.topic)}`)}
            className="text-xs text-indigo-600 hover:underline"
          >Drill this</button>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Pre-fill the generation form from the `drill` param**

In `src/Quiz.jsx` / `src/Flashcards.jsx`, read a `drill` query param (or routed state) on mount and
seed the existing topic input (the topic `<input>` at `src/Quiz.jsx:797` / `src/Flashcards.jsx:778`).

- [ ] **Step 3: Render the widget**

Add `<WeakTopicsWidget courseId={course.id} />` to the course page (and/or dashboard).

- [ ] **Step 4: Manually verify**

Run: `npm run dev`. Take quizzes with mixed results → weak topics list worst-first; "Drill this"
opens the generation form with the topic pre-filled.

- [ ] **Step 5: Commit**

```bash
git add src/components/WeakTopicsWidget.jsx src/CoursePage.jsx src/Quiz.jsx src/Flashcards.jsx
git commit -m "feat: weak-topics widget that drills into targeted generation"
```

---

## Self-Review

- **Spec coverage:** aggregator (T1), endpoint over existing attempt tables (T2), widget + drill
  pre-fill (T3). ✓
- **No new write path:** purely a read-model + navigation; the only risk is schema-name drift, which
  T2 step 1 forces the engineer to confirm before writing SQL. ✓
- **Type consistency:** `mastery_by_topic(rows) -> [{topic, attempted, correct, accuracy}]` used
  identically by endpoint and widget. ✓
