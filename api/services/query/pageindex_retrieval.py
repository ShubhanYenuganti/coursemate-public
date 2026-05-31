import re


def _extract_page_summaries(nodes: list) -> list[dict]:
    result = []
    for node in nodes:
        start = node.get("start_page")
        if start is None:
            continue
        result.append({
            "start_page": start,
            "end_page": node.get("end_page") or start,
            "summary": (node.get("summary") or "").strip().replace("\n", " "),
        })
    return sorted(result, key=lambda x: x["start_page"])


def _parse_pages(pages_str: str) -> list[int]:
    result = []
    for part in pages_str.split(","):
        part = part.strip()
        m = re.match(r'^(\d+)-(\d+)$', part)
        if m:
            result.extend(range(int(m.group(1)), int(m.group(2)) + 1))
        elif re.match(r'^\d+$', part):
            result.append(int(part))
    return result


def get_course_routing_index(conn, course_id: int, material_ids: list[int] | None = None) -> list[dict]:
    cursor = conn.cursor()
    if material_ids:
        cursor.execute(
            """SELECT cmi.material_id, cmi.material_title, cmi.doc_type, cmi.page_count,
                      cmi.material_summary, cmi.metadata_tags,
                      mpi.index_json->'nodes' AS nodes
               FROM course_material_index cmi
               LEFT JOIN material_page_index mpi USING (material_id)
               WHERE cmi.course_id = %s AND cmi.material_id = ANY(%s)
               ORDER BY cmi.material_id""",
            (course_id, material_ids),
        )
    else:
        cursor.execute(
            """SELECT cmi.material_id, cmi.material_title, cmi.doc_type, cmi.page_count,
                      cmi.material_summary, cmi.metadata_tags,
                      mpi.index_json->'nodes' AS nodes
               FROM course_material_index cmi
               LEFT JOIN material_page_index mpi USING (material_id)
               WHERE cmi.course_id = %s
               ORDER BY cmi.material_id""",
            (course_id,),
        )
    rows = cursor.fetchall()
    cursor.close()
    return [
        {
            "material_id": r["material_id"],
            "title": r["material_title"],
            "doc_type": r["doc_type"],
            "page_count": r["page_count"],
            "summary": r["material_summary"],
            "tags": r["metadata_tags"] or [],
            "sections": _extract_page_summaries(r.get("nodes") or []),
        }
        for r in rows
    ]


def get_material_structure(conn, material_id: int) -> dict:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT index_json FROM material_page_index WHERE material_id = %s",
        (material_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return {"error": f"No index found for material {material_id}. It may not have been indexed yet."}
    return row["index_json"]


def get_page_content(conn, material_id: int, pages: str) -> list[dict]:
    page_numbers = _parse_pages(pages)
    if not page_numbers:
        return []
    cursor = conn.cursor()
    cursor.execute(
        """SELECT page_number, text_content, has_images
           FROM material_page_text
           WHERE material_id = %s AND page_number = ANY(%s)
           ORDER BY page_number""",
        (material_id, page_numbers),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def get_material_relations(conn, course_id: int, material_id: int) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        """SELECT source_id, target_id, relation_type, shared_tags, similarity_score
           FROM course_material_relations
           WHERE course_id = %s AND (source_id = %s OR target_id = %s)
           ORDER BY similarity_score DESC NULLS LAST""",
        (course_id, material_id, material_id),
    )
    rows = cursor.fetchall()
    cursor.close()
    result = []
    for r in rows:
        other_id = r["target_id"] if r["source_id"] == material_id else r["source_id"]
        result.append({
            "other_material_id": other_id,
            "relation_type": r["relation_type"],
            "shared_tags": r["shared_tags"] or [],
            "similarity_score": r["similarity_score"],
        })
    return result
