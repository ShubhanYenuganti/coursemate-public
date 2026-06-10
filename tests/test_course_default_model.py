import sys, os
from unittest.mock import MagicMock

# Stub out modules with relative imports so `course` can be imported standalone.
for mod in ('courses', 'models', 'middleware', 'db'):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_course_default_model_update_payload():
    from course import _extract_default_model_fields
    out = _extract_default_model_fields({"default_ai_provider": "claude", "default_ai_model": "claude-sonnet-4-6"})
    assert out == ("claude", "claude-sonnet-4-6")
    assert _extract_default_model_fields({}) == (None, None)
    assert _extract_default_model_fields({"default_ai_provider": "  "}) == (None, None)
