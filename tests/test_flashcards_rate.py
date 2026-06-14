from api.flashcards import compute_next_review


def test_compute_next_review_advances_on_up():
    prev = {'repetitions': 0, 'interval_days': 0, 'ease': 2.5}
    nxt = compute_next_review(prev, 'up')
    assert nxt['repetitions'] == 1
    assert nxt['interval_days'] == 1
    assert nxt['ease'] >= 2.5


def test_compute_next_review_resets_on_down():
    prev = {'repetitions': 4, 'interval_days': 30, 'ease': 2.6}
    nxt = compute_next_review(prev, 'down')
    assert nxt['repetitions'] == 0
    assert nxt['interval_days'] == 1
