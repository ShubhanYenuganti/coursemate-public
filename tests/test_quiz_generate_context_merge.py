import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'quiz_generate'))


def test_merge_conversation_context_prepends_discussion():
    from handler import _merge_conversation_context
    merged = _merge_conversation_context("We discussed TCP handshake.", "PDF chunk text.")
    assert "We discussed TCP handshake." in merged
    assert "PDF chunk text." in merged
    assert merged.index("We discussed") < merged.index("PDF chunk text.")


def test_merge_conversation_context_no_summary_returns_material_only():
    from handler import _merge_conversation_context
    assert _merge_conversation_context(None, "PDF chunk text.") == "PDF chunk text."
    assert _merge_conversation_context("", "PDF chunk text.") == "PDF chunk text."
    assert _merge_conversation_context("  ", "PDF chunk text.") == "PDF chunk text."
