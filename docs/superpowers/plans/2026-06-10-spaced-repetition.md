# Server-Side Ratings + Spaced Repetition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist flashcard ratings server-side and schedule each card's next review with SM-2, surfacing a "Due today" loop on the dashboard.

**Architecture:** Pure SM-2 scheduler (`api/services/spaced_repetition.py`) drives a new `flashcard_reviews` table via `rate`/`due` actions in `api/flashcards.py`. `FlashcardViewer` writes through to the API (replacing localStorage); a `DueTodayWidget` reads the due summary on the dashboard.

**Tech Stack:** Python serverless, Neon Postgres, pytest, React, vitest.

**Spec:** `docs/superpowers/specs/2026-06-10-spaced-repetition-design.md`

---

### Task 1: Pure SM-2 scheduler

**Files:**
- Create: `api/services/spaced_repetition.py`
- Test: `tests/test_spaced_repetition.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spaced_repetition.py
from api.services.spaced_repetition import schedule, ReviewState, INITIAL, THUMB_TO_QUALITY

def test_down_resets_to_one_day():
    s = schedule(ReviewState(repetitions=5, interval_days=40, ease=2.6), quality=2)
    assert s.repetitions == 0
    assert s.interval_days == 1

def test_first_two_intervals_are_fixed():
    s1 = schedule(INITIAL, quality=4)
    assert s1.repetitions == 1 and s1.interval_days == 1
    s2 = schedule(s1, quality=4)
    assert s2.repetitions == 2 and s2.interval_days == 6

def test_third_interval_uses_ease():
    s = schedule(ReviewState(repetitions=2, interval_days=6, ease=2.5), quality=4)
    assert s.repetitions == 3
    assert s.interval_days == round(6 * s.ease)

def test_ease_never_below_floor():
    s = INITIAL
    for _ in range(10):
        s = schedule(s, quality=0)
    assert s.ease >= 1.3

def test_thumb_mapping():
    assert THUMB_TO_QUALITY['down'] < 3 <= THUMB_TO_QUALITY['up']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_spaced_repetition.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the scheduler**

```python
# api/services/spaced_repetition.py
from dataclasses import dataclass

@dataclass
class ReviewState:
    repetitions: int
    interval_days: int
    ease: float

def schedule(prev: ReviewState, quality: int) -> ReviewState:
    """SM-2. quality in 0..5; quality < 3 resets repetitions and interval."""
    ease = max(1.3, prev.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    if quality < 3:
        return ReviewState(repetitions=0, interval_days=1, ease=ease)
    reps = prev.repetitions + 1
    if reps == 1:
        interval = 1
    elif reps == 2:
        interval = 6
    else:
        interval = round(prev.interval_days * ease)
    return ReviewState(repetitions=reps, interval_days=interval, ease=ease)

INITIAL = ReviewState(repetitions=0, interval_days=0, ease=2.5)
THUMB_TO_QUALITY = {"down": 2, "up": 4}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_spaced_repetition.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add api/services/spaced_repetition.py tests/test_spaced_repetition.py
git commit -m "feat: add pure SM-2 spaced-repetition scheduler"
```

---

### Task 2: Database migration

**Files:**
- Create: `migrations/011_flashcard_reviews.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 011_flashcard_reviews.sql — per-user spaced-repetition state for flashcards.
CREATE TABLE IF NOT EXISTS flashcard_reviews (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_id INTEGER NOT NULL,
    card_index    INTEGER NOT NULL,
    last_rating   TEXT,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease          REAL    NOT NULL DEFAULT 2.5,
    due_at        TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, generation_id, card_index)
);

CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_due ON flashcard_reviews (user_id, due_at);
```

- [ ] **Step 2: Apply against the dev database**

Run: `psql "$DATABASE_URL" -f migrations/011_flashcard_reviews.sql`
Expected: `CREATE TABLE`, `CREATE INDEX`.

- [ ] **Step 3: Commit**

```bash
git add migrations/011_flashcard_reviews.sql
git commit -m "feat: add flashcard_reviews table"
```

---

### Task 3: `rate` action — persist + schedule

**Files:**
- Modify: `api/flashcards.py` (POST dispatch ~line 353; add `_rate`; import scheduler)
- Test: `tests/test_flashcards_rate.py`

- [ ] **Step 1: Write the failing test (pure compute helper)**

Extract the scheduling-from-prior-row math into a testable helper so the DB is not needed:

```python
# tests/test_flashcards_rate.py
from api.flashcards import compute_next_review

def test_compute_next_review_advances_on_up():
    prev = {'repetitions': 0, 'interval_days': 0, 'ease': 2.5}
    nxt = compute_next_review(prev, 'up')
    assert nxt['repetitions'] == 1
    assert nxt['interval_days'] == 1
    assert nxt['ease'] >= 2.5

def test_compute_next_review_resets_on_down():
    prev = {'repetitions': 4, 'interval_days': 30, 'ease': 2.6}
    nxt = compute_next_review(prev, 'down')
    assert nxt['repetitions'] == 0
    assert nxt['interval_days'] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_flashcards_rate.py -v`
Expected: FAIL — `cannot import name 'compute_next_review'`.

- [ ] **Step 3: Implement helper + action**

Add the import (both try/except branches at top of `api/flashcards.py`):

```python
from .services.spaced_repetition import schedule, ReviewState, INITIAL, THUMB_TO_QUALITY
# and: from services.spaced_repetition import ...
```

Add the pure helper:

```python
def compute_next_review(prev: dict, rating: str) -> dict:
    state = ReviewState(
        repetitions=prev.get('repetitions', 0),
        interval_days=prev.get('interval_days', 0),
        ease=prev.get('ease', 2.5),
    ) if prev else INITIAL
    quality = THUMB_TO_QUALITY.get(rating, 4)
    nxt = schedule(state, quality)
    return {'repetitions': nxt.repetitions, 'interval_days': nxt.interval_days, 'ease': nxt.ease}
```

Add `_rate` to the handler and wire it into the POST dispatch next to the other `elif action ==`
branches (around line 353):

```python
elif action == 'rate':
    self._rate(body, user)
```

```python
def _rate(self, body: dict, user: dict):
    generation_id = body.get('generation_id')
    card_index = body.get('card_index')
    rating = body.get('rating')
    if not isinstance(generation_id, int) or not isinstance(card_index, int) or rating not in ('up', 'down'):
        send_json(self, 400, {"error": "generation_id, card_index, rating required"})
        return
    with get_db_connection() as conn:          # match the helper this file already uses
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT repetitions, interval_days, ease FROM flashcard_reviews
                   WHERE user_id=%s AND generation_id=%s AND card_index=%s""",
                (user['id'], generation_id, card_index),
            )
            prev = cur.fetchone()
            nxt = compute_next_review(prev, rating)
            cur.execute(
                """INSERT INTO flashcard_reviews
                     (user_id, generation_id, card_index, last_rating, repetitions, interval_days, ease, due_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s, now() + (%s || ' days')::interval, now())
                   ON CONFLICT (user_id, generation_id, card_index) DO UPDATE SET
                     last_rating=EXCLUDED.last_rating, repetitions=EXCLUDED.repetitions,
                     interval_days=EXCLUDED.interval_days, ease=EXCLUDED.ease,
                     due_at=EXCLUDED.due_at, updated_at=now()
                   RETURNING due_at""",
                (user['id'], generation_id, card_index, rating,
                 nxt['repetitions'], nxt['interval_days'], nxt['ease'], nxt['interval_days']),
            )
            due_at = cur.fetchone()['due_at']
        conn.commit()
    send_json(self, 200, {**nxt, "due_at": due_at.isoformat()})
```

Match the DB connection helper (`get_db_connection`/`dict_row`) to what `api/flashcards.py` already
imports at the top — do not introduce a new one.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_flashcards_rate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/flashcards.py tests/test_flashcards_rate.py
git commit -m "feat: persist flashcard ratings and schedule reviews via SM-2"
```

---

### Task 4: `due` summary + `ratings` load

**Files:**
- Modify: `api/flashcards.py` (GET dispatch ~line 271; add `_due`, `_ratings`)
- Test: `tests/test_flashcards_due.py`

- [ ] **Step 1: Write the failing test (SQL shape via a query builder)**

Extract the due query into a pure builder so it's testable without a DB:

```python
# tests/test_flashcards_due.py
from api.flashcards import due_summary_sql

def test_due_summary_sql_filters_by_user_and_now():
    sql = due_summary_sql()
    low = sql.lower()
    assert 'flashcard_reviews' in low
    assert 'due_at <= now()' in low
    assert 'user_id = %s' in low
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_flashcards_due.py -v`
Expected: FAIL — `cannot import name 'due_summary_sql'`.

- [ ] **Step 3: Implement builder + actions**

```python
def due_summary_sql() -> str:
    # Joins reviews → generations → courses for a deep link to the most-due generation.
    return (
        "SELECT r.generation_id, g.course_id, COUNT(*) OVER () AS due_count "
        "FROM flashcard_reviews r "
        "JOIN flashcard_generations g ON g.id = r.generation_id "      # match real generations table name
        "WHERE r.user_id = %s AND r.due_at <= now() "
        "ORDER BY r.due_at ASC LIMIT 1"
    )
```

> Confirm the generations table/column names against `_load_generation_from_db` in this file
> (search for `FROM ` near line 226) and adjust `flashcard_generations`/`g.course_id` to match.

Add GET dispatch branches near line 271:

```python
elif action == 'due':
    self._due(params, user)
elif action == 'ratings':
    self._ratings(params, user)
```

```python
def _due(self, params: dict, user: dict):
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(due_summary_sql(), (user['id'],))
            row = cur.fetchone()
    if not row:
        send_json(self, 200, {"due_count": 0, "next": None})
        return
    send_json(self, 200, {
        "due_count": row["due_count"],
        "next": {"generation_id": row["generation_id"], "course_id": row["course_id"]},
    })

def _ratings(self, params: dict, user: dict):
    generation_id = int(params.get('generation_id', [0])[0]) if isinstance(params.get('generation_id'), list) else int(params.get('generation_id', 0))
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT card_index, last_rating FROM flashcard_reviews WHERE user_id=%s AND generation_id=%s",
                (user['id'], generation_id),
            )
            rows = cur.fetchall()
    send_json(self, 200, {"ratings": {str(r["card_index"]): r["last_rating"] for r in rows}})
```

Match `params` parsing to how other GET handlers in this file read query params.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_flashcards_due.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/flashcards.py tests/test_flashcards_due.py
git commit -m "feat: add flashcard due-summary and ratings load endpoints"
```

---

### Task 5: FlashcardViewer writes through to the server

**Files:**
- Modify: `src/FlashcardViewer.jsx` (replace `loadRatings`/`setRating` usage at lines 4, 185, 277–279)
- Delete (Task 6): `src/utils/flashcardRatings.js`

- [ ] **Step 1: Load ratings from the server**

Replace the import (line 4) and initial state (line 185). Remove
`import { loadRatings, setRating } ...`. Add:

```jsx
const [ratings, setRatings] = useState({});

useEffect(() => {
  if (!generationId) return;
  fetch(`/api/flashcards?action=ratings&generation_id=${generationId}`, { credentials: 'include' })
    .then((r) => r.json())
    .then((data) => setRatings(data.ratings || {}))
    .catch(() => {});
}, [generationId]);
```

Note the existing code keys ratings by numeric `currentIndex`; the server returns string keys.
Read them with `ratings[currentIndex]` AND `ratings[String(currentIndex)]`, or normalize to strings
on set (below) for consistency.

- [ ] **Step 2: Write through on thumb click**

Replace the `setRating(...)` call (lines 277–279) with an optimistic update + POST:

```jsx
function rate(value) {
  const next = ratings[currentIndex] === value ? null : value;
  setRatings((prev) => ({ ...prev, [currentIndex]: next }));
  if (next == null) return;     // un-rating: leave server state as-is for v1
  fetch('/api/flashcards', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ action: 'rate', generation_id: generationId, card_index: currentIndex, rating: next }),
  }).catch(() => {});
}
```

Wire the two thumb buttons (lines 598/606 and 652/660) to call `rate('up')` / `rate('down')`.
Use this component's existing CSRF token variable (search `X-CSRF-Token` usage in the file or props).

- [ ] **Step 3: Manually verify persistence**

Run: `npm run dev`. Rate cards, hard-refresh → ratings persist; open in a second browser logged in
as the same user → same ratings appear.

- [ ] **Step 4: Commit**

```bash
git add src/FlashcardViewer.jsx
git commit -m "feat: flashcard ratings persist server-side via rate action"
```

---

### Task 6: Remove the localStorage helper

**Files:**
- Delete: `src/utils/flashcardRatings.js`

- [ ] **Step 1: Confirm no remaining importers**

Run: `rg -n "flashcardRatings" src`
Expected: no matches (FlashcardViewer no longer imports it after Task 5).

- [ ] **Step 2: Delete the file**

Run: `git rm src/utils/flashcardRatings.js`

- [ ] **Step 3: Build to confirm nothing breaks**

Run: `npm run build`
Expected: success.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove localStorage flashcard ratings helper"
```

---

### Task 7: "Due today" dashboard widget

**Files:**
- Create: `src/components/DueTodayWidget.jsx`
- Modify: `src/Dashboard.jsx` (render the widget)

- [ ] **Step 1: Build the widget**

```jsx
// src/components/DueTodayWidget.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function DueTodayWidget() {
  const [due, setDue] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetch('/api/flashcards?action=due', { credentials: 'include' })
      .then((r) => r.json())
      .then(setDue)
      .catch(() => {});
  }, []);

  if (!due || !due.due_count) return null;

  return (
    <button
      onClick={() => due.next && navigate(`/course/${due.next.course_id}/flashcards/${due.next.generation_id}`)}
      className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-left hover:bg-indigo-100 transition-colors"
    >
      <div className="text-2xl font-bold text-indigo-700">{due.due_count}</div>
      <div className="text-xs text-indigo-600">cards due today — review now</div>
    </button>
  );
}
```

- [ ] **Step 2: Render it on the dashboard**

In `src/Dashboard.jsx`, import and place `<DueTodayWidget />` near the top of the dashboard body
(above the course grid):

```jsx
import DueTodayWidget from './components/DueTodayWidget';
// ...inside the returned JSX, near the header:
<DueTodayWidget />
```

- [ ] **Step 3: Manually verify**

Run: `npm run dev`. Rate cards `down` (due tomorrow) and confirm widget hides when nothing is due;
backdate a `due_at` in the DB to `now()` and confirm the widget shows the count and deep-links to
the viewer.

- [ ] **Step 4: Commit**

```bash
git add src/components/DueTodayWidget.jsx src/Dashboard.jsx
git commit -m "feat: add Due Today flashcard widget to dashboard"
```

---

## Self-Review

- **Spec coverage:** SM-2 (T1), schema (T2), rate/persist (T3), due+ratings load (T4), viewer
  write-through (T5), localStorage removal (T6), dashboard widget (T7). ✓
- **Type consistency:** `compute_next_review(prev, rating) -> dict` and `ReviewState` fields
  (`repetitions/interval_days/ease`) used consistently across scheduler, helper, and SQL columns. ✓
- **DB-helper / table-name caveats:** Tasks 3–4 flag matching the file's existing connection helper
  and confirming the real flashcard-generations table name from `_load_generation_from_db`. ✓
- **No placeholders:** SQL, Python, and JSX shown in full. ✓
