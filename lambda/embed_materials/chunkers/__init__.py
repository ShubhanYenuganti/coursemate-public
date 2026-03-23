"""
Type-dispatch chunker.
Each chunker receives raw extractor output (list of dicts with text/chunk_text, chunk_type, page_number)
and returns (parent_chunk_dict, [child_chunk_dict, ...]).
"""
from .slides import chunk_slides
from .lecture_notes import chunk_notes
from .reading import chunk_reading
from .hw_instruction import chunk_hw
from .hw_solution import chunk_solution
from .assessment import chunk_assessment
from .coding_spec import chunk_coding_spec

_DISPATCH = {
    'slide':          chunk_slides,
    'lecture_note':   chunk_notes,
    'reading':        chunk_reading,
    'hw_instruction': chunk_hw,
    'hw_solution':    chunk_solution,
    'quiz':           chunk_assessment,
    'exam':           chunk_assessment,
    'coding_spec':    chunk_coding_spec,
    'code_file':      chunk_notes,   # function/class boundaries via heading detection
    'default':        chunk_slides,  # per-page (atomic, no special logic)
}


def chunk_by_type(doc_type, raw_chunks, material_meta, conn=None):
    """
    Dispatch to the appropriate chunker based on doc_type.
    hw_solution receives conn for cross-referencing instruction chunks.
    Returns (parent_dict, [child_dict, ...]).
    """
    fn = _DISPATCH.get(doc_type, chunk_slides)
    if doc_type == 'hw_solution':
        return fn(raw_chunks, material_meta, conn)
    return fn(raw_chunks, material_meta)
