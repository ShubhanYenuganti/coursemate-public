def route_builder(doc_type: str):
    from builders import slides, problems, document, assessment

    _mapping = {
        "lecture_slide": slides.build,
        "lecture_note": document.build,
        "hw_instruction": problems.build,
        "hw_solution": problems.build,
        "reading": document.build,
        "discussion_note": document.build,
        "general": document.build,
        "quiz": assessment.build,
        "exam": assessment.build,
    }
    return _mapping.get(doc_type, document.build)
