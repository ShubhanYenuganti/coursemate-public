import sys, os
from unittest.mock import MagicMock

# Stub modules so prompts.py can be imported without a live DB/Vercel env
for mod in ('middleware', 'models', 'db'):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_validate_prompt_payload():
    from prompts import _validate_prompt
    assert _validate_prompt({"title": "Summarize", "body": "Summarize this lecture"}) == ("Summarize", "Summarize this lecture")
    err1 = None
    try:
        _validate_prompt({"title": "", "body": "x"})
    except ValueError as e:
        err1 = str(e)
    assert err1 and "title" in err1.lower()
    err2 = None
    try:
        _validate_prompt({"title": "t", "body": "  "})
    except ValueError as e:
        err2 = str(e)
    assert err2 and "body" in err2.lower()
