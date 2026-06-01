import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'flashcards_generate'))


def test_flashcards_extract_conversation_context():
    from api.flashcards import _extract_conversation_context
    assert _extract_conversation_context({"conversation_context": "We discussed mitosis."}) == "We discussed mitosis."
    assert _extract_conversation_context({}) is None
    assert _extract_conversation_context({"conversation_context": "  "}) is None


def test_flashcards_merge_conversation_context():
    from handler import _merge_conversation_context
    merged = _merge_conversation_context("We discussed mitosis.", "Material chunk.")
    assert "We discussed mitosis." in merged and "Material chunk." in merged
    assert merged.index("We discussed") < merged.index("Material chunk.")
    assert _merge_conversation_context(None, "Material chunk.") == "Material chunk."
