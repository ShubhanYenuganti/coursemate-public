import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_extract_conversation_context_from_body():
    from api.quiz import _extract_conversation_context
    assert _extract_conversation_context({"conversation_context": "We discussed TCP."}) == "We discussed TCP."
    assert _extract_conversation_context({}) is None
    assert _extract_conversation_context({"conversation_context": "  "}) is None
