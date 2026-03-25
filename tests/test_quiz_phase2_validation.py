import sys
import os
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_token_estimator_output_shape_and_sanity():
    from api.services.quiz_token_estimator import estimate_quiz_token_ranges

    estimate = estimate_quiz_token_ranges(
        system_prompt="You are a helpful quiz generator.",
        user_prompt="Generate questions about topic X.",
        tf_count=2,
        sa_count=1,
        la_count=0,
        mcq_count=3,
        mcq_options=4,
    )

    keys = {
        'estimated_prompt_tokens_low',
        'estimated_prompt_tokens_high',
        'estimated_total_tokens_low',
        'estimated_total_tokens_high',
    }
    assert set(estimate.keys()) == keys
    assert estimate['estimated_prompt_tokens_low'] >= 0
    assert estimate['estimated_prompt_tokens_high'] >= estimate['estimated_prompt_tokens_low']
    assert estimate['estimated_total_tokens_low'] >= estimate['estimated_prompt_tokens_low']
    assert estimate['estimated_total_tokens_high'] >= estimate['estimated_total_tokens_low']


def test_grading_logic_mcq_tf_sa_la_and_skipped():
    from api.services.quiz_attempt_grader import grade_quiz_attempt

    questions = [
        {
            'question_index': 0,
            'question_type': 'mcq',
            'correct_answer_text': 'A',
            'question_id': 10,
        },
        {
            'question_index': 1,
            'question_type': 'tf',
            'correct_answer_text': 'True',
            'question_id': 11,
        },
        {
            'question_index': 2,
            'question_type': 'sa',
            'correct_answer_text': 'hello world',
            'question_id': 12,
        },
        {
            'question_index': 3,
            'question_type': 'la',
            'correct_answer_text': 'expected long answer',
            'question_id': 13,
        },
    ]

    # Skipped question: index 4 doesn't exist in questions; ignore it.
    answers_by_index = {
        0: 'A',  # correct mcq
        1: 'False',  # incorrect tf
        2: 'Hello   World',  # exact after normalization
        # 3 omitted => skipped
    }

    grade = grade_quiz_attempt(questions=questions, answers_by_index=answers_by_index)

    assert grade['auto_graded_count'] == 3
    assert grade['manual_review_required'] is False  # no sa/la mismatch because la skipped
    assert grade['manual_review_count'] == 0

    # Score: correct among auto-graded = mcq(1) + tf(0) + sa(1) => 2/3 => 66.6%
    assert round(grade['score_percent'], 1) == round((2 / 3) * 100.0, 1)

    per_q = {pq['question_index']: pq for pq in grade['per_question']}
    assert per_q[0]['is_correct'] is True
    assert per_q[1]['is_correct'] is False
    assert per_q[2]['is_correct'] is True
    assert per_q[3]['skipped'] is True
    assert per_q[3]['is_correct'] is None


def test_pdf_builder_builds_bytes_with_mock_weasyprint(monkeypatch):
    # Provide a fake weasyprint module so tests don't require system deps.
    class FakeHTML:
        def __init__(self, string=None):
            self.string = string

        def write_pdf(self):
            return b'%PDF-1.4\n%fake\n'

    fake_weasyprint = types.SimpleNamespace(HTML=FakeHTML)
    monkeypatch.setitem(sys.modules, 'weasyprint', fake_weasyprint)

    from api.services.quiz_pdf_builder import build_quiz_pdf_bytes

    pdf = build_quiz_pdf_bytes(
        quiz={
            'title': 'Quiz 1',
            'topic': 'Topic',
            'provider': 'openai',
            'model_id': 'gpt-4o-mini',
            'generated_at': '2026-03-24',
            'generation_settings': {},
            'questions': [
                {
                    'question_index': 0,
                    'type': 'mcq',
                    'question': 'What is X?',
                    'options': ['A', 'B'],
                    'answer': 'A',
                }
            ],
        }
    )
    assert isinstance(pdf, (bytes, bytearray))
    assert len(pdf) > 8
    assert bytes(pdf).startswith(b'%PDF')

