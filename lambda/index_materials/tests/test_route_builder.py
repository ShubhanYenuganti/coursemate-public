import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders import route_builder


def test_lecture_slide_routes_to_slides():
    fn = route_builder("lecture_slide")
    assert fn.__module__ == "builders.slides"


def test_hw_instruction_routes_to_problems():
    fn = route_builder("hw_instruction")
    assert fn.__module__ == "builders.problems"


def test_hw_solution_routes_to_problems():
    fn = route_builder("hw_solution")
    assert fn.__module__ == "builders.problems"


def test_reading_routes_to_document():
    fn = route_builder("reading")
    assert fn.__module__ == "builders.document"


def test_quiz_routes_to_assessment():
    fn = route_builder("quiz")
    assert fn.__module__ == "builders.assessment"


def test_exam_routes_to_assessment():
    fn = route_builder("exam")
    assert fn.__module__ == "builders.assessment"


def test_unknown_defaults_to_document():
    fn = route_builder("unknown_type")
    assert fn.__module__ == "builders.document"
