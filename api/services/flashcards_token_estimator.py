"""
Flashcards token estimation helpers.

Deterministic heuristics for estimate preflight responses.
"""

from __future__ import annotations


def _approx_tokens_from_chars(char_count: int, low_factor: float, high_factor: float) -> tuple[int, int]:
    base = max(0, char_count) / 4.0
    return int(base * low_factor), int(base * high_factor)


def estimate_flashcards_token_ranges(
    *,
    system_prompt: str,
    user_prompt: str,
    card_count: int,
    depth: str,
) -> dict:
    system_prompt = system_prompt or ""
    user_prompt = user_prompt or ""

    prompt_chars = len(system_prompt) + len(user_prompt)
    est_prompt_low, est_prompt_high = _approx_tokens_from_chars(
        prompt_chars, low_factor=0.85, high_factor=1.15
    )

    depth_key = (depth or "moderate").strip().lower()
    if depth_key == 'brief':
        per_card_low, per_card_high = 90, 140
    elif depth_key in ('in-depth', 'indepth', 'in_depth'):
        per_card_low, per_card_high = 220, 320
    else:
        per_card_low, per_card_high = 140, 220

    output_low = max(0, int(card_count)) * per_card_low
    output_high = max(0, int(card_count)) * per_card_high

    return {
        'estimated_prompt_tokens_low': est_prompt_low,
        'estimated_prompt_tokens_high': est_prompt_high,
        'estimated_total_tokens_low': int(est_prompt_low + output_low),
        'estimated_total_tokens_high': int(est_prompt_high + output_high),
    }
