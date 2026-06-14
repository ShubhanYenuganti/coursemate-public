from api.services.spaced_repetition import schedule, ReviewState, INITIAL, THUMB_TO_QUALITY


def test_down_resets_to_one_day():
    s = schedule(ReviewState(repetitions=5, interval_days=40, ease=2.6), quality=2)
    assert s.repetitions == 0
    assert s.interval_days == 1


def test_first_two_intervals_are_fixed():
    s1 = schedule(INITIAL, quality=4)
    assert s1.repetitions == 1 and s1.interval_days == 1
    s2 = schedule(s1, quality=4)
    assert s2.repetitions == 2 and s2.interval_days == 6


def test_third_interval_uses_ease():
    s = schedule(ReviewState(repetitions=2, interval_days=6, ease=2.5), quality=4)
    assert s.repetitions == 3
    assert s.interval_days == round(6 * s.ease)


def test_ease_never_below_floor():
    s = INITIAL
    for _ in range(10):
        s = schedule(s, quality=0)
    assert s.ease >= 1.3


def test_thumb_mapping():
    assert THUMB_TO_QUALITY['down'] < 3 <= THUMB_TO_QUALITY['up']
