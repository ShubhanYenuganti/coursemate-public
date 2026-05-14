import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.problems import _split_problems, _split_subparts, build_from_markdown


def test_split_problems_detects_boundaries():
    md = "HW 3\n\nProblem 1\nDerive the gradient.\n\nProblem 2\nProve convergence."
    preamble, problems = _split_problems(md)
    assert len(problems) == 2
    assert problems[0][0] == "1"
    assert "Derive" in problems[0][1]


def test_split_problems_no_matches_returns_preamble():
    md = "Just a preamble with no problems."
    preamble, problems = _split_problems(md)
    assert preamble == md
    assert problems == []


def test_split_subparts_detects_ab():
    text = "Problem 1\n(a) First part.\n(b) Second part."
    parts = _split_subparts(text)
    assert len(parts) == 2
    assert parts[0][0] == "a"
    assert parts[1][0] == "b"


def test_split_subparts_no_parts_returns_empty():
    text = "Problem 1\nDerive the gradient."
    parts = _split_subparts(text)
    assert parts == []


def test_build_from_markdown_creates_nodes():
    md = "HW 3\n\nProblem 1\nDerive the gradient.\n\nProblem 2\nProve convergence."
    mi = build_from_markdown(md, doc_type="hw_instruction", page_count=4)
    assert mi.doc_type == "hw_instruction"
    problem_titles = [n.title for n in mi.nodes]
    assert any("1" in t for t in problem_titles)
    assert any("2" in t for t in problem_titles)


def test_build_from_markdown_no_problems_single_node():
    md = "Just a preamble with no problems."
    mi = build_from_markdown(md, doc_type="hw_instruction", page_count=2)
    assert len(mi.nodes) == 1
    assert mi.nodes[0].end_page == 2
