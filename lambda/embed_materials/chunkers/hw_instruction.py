"""
Homework instruction chunker: detect preamble + split at problem boundaries.
"""
import re

_PROBLEM_RE = re.compile(
    r'(?:^|\n)\s*(?:Problem|Question|Part|Exercise|Q)\s*(\d+)',
    re.IGNORECASE
)


def chunk_hw(raw_chunks, material_meta):
    """
    Detect preamble text (before first problem marker) and split into per-problem children.
    Each problem child has preamble prepended to its chunk_text.
    Returns (parent_dict, [child_dict, ...]).
    """
    doc_type = material_meta.get('doc_type', 'hw_instruction')
    material_id = material_meta.get('id', 'unknown')
    week = material_meta.get('week')

    full_text = '\n'.join(rc.get('text', '') or rc.get('chunk_text', '') for rc in raw_chunks)

    # Find first problem marker
    first_match = _PROBLEM_RE.search(full_text)
    if not first_match:
        # No problem markers — fall back to single parent + single child
        return _no_problems_fallback(full_text, doc_type, week)

    preamble_text = full_text[:first_match.start()].strip()

    # Split at all problem markers
    splits = list(_PROBLEM_RE.finditer(full_text))
    problems = []
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
        problem_num = m.group(1)
        problem_body = full_text[start:end].strip()
        problems.append((problem_num, problem_body))

    total = len(problems) + (1 if preamble_text else 0)
    children = []
    idx = 0

    # Preamble as standalone child
    if preamble_text:
        children.append({
            'chunk_text': preamble_text,
            'chunk_type': 'preamble',
            'page_number': None,
            'page_numbers': [],
            'source_type': doc_type,
            'is_parent': False,
            'parent_id': None,
            'section_title': 'Assignment Instructions',
            'week': week,
            'position_in_doc': 0.0,
            'problem_id': None,
            'related_chunk_ids': [],
            'token_count': len(preamble_text.split()),
        })
        idx = 1

    for i, (problem_num, problem_body) in enumerate(problems):
        text_with_preamble = f"{preamble_text}\n\n{problem_body}".strip() if preamble_text else problem_body
        problem_id = f"{material_id}_p{problem_num}"

        children.append({
            'chunk_text': text_with_preamble,
            'chunk_type': 'problem',
            'page_number': None,
            'page_numbers': [],
            'source_type': doc_type,
            'is_parent': False,
            'parent_id': None,
            'section_title': f"Problem {problem_num}",
            'week': week,
            'position_in_doc': (idx + i) / max(total, 1),
            'problem_id': problem_id,
            'related_chunk_ids': [],
            'token_count': len(text_with_preamble.split()),
        })

    parent_text = f"Assignment with {len(problems)} problem(s). " + \
                  (preamble_text[:200] if preamble_text else '')
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


def _no_problems_fallback(full_text, doc_type, week):
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
