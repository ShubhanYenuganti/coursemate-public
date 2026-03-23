"""
Slide chunker: one child per page, grouped under a parent summarising all headings.
"""
import re


def chunk_slides(raw_chunks, material_meta):
    """
    Group extractor output by page_number — each page = one child chunk.
    Parent chunk_text = concatenation of all heading texts across the deck.
    Returns (parent_dict, [child_dict, ...]).
    """
    # Group raw chunks by page number
    pages = {}
    for rc in raw_chunks:
        pn = rc.get('page_number') or 1
        pages.setdefault(pn, []).append(rc)

    sorted_pages = sorted(pages.keys())
    total_pages = len(sorted_pages)
    if total_pages == 0:
        return _empty_parent(material_meta), []

    # Build children (one per page)
    children = []
    heading_texts = []
    for idx, pn in enumerate(sorted_pages):
        page_chunks = pages[pn]
        page_text = '\n'.join(rc.get('text', '') or rc.get('chunk_text', '') for rc in page_chunks).strip()
        heading = next((rc.get('text', '') for rc in page_chunks if rc.get('chunk_type') == 'heading'), None)
        if heading:
            heading_texts.append(heading)

        children.append({
            'chunk_text': page_text,
            'chunk_type': 'slide_page',
            'page_number': pn,
            'page_numbers': [pn],
            'source_type': material_meta.get('doc_type', 'slide'),
            'is_parent': False,
            'parent_id': None,
            'section_title': heading,
            'week': material_meta.get('week'),
            'position_in_doc': idx / total_pages,
            'problem_id': None,
            'related_chunk_ids': [],
            'token_count': len(page_text.split()),
        })

    # Build parent
    parent_text = ' | '.join(heading_texts) if heading_texts else \
                  ' '.join(c['chunk_text'][:80] for c in children[:5])
    parent = {
        'chunk_text': parent_text,
        'chunk_type': 'parent',
        'page_number': None,
        'page_numbers': sorted_pages,
        'source_type': material_meta.get('doc_type', 'slide'),
        'is_parent': True,
        'parent_id': None,
        'section_title': None,
        'week': material_meta.get('week'),
        'position_in_doc': 0.0,
        'problem_id': None,
        'related_chunk_ids': [],
        'token_count': len(parent_text.split()),
    }
    return parent, children


def _empty_parent(material_meta):
    return {
        'chunk_text': '',
        'chunk_type': 'parent',
        'page_number': None,
        'page_numbers': [],
        'source_type': material_meta.get('doc_type', 'slide'),
        'is_parent': True,
        'parent_id': None,
        'section_title': None,
        'week': material_meta.get('week'),
        'position_in_doc': 0.0,
        'problem_id': None,
        'related_chunk_ids': [],
        'token_count': 0,
    }
