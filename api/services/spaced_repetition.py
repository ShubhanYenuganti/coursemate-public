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
