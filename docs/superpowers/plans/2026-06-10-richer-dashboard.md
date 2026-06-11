# Richer Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace inert course counts with engagement metrics — study streak, cards due today, recent quiz score, last synced — degrading gracefully when dependent tables aren't present.

**Architecture:** A pure `current_streak` helper + small guarded queries extend `_shape_stats`; `CourseStatsWidget` renders the new tiles and hides empty ones. Backward-compatible with the existing stats keys.

**Tech Stack:** Python serverless, Neon Postgres, pytest, React.

**Spec:** `docs/superpowers/specs/2026-06-10-richer-dashboard-design.md`

---

### Task 1: Pure streak helper

**Files:**
- Create: `api/services/dashboard_stats.py`
- Test: `tests/test_dashboard_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dashboard_stats.py
from datetime import date
from api.services.dashboard_stats import current_streak

D = date

def test_empty_is_zero():
    assert current_streak(set(), D(2026, 6, 10)) == 0

def test_counts_today_and_back():
    days = {D(2026, 6, 10), D(2026, 6, 9), D(2026, 6, 8)}
    assert current_streak(days, D(2026, 6, 10)) == 3

def test_today_inactive_but_yesterday_keeps_streak():
    days = {D(2026, 6, 9), D(2026, 6, 8)}
    assert current_streak(days, D(2026, 6, 10)) == 2

def test_gap_breaks_streak():
    days = {D(2026, 6, 10), D(2026, 6, 8)}
    assert current_streak(days, D(2026, 6, 10)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_stats.py -v` — FAIL.

- [ ] **Step 3: Implement** (function body from the spec into `api/services/dashboard_stats.py`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_stats.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/dashboard_stats.py tests/test_dashboard_stats.py
git commit -m "feat: add pure current_streak helper"
```

---

### Task 2: Extend the stats endpoint (guarded)

**Files:**
- Modify: `api/course.py` (`_shape_stats` signature + the `action=stats` query block ~line 62)
- Test: `tests/test_course_stats.py` (extend the existing file)

- [ ] **Step 1: Extend the existing stats test**

Add to `tests/test_course_stats.py` an assertion that `_shape_stats` accepts and surfaces the new
fields with safe defaults:

```python
def test_shape_stats_includes_engagement_fields():
    from api.course import _shape_stats
    out = _shape_stats(1, 2, 3, 4, 5, 6,
                       streak_days=5, cards_due=7, recent_score=0.71, last_synced_at='2026-06-10T00:00:00')
    assert out['streak_days'] == 5
    assert out['cards_due'] == 7
    assert out['recent_score'] == 0.71
    assert out['last_synced_at'] == '2026-06-10T00:00:00'
    # legacy keys preserved
    assert out['materials'] == 1 and out['generations']['total'] == 2 + 3 + 4
```

- [ ] **Step 2: Run → FAIL** (`_shape_stats` doesn't accept the new kwargs).

- [ ] **Step 3: Implement**

Update `_shape_stats` to accept the new keyword args (defaulting to `None`/`0`) and include them in
the dict, preserving all existing keys:

```python
def _shape_stats(materials, quizzes, flashcards, reports, chats, messages,
                 streak_days=0, cards_due=0, recent_score=None, last_synced_at=None) -> dict:
    return {
        "materials": materials,
        "generations": {"quiz": quizzes, "flashcards": flashcards, "reports": reports,
                         "total": quizzes + flashcards + reports},
        "chats": chats, "messages": messages,
        "streak_days": streak_days, "cards_due": cards_due,
        "recent_score": recent_score, "last_synced_at": last_synced_at,
    }
```

In the `action=stats` handler, compute the new values with guarded queries (each wrapped so a missing
table yields the default):

```python
from .services.dashboard_stats import current_streak
from datetime import date

def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default

activity = _safe(lambda: _activity_dates(conn, course_id, user_id), set())
streak = current_streak(activity, date.today())
cards_due = _safe(lambda: _cards_due_count(conn, user_id), 0)         # COUNT(*) FROM flashcard_reviews ... due_at <= now()
recent_score = _safe(lambda: _latest_attempt_accuracy(conn, course_id, user_id), None)
last_synced = _safe(lambda: _last_synced_at(conn, course_id), None)
```

Implement `_activity_dates` (UNION of distinct DATE() from quiz_attempts, flashcard_reviews, and
chat_messages for this user/course — include only tables that exist; the `_safe` wrapper covers the
rest), `_cards_due_count`, `_latest_attempt_accuracy`, `_last_synced_at` as small queries matching
the real schema (confirm column names first with `rg`).

- [ ] **Step 4: Run → PASS** and existing `tests/test_course_stats.py` still green.

- [ ] **Step 5: Commit**

```bash
git add api/course.py tests/test_course_stats.py
git commit -m "feat: add engagement metrics to course stats (guarded)"
```

---

### Task 3: Render the richer widget

**Files:**
- Modify: `src/components/CourseStatsWidget.jsx`

- [ ] **Step 1: Render new tiles, hide empties**

Replace the four-`Stat` row with a primary engagement row + a secondary counts row:

```jsx
<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
  {stats.streak_days > 0 && <Stat label="🔥 Streak" value={`${stats.streak_days}d`} />}
  {stats.cards_due > 0 && <Stat label="Due today" value={stats.cards_due} />}
  {stats.recent_score != null && <Stat label="Last quiz" value={`${Math.round(stats.recent_score * 100)}%`} />}
  {stats.last_synced_at && <Stat label="Synced" value={relativeTime(stats.last_synced_at)} />}
</div>
<div className="mt-3 grid grid-cols-4 gap-2 text-gray-400">
  <Stat label="Materials" value={stats.materials} />
  <Stat label="Generations" value={stats.generations?.total} />
  <Stat label="Chats" value={stats.chats} />
  <Stat label="Messages" value={stats.messages} />
</div>
```

Use the existing `dateUtils` for `relativeTime` (or add a small helper) — check `src/utils/dateUtils.js`.

- [ ] **Step 2: Manually verify**

Run: `npm run dev`. With activity, the streak/due/last-quiz/synced tiles appear and empty ones hide;
legacy counts still render below.

- [ ] **Step 3: Commit**

```bash
git add src/components/CourseStatsWidget.jsx
git commit -m "feat: engagement-oriented course stats widget"
```

---

## Self-Review

- **Spec coverage:** streak helper (T1), guarded endpoint extension preserving legacy keys (T2),
  richer widget hiding empties (T3). ✓
- **Graceful degradation:** every new metric is wrapped so a not-yet-built dependency (e.g.
  `flashcard_reviews`) yields a safe default — this item ships independently. ✓
- **Backward compatible:** `_shape_stats` keeps all original keys; new args default. ✓
