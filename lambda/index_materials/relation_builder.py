import asyncio
import json
import logging
import re

import psycopg

from llm_client import build_relations_prompt, summarize, RELATION_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

_VALID_RELATION_TYPES = {"prerequisite", "extends", "practice_for", "solution_for"}


def _extract_json(raw: str) -> list[dict]:
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def _filter_relations(relations: list[dict], course_id: int) -> list[dict]:
    result = []
    for rel in relations:
        if rel.get("relation_type") not in _VALID_RELATION_TYPES:
            continue
        if float(rel.get("confidence", 0)) < RELATION_CONFIDENCE_THRESHOLD:
            continue
        result.append({
            "course_id": course_id,
            "source_id": int(rel["source_id"]),
            "target_id": int(rel["target_id"]),
            "relation_type": rel["relation_type"],
            "shared_tags": rel.get("shared_tags", []),
            "similarity_score": float(rel.get("confidence", 0)),
        })
    return result


def _build_relations_prompt(target: dict, others: list[dict]) -> str:
    return build_relations_prompt(target, others)


async def build_course_relations(
    db_url: str,
    course_id: int,
    updated_material_id: int,
    api_key: str,
) -> None:
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
        from db import load_course_materials_for_relations, store_material_relations

        rows = load_course_materials_for_relations(conn, course_id)
        target = next((r for r in rows if r["material_id"] == updated_material_id), None)
        if not target:
            logger.warning(
                "Material %d not found in course_material_index for course %d",
                updated_material_id,
                course_id,
            )
            return

        others = [r for r in rows if r["material_id"] != updated_material_id]
        if not others:
            logger.info("No other materials in course %d; skipping relation building", course_id)
            return

        prompt = _build_relations_prompt(target, others)
        try:
            raw = await asyncio.to_thread(summarize, prompt, api_key)
        except Exception as exc:
            logger.warning("LLM call for relations failed: %s", exc)
            return

        raw_relations = _extract_json(raw)
        relations = _filter_relations(raw_relations, course_id)

        if relations:
            store_material_relations(conn, relations)
            conn.commit()
            logger.info(
                "Stored %d relations for course %d (material %d)",
                len(relations),
                course_id,
                updated_material_id,
            )
