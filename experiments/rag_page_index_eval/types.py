from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PageRecord:
    paper_id: str
    page_number: int
    text: str
    section_name: str | None = None
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexNodeRecord:
    paper_id: str
    node_id: str
    title: str
    start_page: int
    end_page: int
    summary: str = ""
    node_type: str = "section"
    parent_path: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    confidence: float = 1.0

    def pages(self) -> set[int]:
        return set(range(self.start_page, self.end_page + 1))


@dataclass(frozen=True)
class QueryExample:
    query_id: str
    paper_id: str
    question: str
    gold_pages: set[int]
    answer_texts: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalHit:
    paper_id: str
    unit_id: str
    unit_type: str
    score: float
    pages: set[int]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricResult:
    query_id: str
    variant: str
    recall_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    page_range_hit_at_k: float
    answerability_coverage: float
