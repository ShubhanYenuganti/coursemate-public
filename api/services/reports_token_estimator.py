"""Reports token estimation heuristics."""
from __future__ import annotations

_OUTPUT_BUDGETS = {
    "study-guide": (3_000, 5_500),
    "briefing":    (1_000, 1_800),
    "summary":     (2_500, 4_500),
    "custom":      (2_000, 5_000),
}


def _approx_tokens(char_count: int, low_f: float, high_f: float) -> tuple[int, int]:
    base = max(0, char_count) / 4.0
    return int(base * low_f), int(base * high_f)


def estimate_reports_token_ranges(
    *,
    system_prompt: str,
    user_prompt: str,
    template_id: str,
) -> dict:
    prompt_chars = len(system_prompt or "") + len(user_prompt or "")
    p_low, p_high = _approx_tokens(prompt_chars, 0.85, 1.15)
    o_low, o_high = _OUTPUT_BUDGETS.get(template_id, (1_200, 2_000))
    return {
        "estimated_prompt_tokens_low": p_low,
        "estimated_prompt_tokens_high": p_high,
        "estimated_total_tokens_low": p_low + o_low,
        "estimated_total_tokens_high": p_high + o_high,
    }
