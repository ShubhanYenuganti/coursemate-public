"""
Assessment chunker (quiz/exam): split at question boundaries.
Keeps answer choices (A/B/C/D) inside the question chunk.
"""
import re

_QUESTION_RE = re.compile(
    r'(?:^|\n)\s*(?:Q(?:uestion)?\s*(\d+)|(\d+)\s*\.)',
    re.IGNORECASE
)
_POINTS_RE = re.compile(r'\((\d+)\s*points?\)|\[(\d+)\s*pts?\]', re.IGNORECASE)


def chunk_assessment(raw_chunks, material_meta):
    """
    Split at question/Q# boundaries. Keep answer choices inside same chunk.
    Returns (parent_dict, [child_dict, ...]).
    """
    doc_type = material_meta.get('doc_type', 'quiz')
    week = material_meta.get('week')

    full_text = '\n'.join(rc.get('text', '') or rc.get('chunk_text', '') for rc in raw_chunks)

    first_match = _QUESTION_RE.search(full_text)
    if not first_match:
        return _no_questions_fallback(full_text, doc_type, week)

    splits = list(_QUESTION_RE.finditer(full_text))
    questions = []
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
        q_num = m.group(1) or m.group(2)
        q_body = full_text[start:end].strip()
        questions.append((q_num, q_body))

    total = len(questions)
    children = []
    for i, (q_num, q_body) in enumerate(questions):
        points_match = _POINTS_RE.search(q_body)
        points_str = None
        if points_match:
            pts = points_match.group(1) or points_match.group(2)
            points_str = f"{pts} pts"

        children.append({
            'chunk_text': q_body,
            'chunk_type': 'question',
            'page_number': None,
            'page_numbers': [],
            'source_type': doc_type,
            'is_parent': False,
            'parent_id': None,
            'section_title': points_str,
            'week': week,
            'position_in_doc': i / max(total, 1),
            'problem_id': f"q{q_num}",
            'related_chunk_ids': [],
            'token_count': len(q_body.split()),
        })

    parent_text = f"{doc_type.capitalize()} with {total} question(s)."
    parent = {
        'chunk_text': parent_text,
        'chunk_type': 'parent',
        'page_number': None,
        'page_numbers': [],
        'source_type': doc_type,
        'is_parent': True,
        'parent_id': None,
        'section_title': None,
        'week': week,
        'position_in_doc': 0.0,
        'problem_id': None,
        'related_chunk_ids': [],
        'token_count': len(parent_text.split()),
    }
    return parent, children


def _no_questions_fallback(full_text, doc_type, week):
    parent = {
        'chunk_text': full_text[:300],
        'chunk_type': 'parent',
        'page_number': None,
        'page_numbers': [],
        'source_type': doc_type,
        'is_parent': True,
        'parent_id': None,
        'section_title': None,
        'week': week,
        'position_in_doc': 0.0,
        'problem_id': None,
        'related_chunk_ids': [],
        'token_count': len(full_text.split()),
    }
    child = {
        'chunk_text': full_text,
        'chunk_type': 'paragraph',
        'page_number': None,
        'page_numbers': [],
        'source_type': doc_type,
        'is_parent': False,
        'parent_id': None,
        'section_title': None,
        'week': week,
        'position_in_doc': 0.5,
        'problem_id': None,
        'related_chunk_ids': [],
        'token_count': len(full_text.split()),
    }
    return parent, [child]
