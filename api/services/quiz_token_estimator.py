"""
Quiz token estimation helpers for Phase 2.

This module intentionally uses deterministic heuristics (no network calls)
so Phase 2 can provide a stable low/high token range before invoking the LLM.
"""

from __future__ import annotations


def _approx_tokens_from_chars(char_count: int, low_factor: float, high_factor: float) -> tuple[int, int]:
    # Conservative English heuristic: ~4 chars per token on average.
    # We intentionally keep it simple/deterministic.
    base = max(0, char_count) / 4.0
    low = int(base * low_factor)
    high = int(base * high_factor)
    return low, high


def estimate_quiz_token_ranges(
    *,
    system_prompt: str,
    user_prompt: str,
    tf_count: int,
    sa_count: int,
    la_count: int,
    mcq_count: int,
    mcq_options: int,
) -> dict:
    """
    Return a deterministic token envelope estimate.

    Output keys match the DB snapshot columns:
      - estimated_prompt_tokens_low/high
      - estimated_total_tokens_low/high
    """
    system_prompt = system_prompt or ""
    user_prompt = user_prompt or ""

    prompt_chars = len(system_prompt) + len(user_prompt)
    estimated_prompt_tokens_low, estimated_prompt_tokens_high = _approx_tokens_from_chars(
        prompt_chars, low_factor=0.85, high_factor=1.15
    )

    # Output envelope: rough per-question token sizes by type.
    # These are heuristics; they only need to be good enough for a preflight warning/UI.
    per_mcq_tokens_low = 260 + max(0, mcq_options - 2) * 25
    per_mcq_tokens_high = 340 + max(0, mcq_options - 2) * 35

    per_tf_tokens_low = 120
    per_tf_tokens_high = 170

    # Answers/explanations for SA/LA can vary widely; keep an envelope.
    per_sa_tokens_low = 220
    per_sa_tokens_high = 320

    per_la_tokens_low = 300
    per_la_tokens_high = 450

    output_low = (
        mcq_count * per_mcq_tokens_low
        + tf_count * per_tf_tokens_low
        + sa_count * per_sa_tokens_low
        + la_count * per_la_tokens_low
    )
    output_high = (
        mcq_count * per_mcq_tokens_high
        + tf_count * per_tf_tokens_high
        + sa_count * per_sa_tokens_high
        + la_count * per_la_tokens_high
    )

    estimated_total_tokens_low = int(estimated_prompt_tokens_low + output_low)
    estimated_total_tokens_high = int(estimated_prompt_tokens_high + output_high)

    return {
        "estimated_prompt_tokens_low": estimated_prompt_tokens_low,
        "estimated_prompt_tokens_high": estimated_prompt_tokens_high,
        "estimated_total_tokens_low": estimated_total_tokens_low,
        "estimated_total_tokens_high": estimated_total_tokens_high,
    }

