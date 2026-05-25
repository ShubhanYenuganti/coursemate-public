import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.assessment import build_from_markdown


def test_quiz_splits_by_question():
    md = "# Quiz 3\n\nProblem 1\nWhat is backprop?\n\nProblem 2\nDefine the chain rule.\n\nProblem 3\nCompute gradient."
    mi = build_from_markdown(md, doc_type="quiz", page_count=2)
    assert mi.doc_type == "quiz"
    assert len(mi.nodes) == 3


def test_exam_with_no_questions_returns_single_node():
    md = "# Exam\nGeneral instructions only."
    mi = build_from_markdown(md, doc_type="exam", page_count=4)
    assert len(mi.nodes) == 1
    assert mi.nodes[0].end_page == 4


def test_nodes_have_no_subparts():
    md = "Problem 1\n(a) Part a.\n(b) Part b."
    mi = build_from_markdown(md, doc_type="quiz", page_count=2)
    for n in mi.nodes:
        assert n.nodes == []


def test_question_title_format():
    md = "Problem 1\nFirst question.\n\nProblem 2\nSecond question."
    mi = build_from_markdown(md, doc_type="exam", page_count=3)
    titles = [n.title for n in mi.nodes]
    assert any("Question 1" in t for t in titles)
    assert any("Question 2" in t for t in titles)


def test_assessment_builder_ids_are_stable():
    md = "Problem 1\nFirst question.\n\nProblem 2\n[ANSWER_KEY]\nSecond question."
    a = build_from_markdown(md, doc_type="exam", page_count=3).to_dict()
    b = build_from_markdown(md, doc_type="exam", page_count=3).to_dict()
    assert a == b
