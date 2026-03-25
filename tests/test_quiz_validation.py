"""Tests for quiz LLM response validation and normalization."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.quiz import _normalize_question_type, _validate_and_normalize_questions

def test_type_aliases():
    assert _normalize_question_type('multiple_choice') == 'mcq'
    assert _normalize_question_type('true_false') == 'tf'
    assert _normalize_question_type('short_answer') == 'sa'
    assert _normalize_question_type('long_answer') == 'la'
    assert _normalize_question_type('MCQ') == 'mcq'
    assert _normalize_question_type('TF') == 'tf'

def test_mcq_question_valid():
    q = {'type': 'mcq', 'question': 'What is X?', 'options': ['A', 'B', 'C', 'D'], 'answer': 'A', 'explanation': 'Because A'}
    result = _validate_and_normalize_questions([q])
    assert len(result) == 1
    assert result[0]['type'] == 'mcq'
    assert result[0]['options'] == ['A', 'B', 'C', 'D']
    assert result[0]['answer'] == 'A'

def test_tf_normalizes_answer():
    q = {'type': 'tf', 'question': 'Is sky blue?', 'answer': 'yes'}
    result = _validate_and_normalize_questions([q])
    assert result[0]['answer'] == 'True'

def test_tf_false_normalizes():
    q = {'type': 'true_false', 'question': 'Is sky green?', 'answer': 'no'}
    result = _validate_and_normalize_questions([q])
    assert result[0]['answer'] == 'False'

def test_missing_question_text_raises():
    import pytest
    with pytest.raises(ValueError, match='question text'):
        _validate_and_normalize_questions([{'type': 'sa', 'question': '', 'answer': 'x'}])

def test_mcq_missing_options_raises():
    import pytest
    with pytest.raises(ValueError, match='options'):
        _validate_and_normalize_questions([{'type': 'mcq', 'question': 'What?', 'options': ['A'], 'answer': 'A'}])


from api.quiz import _build_quiz_prompt

def test_build_prompt_includes_topic():
    system, user = _build_quiz_prompt(
        topic='Neural Networks', tf_count=2, sa_count=1, la_count=0, mcq_count=3, mcq_options=4,
        material_context='Context text here'
    )
    assert 'Neural Networks' in user
    assert 'Context text here' in user
    assert 'JSON' in system

def test_build_prompt_no_topic_fallback():
    system, user = _build_quiz_prompt(
        topic='', tf_count=1, sa_count=0, la_count=0, mcq_count=0, mcq_options=4,
        material_context='Some material'
    )
    assert 'course material' in user.lower()
