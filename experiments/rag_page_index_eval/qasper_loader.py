from __future__ import annotations

import json
from pathlib import Path

from .types import PageRecord, QueryExample


def _answer_texts(qa: dict) -> tuple[str, ...]:
    out = []
    for item in qa.get("answers", []):
        answer = item.get("answer", item)
        for key in ("free_form_answer", "extractive_spans", "yes_no"):
            value = answer.get(key)
            if isinstance(value, list):
                out.extend(str(item) for item in value if item)
            elif value:
                out.append(str(value))
    return tuple(out)


def load_qasper_json(path: Path) -> tuple[list[PageRecord], list[QueryExample]]:
    raw = json.loads(path.read_text())
    pages: list[PageRecord] = []
    queries: list[QueryExample] = []

    for paper in raw:
        paper_id = paper.get("paper_id") or paper.get("id")
        page_num = 1
        for section in paper.get("full_text", []):
            name = section.get("section_name") or "Unknown"
            text = "\n".join(section.get("paragraphs") or [])
            pages.append(PageRecord(paper_id, page_num, text, name, (name,)))
            page_num += 1

        for qa in paper.get("qas", []):
            evidence = qa.get("evidence") or []
            gold_pages = set()
            for item in evidence:
                evidence_text = str(item)
                for page in pages:
                    if page.paper_id == paper_id and evidence_text and evidence_text in page.text:
                        gold_pages.add(page.page_number)

            queries.append(
                QueryExample(
                    query_id=qa.get("question_id") or qa.get("id") or f"{paper_id}:{len(queries)}",
                    paper_id=paper_id,
                    question=qa["question"],
                    gold_pages=gold_pages,
                    answer_texts=_answer_texts(qa),
                    metadata={"title": paper.get("title", "")},
                )
            )

    return pages, queries
