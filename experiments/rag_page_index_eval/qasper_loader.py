from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import PageRecord, QueryExample


_HF_PARQUET_URLS = {
    "train": "https://huggingface.co/datasets/allenai/qasper/resolve/refs%2Fconvert%2Fparquet/qasper/train/0000.parquet",
    "validation": "https://huggingface.co/datasets/allenai/qasper/resolve/refs%2Fconvert%2Fparquet/qasper/validation/0000.parquet",
    "test": "https://huggingface.co/datasets/allenai/qasper/resolve/refs%2Fconvert%2Fparquet/qasper/test/0000.parquet",
}


def _answer_texts(qa: dict) -> tuple[str, ...]:
    out = []
    for item in qa.get("answers", []):
        answer = item.get("answer", item)
        for key in ("free_form_answer", "extractive_spans", "yes_no"):
            value = answer.get(key)
            for answer_item in _as_list(value):
                if answer_item is not None and str(answer_item):
                    out.append(str(answer_item))
    return tuple(out)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        value = tolist()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _paper_items(raw) -> list[dict]:
    if isinstance(raw, dict):
        papers = []
        for paper_id, paper in raw.items():
            item = dict(paper)
            item.setdefault("paper_id", paper_id)
            papers.append(item)
        return papers
    return list(raw)


def _evidence_strings(qa: dict) -> tuple[str, ...]:
    evidence: list[str] = []
    for item in _as_list(qa.get("evidence")):
        if item:
            evidence.append(str(item))

    for answer_item in qa.get("answers", []):
        answer = answer_item.get("answer", answer_item)
        answer_evidence = answer.get("evidence")
        if answer_evidence is None:
            answer_evidence = answer_item.get("evidence")
        for item in _as_list(answer_evidence):
            if item:
                evidence.append(str(item))

    return tuple(dict.fromkeys(evidence))


def load_qasper_json(path: Path) -> tuple[list[PageRecord], list[QueryExample]]:
    raw = json.loads(path.read_text())
    pages: list[PageRecord] = []
    queries: list[QueryExample] = []

    for paper in _paper_items(raw):
        paper_id = paper.get("paper_id") or paper.get("id")
        page_num = 1
        for section in paper.get("full_text", []):
            name = section.get("section_name") or "Unknown"
            text = "\n".join(section.get("paragraphs") or [])
            pages.append(PageRecord(paper_id, page_num, text, name, (name,)))
            page_num += 1

        for qa in paper.get("qas", []):
            evidence = _evidence_strings(qa)
            gold_pages = set()
            matched: list[str] = []
            unmatched: list[str] = []
            for item in evidence:
                evidence_text = str(item).strip()
                found = False
                for page in pages:
                    if page.paper_id == paper_id and evidence_text and evidence_text in page.text:
                        gold_pages.add(page.page_number)
                        found = True
                if found:
                    matched.append(evidence_text)
                elif evidence_text:
                    unmatched.append(evidence_text)

            queries.append(
                QueryExample(
                    query_id=qa.get("question_id") or qa.get("id") or f"{paper_id}:{len(queries)}",
                    paper_id=paper_id,
                    question=qa["question"],
                    gold_pages=gold_pages,
                    answer_texts=_answer_texts(qa),
                    metadata={
                        "title": paper.get("title", ""),
                        "evidence_strings": tuple(evidence),
                        "matched_evidence_strings": tuple(dict.fromkeys(matched)),
                        "unmatched_evidence_strings": tuple(dict.fromkeys(unmatched)),
                    },
                )
            )

    return pages, queries


def load_qasper_huggingface(
    dataset_name: str = "allenai/qasper",
    split: str = "test",
) -> tuple[list[PageRecord], list[QueryExample]]:
    if dataset_name != "allenai/qasper":
        raise ValueError("Only allenai/qasper is currently supported for Hugging Face loading.")
    parquet_url = _HF_PARQUET_URLS.get(split)
    if not parquet_url:
        raise ValueError(f"Unsupported QASPER split: {split!r}. Expected one of {sorted(_HF_PARQUET_URLS)}")
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Hugging Face parquet loading requires pandas with parquet support. "
            "Install pandas/pyarrow or use --dataset-source json."
        ) from exc

    dataset = pd.read_parquet(parquet_url).to_dict("records")
    pages: list[PageRecord] = []
    queries: list[QueryExample] = []

    for paper in dataset:
        paper_id = str(paper.get("id") or paper.get("paper_id") or len(pages))
        title = paper.get("title") or ""
        page_num = 1
        paper_pages: list[PageRecord] = []
        full_text = paper.get("full_text") or []
        if isinstance(full_text, dict):
            sections = [
                {"section_name": name, "paragraphs": paragraphs}
                for name, paragraphs in zip(
                    _as_list(full_text.get("section_name")),
                    _as_list(full_text.get("paragraphs")),
                )
            ]
        else:
            sections = full_text
        for section in sections:
            name = section.get("section_name") or "Unknown"
            text = "\n".join(str(paragraph) for paragraph in _as_list(section.get("paragraphs")))
            page = PageRecord(paper_id, page_num, text, name, (name,))
            pages.append(page)
            paper_pages.append(page)
            page_num += 1

        qas = paper.get("qas") or {}
        questions = _as_list(qas.get("question"))
        question_ids = _as_list(qas.get("question_id"))
        answers_list = _as_list(qas.get("answers"))
        for idx, question in enumerate(questions):
            answers = answers_list[idx] if idx < len(answers_list) else {}
            qa = {
                "question": question,
                "question_id": question_ids[idx] if idx < len(question_ids) else f"{paper_id}:{idx}",
                "answers": [
                    {"answer": answer}
                    for answer in _as_list(answers.get("answer") if isinstance(answers, dict) else answers)
                ],
            }
            evidence = _evidence_strings(qa)
            gold_pages = set()
            matched: list[str] = []
            unmatched: list[str] = []
            for item in evidence:
                evidence_text = str(item).strip()
                found = False
                for page in paper_pages:
                    if evidence_text and evidence_text in page.text:
                        gold_pages.add(page.page_number)
                        found = True
                if found:
                    matched.append(evidence_text)
                elif evidence_text:
                    unmatched.append(evidence_text)

            queries.append(
                QueryExample(
                    query_id=str(qa["question_id"]),
                    paper_id=paper_id,
                    question=str(question),
                    gold_pages=gold_pages,
                    answer_texts=_answer_texts(qa),
                    metadata={
                        "title": title,
                        "evidence_strings": tuple(evidence),
                        "matched_evidence_strings": tuple(dict.fromkeys(matched)),
                        "unmatched_evidence_strings": tuple(dict.fromkeys(unmatched)),
                    },
                )
            )

    return pages, queries
