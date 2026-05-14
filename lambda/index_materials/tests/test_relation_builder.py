import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from unittest.mock import patch, MagicMock
from relation_builder import _extract_json, _build_relations_prompt, _filter_relations

SAMPLE_TARGET = {
    "material_id": 10,
    "material_title": "Lecture 5: Backpropagation",
    "doc_type": "lecture_slide",
    "material_summary": "Covers chain rule and SGD update.",
    "metadata_tags": ["backpropagation", "chain-rule", "gradient-descent"],
}

SAMPLE_OTHERS = [
    {
        "material_id": 11,
        "material_title": "HW 3",
        "doc_type": "hw_instruction",
        "material_summary": "Problems on backpropagation.",
        "metadata_tags": ["backpropagation", "gradient-computation"],
    }
]


def test_extract_json_valid():
    raw = '[{"source_id": 10, "target_id": 11, "relation_type": "practice_for", "shared_tags": ["backpropagation"], "confidence": 0.9}]'
    result = _extract_json(raw)
    assert len(result) == 1
    assert result[0]["relation_type"] == "practice_for"


def test_extract_json_invalid():
    result = _extract_json("No relationships found.")
    assert result == []


def test_extract_json_embedded_in_prose():
    raw = 'Here are the relations: [{"source_id": 1, "target_id": 2, "relation_type": "extends", "shared_tags": [], "confidence": 0.75}] Done.'
    result = _extract_json(raw)
    assert len(result) == 1


def test_filter_relations_passes_valid():
    relations = [{"source_id": 10, "target_id": 11, "relation_type": "prerequisite", "shared_tags": [], "confidence": 0.8}]
    filtered = _filter_relations(relations, course_id=1)
    assert len(filtered) == 1
    assert filtered[0]["relation_type"] == "prerequisite"
    assert filtered[0]["course_id"] == 1


def test_filter_relations_excludes_low_confidence():
    relations = [{"source_id": 1, "target_id": 2, "relation_type": "extends", "shared_tags": [], "confidence": 0.3}]
    filtered = _filter_relations(relations, course_id=1)
    assert filtered == []


def test_filter_relations_excludes_unknown_type():
    relations = [{"source_id": 1, "target_id": 2, "relation_type": "unrelated", "shared_tags": [], "confidence": 0.9}]
    filtered = _filter_relations(relations, course_id=1)
    assert filtered == []


def test_build_relations_prompt_contains_ids():
    prompt = _build_relations_prompt(SAMPLE_TARGET, SAMPLE_OTHERS)
    assert "10" in prompt
    assert "11" in prompt
    assert "backpropagation" in prompt
    assert "practice_for" in prompt


def test_build_relations_prompt_target_is_marked():
    prompt = _build_relations_prompt(SAMPLE_TARGET, SAMPLE_OTHERS)
    assert "TARGET" in prompt
    assert "EXISTING" in prompt
