# Quiz Attempt History & Grading View — Verification Note (Already Implemented)

> **Status: NOT a build plan.** Code inspection on 2026-05-31 shows this P1 item is **already implemented end-to-end** (backend + frontend). The roadmap's "Grader service exists, no UI" is incorrect — the UI exists.

## Evidence

Backend — `api/quiz.py` + `api/db.py`:
- Tables `quiz_attempts` (with `score_percent DECIMAL(5,2)`, `submitted_at`) and `quiz_attempt_answers` (`attempt_id` FK, per-question feedback), plus indexes `idx_..._gen_user_submitted (generation_id, user_id, submitted_at DESC)` and `idx_..._answers_attempt_q`.
- Grader `grade_quiz` (`services/...`), invoked in `_submit_attempt` (line 1022), which INSERTs the attempt + answers.
- Endpoints `_list_attempts` (line 1167) and `_get_attempt` (line 1200), routed from `action=list_attempts` / `action=get_attempt` (lines 548/550).

Frontend — `src/QuizViewer.jsx`:
- `viewMode` state with `'quiz' | 'attempts' | 'attempt-detail'`.
- Fetches `/api/quiz?action=list_attempts&generation_id=...` and `/api/quiz?action=get_attempt&attempt_id=...`.
- Renders the attempts list (with count), loading + empty states ("No attempts yet. Submit the quiz to record your first attempt."), and attempt detail.

## Verification checklist (do this instead of building)

- [ ] Take a quiz, submit it, confirm a graded score appears and the attempt is recorded.
- [ ] Open the attempts view → the new attempt is listed with score + timestamp.
- [ ] Open an attempt → per-question correctness/feedback renders.
- [ ] Take a second attempt → both appear, newest first (matches the `submitted_at DESC` index).
- [ ] If any of the above fails, capture the failing case and convert it into a targeted TDD fix task.

## Recommendation

Treat as done. Reallocate the effort to genuinely-unbuilt items.
```
