"""
Coding spec chunker: split at numbered requirement/milestone markers.
"""
import re

_REQ_RE = re.compile(
    r'(?:^|\n)\s*(?:Requirement|Milestone|Feature|Task|Step|Objective)\s*(\d+)|'
    r'(?:^|\n)\s*(\d+)\s*[.)]\s+[A-Z]',
    re.MULTILINE
)


def chunk_coding_spec(raw_chunks, material_meta):
    """
    Split at requirement/milestone markers.
    Returns (parent_dict, [child_dict, ...]).
    """
    doc_type = material_meta.get('doc_type', 'coding_spec')
    week = material_meta.get('week')

    full_text = '\n'.join(rc.get('text', '') or rc.get('chunk_text', '') for rc in raw_chunks)

    splits = list(_REQ_RE.finditer(full_text))
    if not splits:
        return _no_reqs_fallback(full_text, doc_type, week)

    requirements = []
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
        req_num = m.group(1) or m.group(2) or str(i + 1)
        req_body = full_text[start:end].strip()
        requirements.append((req_num, req_body))

    total = len(requirements)
    children = []
    for i, (req_num, req_body) in enumerate(requirements):
        # Determine problem_id prefix based on content
        prefix = 'milestone' if re.search(r'milestone', req_body, re.IGNORECASE) else 'req'
        problem_id = f"{prefix}{req_num}"

        children.append({
            'chunk_text': req_body,
            'chunk_type': 'requirement',
            'page_number': None,
            'page_numbers': [],
            'source_type': doc_type,
            'is_parent': False,
            'parent_id': None,
            'section_title': f"Requirement {req_num}",
            'week': week,
            'position_in_doc': i / max(total, 1),
            'problem_id': problem_id,
            'related_chunk_ids': [],
            'token_count': len(req_body.split()),
        })

    parent_text = f"Coding spec with {total} requirement(s)/milestone(s)."
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


def _no_reqs_fallback(full_text, doc_type, week):
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
