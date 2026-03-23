"""
Homework solution chunker: mirrors hw_instruction problem boundaries.
Matches instruction chunk IDs via problem number and populates related_chunk_ids.
"""
import re

_PROBLEM_RE = re.compile(
    r'(?:^|\n)\s*(?:Problem|Question|Part|Exercise|Q)\s*(\d+)',
    re.IGNORECASE
)


def chunk_solution(raw_chunks, material_meta, conn):
    """
    Split at problem markers (same regex as hw_instruction).
    Fetch matching instruction chunk IDs from DB to populate related_chunk_ids.
    Returns (parent_dict, [child_dict, ...]).
    """
    doc_type = material_meta.get('doc_type', 'hw_solution')
    material_id = material_meta.get('id', 'unknown')
    course_id = material_meta.get('course_id')
    week = material_meta.get('week')

    full_text = '\n'.join(rc.get('text', '') or rc.get('chunk_text', '') for rc in raw_chunks)

    first_match = _PROBLEM_RE.search(full_text)
    if not first_match:
        return _no_problems_fallback(full_text, doc_type, week)

    splits = list(_PROBLEM_RE.finditer(full_text))
    problems = []
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
        problem_body = full_text[start:end].strip()
        problems.append((m.group(1), problem_body))

    # Fetch hw_instruction chunk IDs for this course/week by problem_id pattern
    instruction_map = {}
    if conn and course_id:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT problem_id, id FROM material_chunks
                WHERE course_id = %s
                  AND source_type = 'hw_instruction'
                  AND problem_id IS NOT NULL
                  AND (%s IS NULL OR week = %s)
            """, (course_id, week, week))
            for row in cursor.fetchall():
                pid_str = row['problem_id']
                # Extract problem number from e.g. "123_p2"
                m = re.search(r'_p(\d+)$', pid_str)
                if m:
                    instruction_map[m.group(1)] = row['id']
            cursor.close()
        except Exception:
            pass  # non-fatal

    total = len(problems)
    children = []
    for i, (problem_num, problem_body) in enumerate(problems):
        problem_id = f"{material_id}_p{problem_num}"
        related = [instruction_map[problem_num]] if problem_num in instruction_map else []

        children.append({
            'chunk_text': problem_body,
            'chunk_type': 'solution',
            'page_number': None,
            'page_numbers': [],
            'source_type': doc_type,
            'is_parent': False,
            'parent_id': None,
            'section_title': f"Problem {problem_num} Solution",
            'week': week,
            'position_in_doc': i / max(total, 1),
            'problem_id': problem_id,
            'related_chunk_ids': related,
            'token_count': len(problem_body.split()),
        })

    parent_text = f"Solutions for {len(problems)} problem(s)."
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
