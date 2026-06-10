import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'reports_generate'))


def test_reports_extract_conversation_context():
    from api.reports import _extract_conversation_context
    assert _extract_conversation_context({"conversation_context": "We discussed osmosis."}) == "We discussed osmosis."
    assert _extract_conversation_context({}) is None
    assert _extract_conversation_context({"conversation_context": "  "}) is None


def test_reports_merge_conversation_context():
    from handler import _merge_conversation_context
    merged = _merge_conversation_context("We discussed osmosis.", "Material chunk.")
    assert "We discussed osmosis." in merged and "Material chunk." in merged
    assert merged.index("We discussed") < merged.index("Material chunk.")
    assert _merge_conversation_context(None, "Material chunk.") == "Material chunk."
