import sys, os
from unittest.mock import MagicMock

# Stub out modules with relative imports so `course` can be imported standalone.
for mod in ('courses', 'models', 'middleware', 'db'):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_stats_payload_shape():
    from course import _shape_stats
    out = _shape_stats(materials=12, quizzes=3, flashcards=5, reports=2, chats=7, messages=88)
    assert out == {
        "materials": 12,
        "generations": {"quiz": 3, "flashcards": 5, "reports": 2, "total": 10},
        "chats": 7,
        "messages": 88,
    }
