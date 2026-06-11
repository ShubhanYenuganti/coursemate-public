# Study Planner / Mastery Tracking — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 3.1
**Scope:** Read-model over existing `quiz_attempts` / `quiz_attempt_answers`, a mastery API, a "Weak topics" view that pre-fills a targeted generation. Mostly aggregation — no new write-path data.

## Problem

Quiz attempt data already exists in Postgres — `quiz_attempts` and `quiz_attempt_answers`
(`is_correct`, `grader_feedback`, per `question_id`), persisted by `api/quiz.py::_submit_attempt`.
But nothing aggregates it. Students get no feedback on where they're weak and no path from "I missed
these" to "study this," so assessment and study are disconnected.

## Goal

1. A **mastery summary** per course: accuracy by topic, worst topics surfaced first.
2. A **"Weak topics" view** that, for a chosen weak topic, pre-fills the quiz/flashcards generation
   form with that topic so the student can immediately drill it.

## Decisions

1. **Topic granularity = the quiz generation's `topic`.** Quizzes carry a `topic`
   (`quiz_generations.topic`). Per-question topics don't exist, so mastery aggregates answers up to
   their generation's topic. Untopic'd quizzes fall under "General." This is honest about the data we
   have and needs no new tagging.
2. **Pure aggregation function** `mastery_by_topic(rows)` where `rows` are
   `(topic, is_correct)` tuples → `[{topic, attempted, correct, accuracy}]` sorted worst-first. This
   is the TDD core; the DB just supplies the join.
3. **Read-only; no schema change.** A single SQL join (`quiz_attempt_answers` → `quiz_questions` →
   `quiz_generations`) feeds the aggregator.
4. **"Drill this" reuses existing generation forms.** Selecting a weak topic navigates to the quiz or
   flashcards page with the topic pre-filled (query param or state) — no new generation backend.
5. **v1 is quizzes only.** Flashcard "ratings" mastery (from the spaced-repetition item) is a natural
   later merge into the same view.

## Aggregator — `api/services/mastery.py`

```python
def mastery_by_topic(rows: list[tuple]) -> list[dict]:
    """rows: iterable of (topic, is_correct). Returns per-topic accuracy, worst-first."""
    agg = {}
    for topic, is_correct in rows:
        t = topic or "General"
        a = agg.setdefault(t, {"topic": t, "attempted": 0, "correct": 0})
        a["attempted"] += 1
        if is_correct:
            a["correct"] += 1
    out = []
    for a in agg.values():
        a["accuracy"] = round(a["correct"] / a["attempted"], 3) if a["attempted"] else 0.0
        out.append(a)
    out.sort(key=lambda x: (x["accuracy"], -x["attempted"]))
    return out
```

## API — `api/quiz.py` (new `action=mastery`) or `api/course.py`

`GET /api/quiz?action=mastery&course_id=7` →
```json
{ "topics": [ {"topic": "EKF", "attempted": 12, "correct": 4, "accuracy": 0.333}, ... ] }
```
SQL: join `quiz_attempt_answers` (the user's attempts) to `quiz_questions`/`quiz_generations` filtered
to `course_id` and the requesting user, selecting `(quiz_generations.topic, is_correct)`.

## Frontend

- New `src/components/WeakTopicsWidget.jsx` (or a Generations-page panel): GETs mastery, lists topics
  worst-first with an accuracy bar, and a "Drill this" button per topic.
- "Drill this" → navigate to `/course/:id` quiz/flashcards generation with `topic` pre-filled (the
  Quiz/Flashcards forms already have a topic input — `src/Quiz.jsx:797`, `src/Flashcards.jsx:778`).
- Surface the widget on the dashboard and/or course page.

## Verification

- pytest: `mastery_by_topic` — worst-first ordering, untopic'd → "General", accuracy math, empty
  input → `[]`.
- Manual: take quizzes with mixed results across topics → weak topics surface in order; "Drill this"
  opens the generation form with the topic filled.
