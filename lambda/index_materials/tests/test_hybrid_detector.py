import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import statistics
from unittest.mock import patch, MagicMock
from hybrid_detector import CandidateHeading, HybridSectionDetector, _score_candidate


def test_candidate_heading_defaults():
    c = CandidateHeading(page_num=1, text="Intro", font_size=14.0, is_bold=True, y_position=0.1)
    assert c.score == 0.0
    assert c.source == ""


def test_score_candidate_large_font_bold():
    c = CandidateHeading(page_num=1, text="Section 1", font_size=18.0, is_bold=True, y_position=0.1)
    score = _score_candidate(c, size_delta_sigma=2.0, regex_corroborated=True)
    assert score >= 0.6


def test_score_candidate_small_font():
    c = CandidateHeading(page_num=1, text="Section 1", font_size=11.0, is_bold=False, y_position=0.5)
    score = _score_candidate(c, size_delta_sigma=0.1, regex_corroborated=False)
    assert score < 0.3


def test_score_candidate_long_text_penalized():
    long_text = "A" * 150
    c = CandidateHeading(page_num=1, text=long_text, font_size=16.0, is_bold=True, y_position=0.1)
    score = _score_candidate(c, size_delta_sigma=1.5, regex_corroborated=False)
    assert score < 0.6


def test_regex_only_candidate_gets_baseline_score():
    detector = HybridSectionDetector(doc_type="lecture_slide")
    font_cands = []
    regex_cands = [
        CandidateHeading(page_num=3, text="Motivation", font_size=0.0, is_bold=False, y_position=0.0, source="regex")
    ]
    merged = detector._merge_and_score(font_cands, regex_cands, median_size=12.0, stdev_size=2.0)
    assert len(merged) == 1
    assert merged[0].score >= 0.5


def test_llm_resolve_parses_valid_json():
    detector = HybridSectionDetector(doc_type="reading")
    mock_raw = '[{"page_num": 5, "title": "Methods"}, {"page_num": 9, "title": "Results"}]'
    with patch("hybrid_detector.summarize", return_value=mock_raw):
        resolved = detector._llm_resolve([], ["page text"] * 10, api_key="sk-test")
    assert len(resolved) == 2
    assert resolved[0].page_num == 5
    assert resolved[1].text == "Results"
    assert all(c.source == "llm" for c in resolved)


def test_llm_resolve_returns_empty_on_bad_json():
    detector = HybridSectionDetector(doc_type="reading")
    with patch("hybrid_detector.summarize", return_value="No headings found."):
        resolved = detector._llm_resolve([], ["text"] * 5, api_key="sk-test")
    assert resolved == []


def test_llm_resolve_skips_call_when_no_api_key():
    detector = HybridSectionDetector(doc_type="reading")
    resolved = detector._llm_resolve([], ["text"] * 5, api_key=None)
    assert resolved == []


def test_extract_regex_signals_finds_headings():
    detector = HybridSectionDetector(doc_type="lecture_slide")
    pages = ["# Introduction\nSome text", "## Methods\nMore text", "Body only"]
    cands = detector._extract_regex_signals(pages)
    assert len(cands) == 2
    assert cands[0].page_num == 1
    assert cands[0].text == "Introduction"


def test_merge_and_score_deduplicates_by_page():
    detector = HybridSectionDetector(doc_type="lecture_slide")
    font_cands = [
        CandidateHeading(page_num=1, text="Intro", font_size=16.0, is_bold=True, y_position=0.1, source="font")
    ]
    regex_cands = [
        CandidateHeading(page_num=1, text="Intro", font_size=0.0, is_bold=False, y_position=0.0, source="regex")
    ]
    merged = detector._merge_and_score(font_cands, regex_cands, median_size=12.0, stdev_size=2.0)
    font_entries = [c for c in merged if c.source == "font"]
    assert len(font_entries) == 1
