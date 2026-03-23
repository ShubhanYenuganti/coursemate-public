"""
Reading chunker: heading-based splitting, preserving chapter structure.
Sections are never merged across headings even if short.
"""
from .lecture_notes import _split_at_headings, _single_parent


def chunk_reading(raw_chunks, material_meta):
    """
    Split at heading boundaries, preserving section structure.
    Returns (parent_dict, [child_dict, ...]).
    """
    doc_type = material_meta.get('doc_type', 'reading')
    week = material_meta.get('week')

    sections = _split_at_headings(raw_chunks)
    total = len(sections)
    if total == 0:
        return _single_parent(raw_chunks, doc_type, week), []

    children = []
    heading_texts = []
    for idx, section in enumerate(sections):
        heading = section.get('heading', '')
        if heading:
            heading_texts.append(heading)
        combined = f"{heading}\n\n{section['body']}".strip() if heading else section['body'].strip()
        pn = section.get('page_number')

        children.append({
            'chunk_text': combined,
            'chunk_type': 'section',
            'page_number': pn,
            'page_numbers': section.get('page_numbers', [pn] if pn else []),
            'source_type': doc_type,
            'is_parent': False,
            'parent_id': None,
            'section_title': heading or None,
            'week': week,
            'position_in_doc': idx / total,
            'problem_id': None,
            'related_chunk_ids': [],
            'token_count': len(combined.split()),
        })

    parent_text = ' | '.join(heading_texts) if heading_texts else \
                  (children[0]['chunk_text'][:200] if children else '')
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
