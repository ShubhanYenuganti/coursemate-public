"""
Document type dispatcher — routes a PDF to the appropriate chunker.
"""
from chunkers.base import ChunkSpec
from chunkers import notes, slides, reading, homework, assessment, coding_spec, code_file

_DISPATCH = {
    'general':         notes.chunk,
    'lecture_note':    notes.chunk,
    'discussion_note': notes.chunk,
    'lecture_slide':   slides.chunk,
    'reading':         reading.chunk,
    'hw_instruction':  homework.chunk_instruction,
    'hw_solution':     homework.chunk_solution,
    'quiz':            assessment.chunk,
    'exam':            assessment.chunk,
    'coding_spec':     coding_spec.chunk,
    'code_file':       code_file.chunk,
}


def route_chunker(doc_type: str, pdf_path: str, full_md: str) -> list[ChunkSpec]:
    fn = _DISPATCH.get(doc_type, notes.chunk)
    return fn(pdf_path, full_md)
