# Richer Dashboard — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 3.5
**Scope:** Replace the four raw counts in `CourseStatsWidget` / `_shape_stats` with engagement-oriented stats: study streak, cards due today, recent quiz score, last-synced. Composes data added by the spaced-repetition, mastery, and sync-transparency items.

## Problem

`src/components/CourseStatsWidget.jsx` shows four raw counts — materials, generations, chats,
messages (`api/course.py::_shape_stats`). They're inert: they don't tell a student whether they're
keeping up, what to do next, or whether their materials are current.

## Goal

The course stats widget shows actionable, engagement-oriented metrics:
- **Study streak** (consecutive days with any study activity).
- **Cards due today** (from `flashcard_reviews`, the spaced-repetition item).
- **Recent quiz score** (latest attempt's accuracy).
- **Last synced** (most recent material sync time).
Materials/generations counts remain available but secondary.

## Decisions

1. **Extend `_shape_stats`, don't replace the endpoint.** Add the new fields; keep the existing keys
   for backward compatibility so nothing that reads them breaks.
2. **Compute each metric with a small pure helper** fed by simple queries — streak from a list of
   activity dates, latest-score from the latest attempt. The streak helper is the TDD core (date math
   is the bug-prone part).
3. **Graceful degradation when dependencies aren't built.** `cards_due` is `0`/absent if
   `flashcard_reviews` doesn't exist yet; `recent_score` is `null` if no attempts. The widget hides
   rows with no data. This keeps the dashboard shippable before/independent of the other items.
4. **Activity = any study event.** For the streak, "activity on day D" = a quiz attempt, a flashcard
   review, or a chat message on day D. Union the dates from those sources (whichever tables exist).

## Streak helper — `api/services/dashboard_stats.py`

```python
from datetime import date, timedelta

def current_streak(activity_dates: set, today: date) -> int:
    """Consecutive days up to `today` (or yesterday) with activity."""
    if not activity_dates:
        return 0
    streak = 0
    cursor = today
    if today not in activity_dates and (today - timedelta(days=1)) in activity_dates:
        cursor = today - timedelta(days=1)   # today not yet active but streak still alive
    while cursor in activity_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
```

## API — `api/course.py`

Extend `_shape_stats(...)` (and the `action=stats` query block that feeds it) to also return:

```json
{
  "materials": 12,
  "generations": { "...": "unchanged" },
  "chats": 4, "messages": 88,
  "streak_days": 5,
  "cards_due": 7,
  "recent_score": 0.71,
  "last_synced_at": "2026-06-10T09:12:00Z"
}
```

Each new field comes from a small query guarded so a missing table → safe default (try/except or an
existence check), per decision 3.

## Frontend — `src/components/CourseStatsWidget.jsx`

- Render the new metrics as prominent stat tiles (streak with a 🔥, cards-due links to the
  flashcard viewer, recent score as a %, last-synced as relative time).
- Keep materials/generations/chats/messages as a smaller secondary row.
- Hide any tile whose value is null/absent.

## Verification

- pytest: `current_streak` — empty set → 0; today active → counts today; today inactive but
  yesterday active → streak preserved; gap breaks the streak.
- Manual: with activity on consecutive days, streak increments; due cards reflect
  `flashcard_reviews`; recent score matches the latest attempt; last-synced shows the newest material
  sync.
