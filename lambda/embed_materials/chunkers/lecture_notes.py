"""
Lecture notes chunker: heading-based splitting, treating worked examples as indivisible.
"""
import re

_EXAMPLE_MARKERS = re.compile(
    r'^\s*(Example|Proof|Solution|Theorem|Lemma|Corollary|Definition|Remark)\s*[:\d]',
    re.IGNORECASE | re.MULTILINE
)


def chunk_notes(raw_chunks, material_meta):
    """
    Split at heading boundaries. Merge worked examples/equation blocks into their
    enclosing heading section. Returns (parent_dict, [child_dict, ...]).
    """
    doc_type = material_meta.get('doc_type', 'lecture_note')
    week = material_meta.get('week')

    # Group raw chunks into sections at heading boundaries
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


def _split_at_headings(raw_chunks):
    """Group raw extractor chunks into sections delimited by heading chunks."""
    sections = []
    current = None
    for rc in raw_chunks:
        text = rc.get('text', '') or rc.get('chunk_text', '')
        ctype = rc.get('chunk_type', '')
        pn = rc.get('page_number')

        if ctype == 'heading':
            if current is not None:
                sections.append(current)
            current = {
                'heading': text.strip(),
                'body': '',
                'page_number': pn,
                'page_numbers': [pn] if pn else [],
            }
        else:
            if current is None:
                current = {'heading': '', 'body': '', 'page_number': pn, 'page_numbers': []}
            current['body'] += '\n' + text
            if pn and pn not in current['page_numbers']:
                current['page_numbers'].append(pn)

    if current is not None:
        sections.append(current)
    return sections


def _single_parent(raw_chunks, doc_type, week):
    text = '\n'.join(rc.get('text', '') or rc.get('chunk_text', '') for rc in raw_chunks).strip()
    return {
        'chunk_text': text[:300],
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
        'token_count': len(text.split()),
    }
