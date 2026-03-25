"""
Quiz attempt grading helpers for Phase 2.

Grading is deterministic and does not require any external services.
"""

from __future__ import annotations


def normalize_text(value: str) -> str:
    """Normalize text for deterministic equality checks."""
    value = (value or "").strip().lower()
    # Collapse internal whitespace for more forgiving comparisons.
    return " ".join(value.split())


def grade_quiz_attempt(*, questions: list[dict], answers_by_index: dict) -> dict:
    """
    Grade a quiz attempt.

    questions:
      [{ question_index, question_type, correct_answer_text, question_id }]

    answers_by_index:
      { <question_index>: <response_text> }
      Keys may be strings or ints.
    """
    per_question = []
    auto_graded = 0
    auto_correct = 0
    manual_review_count = 0

    # Normalize keys once.
    normalized_answers = {}
    for k, v in (answers_by_index or {}).items():
        try:
            ki = int(k)
            normalized_answers[ki] = v
        except (TypeError, ValueError):
            # Ignore unknown keys
            continue

    for q in questions:
        idx = q["question_index"]
        q_type = (q.get("question_type") or "").lower()
        correct = (q.get("correct_answer_text") or "")

        response = normalized_answers.get(idx)
        response_text = None if response is None else str(response)
        response_norm = normalize_text(response_text or "")
        correct_norm = normalize_text(correct)

        is_skipped = response_text is None or response_text.strip() == ""

        if is_skipped:
            per_question.append(
                {
                    "question_index": idx,
                    "skipped": True,
                    "is_correct": None,
                    "manual_review_needed": False,
                }
            )
            continue

        # Auto-grade MCQ / TF.
        if q_type in ("mcq", "tf", "true_false"):
            # For TF, correct is stored as "True"/"False" and UI submits those strings.
            is_correct = response_norm == correct_norm
            if is_correct:
                auto_correct += 1
            auto_graded += 1

            per_question.append(
                {
                    "question_index": idx,
                    "skipped": False,
                    "is_correct": bool(is_correct),
                    "manual_review_needed": False,
                }
            )
            continue

        # SA/LA: exact-match fallback; otherwise manual review.
        if q_type in ("sa", "short_answer", "la", "long_answer"):
            is_exact = response_norm == correct_norm
            if is_exact:
                auto_graded += 1
                auto_correct += 1
                per_question.append(
                    {
                        "question_index": idx,
                        "skipped": False,
                        "is_correct": True,
                        "manual_review_needed": False,
                    }
                )
            else:
                manual_review_count += 1
                per_question.append(
                    {
                        "question_index": idx,
                        "skipped": False,
                        "is_correct": None,
                        "manual_review_needed": True,
                    }
                )
            continue

        # Unknown question types: treat as manual review.
        manual_review_count += 1
        per_question.append(
            {
                "question_index": idx,
                "skipped": False,
                "is_correct": None,
                "manual_review_needed": True,
            }
        )

    manual_review_required = manual_review_count > 0
    score_percent = None
    if auto_graded > 0:
        score_percent = float(auto_correct) / float(auto_graded) * 100.0

    return {
        "auto_graded_count": int(auto_graded),
        "manual_review_count": int(manual_review_count),
        "manual_review_required": bool(manual_review_required),
        "score_percent": score_percent,
        "per_question": per_question,
    }

