DOCUMENT_TYPES = [
    ("general",         "General / other"),
    ("lecture_slide",   "Lecture slides"),
    ("lecture_note",    "Lecture notes"),
    ("discussion_note", "Discussion notes"),
    ("reading",         "Reading"),
    ("hw_instruction",  "Homework instructions"),
    ("hw_solution",     "Homework solutions"),
    ("quiz",            "Quiz"),
    ("exam",            "Exam"),
    ("coding_spec",     "Coding project spec"),
    ("code_file",       "Code file"),
]

VALID_DOC_TYPES = {k for k, _ in DOCUMENT_TYPES}
DEFAULT_DOC_TYPE = "general"
