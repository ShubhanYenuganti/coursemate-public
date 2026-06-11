# Server-Side Ratings + Spaced Repetition — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 1.2 (incomplete: ratings only in localStorage) + 2.5 (retention flywheel)
**Scope:** New `flashcard_reviews` table, pure SM-2 scheduler, `api/flashcards.py` rate/due actions, `src/FlashcardViewer.jsx` (replace localStorage), a "Due today" dashboard widget.

## Problem

Flashcard ratings live only in `localStorage`, keyed per generation
(`src/utils/flashcardRatings.js`). They are lost on device switch or cache clear, are not tied to
the user, and feed nothing — the thumbs up/down UI (`src/FlashcardViewer.jsx:277`) is decorative.
There is no reason for a student to return tomorrow.

## Goal

1. Persist each rating server-side, per `(user, generation, card_index)`.
2. Schedule the next review with a standard algorithm (SM-2), so each card has a `due_at`.
3. Surface a "Due today" count + entry point on the dashboard, turning study into a daily loop.

## Decisions

1. **SM-2, not FSRS.** SM-2 is a small, well-understood, fully pure function; FSRS needs trained
   weights we don't have. SM-2 lives in `api/services/spaced_repetition.py` as a pure function and
   is the TDD core.
2. **Keep the thumbs UI; map to grades.** The viewer already shows up/down. Map `down → "again"`
   (quality 2, reset interval) and `up → "good"` (quality 4, advance). A later change can expand to
   again/hard/good/easy without touching the schema.
3. **Card identity = `(generation_id, card_index)`.** Flashcards have no stable per-card DB id
   today; index within a generation is the stable key, matching the existing localStorage scheme.
4. **Server is source of truth; client is optimistic.** The viewer writes through to the API and
   keeps local state for snappy UI, replacing the localStorage helper entirely.
5. **"Due today" is a count + link**, not a cross-generation study queue in v1 (that queue is a
   natural follow-on). The widget links to the most-due generation's viewer.

## SM-2 scheduler — `api/services/spaced_repetition.py`

Pure function, no I/O:

```python
from dataclasses import dataclass

@dataclass
class ReviewState:
    repetitions: int      # consecutive correct reviews
    interval_days: int    # days until next review
    ease: float           # ease factor, >= 1.3

def schedule(prev: ReviewState, quality: int) -> ReviewState:
    """SM-2. quality in 0..5. quality < 3 resets repetitions and interval."""
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

`due_at = now + interval_days` is computed at the API layer when persisting.

## Schema — `migrations/011_flashcard_reviews.sql`

```sql
CREATE TABLE IF NOT EXISTS flashcard_reviews (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_id INTEGER NOT NULL,
    card_index    INTEGER NOT NULL,
    last_rating   TEXT,                       -- 'up' | 'down'
    repetitions   INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 0,
    ease          REAL    NOT NULL DEFAULT 2.5,
    due_at        TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, generation_id, card_index)
);

CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_due ON flashcard_reviews (user_id, due_at);
```

## API — `api/flashcards.py`

- **POST `action=rate`**: body `{ generation_id, card_index, rating }`. Loads prior
  `ReviewState` (or `INITIAL`), maps `rating` → quality via `THUMB_TO_QUALITY`, calls `schedule`,
  upserts the row with new `due_at = now + interval_days days`. Returns the new state + `due_at`.
- **GET `action=due`** (or under existing GET dispatch): returns the user's due summary:
  `{ due_count, next: { generation_id, course_id } }` where `due_at <= now()`, joined to the
  generation's course for the deep link. Used by the dashboard widget.

## Frontend

- `src/FlashcardViewer.jsx`: replace `loadRatings`/`setRating` (localStorage) with:
  - initial ratings loaded from a `ratings` map returned by `get_generation` (extend its payload) or
    a dedicated `action=ratings&generation_id=`.
  - on thumb click, `POST action=rate`; keep optimistic local update.
- New widget `src/components/DueTodayWidget.jsx`: fetches `action=due`, shows
  "N cards due today" with a button linking to `/course/:courseId/flashcards/:generationId`.
  Rendered on `src/Dashboard.jsx`.
- Delete `src/utils/flashcardRatings.js` once no longer imported.

## Verification

- pytest: SM-2 table-driven tests (reset on `down`, 1→6→interval growth on repeated `up`, ease floor
  1.3). API `rate` upsert idempotency.
- Manual: rate a card up several times → due date pushes out; rate down → due tomorrow; dashboard
  "Due today" reflects counts and deep-links correctly; ratings survive a hard refresh and a second
  browser.
