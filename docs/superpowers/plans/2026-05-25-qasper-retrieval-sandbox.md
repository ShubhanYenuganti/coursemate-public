# QASPER Retrieval Sandbox Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Create a separate retrieval-only sandbox that evaluates the `lambda/index_materials` page-index approach against QASPER-style academic-document QA. The sandbox must not call production Lambda, S3, or production Postgres. It should produce local JSONL/CSV metrics for retrieval variants.

Primary dataset:
- QASPER: academic QA over NLP papers. Public references:
  - `allenai/qasper` on Hugging Face
  - paper: "A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers"

Supported retrieval variants:
- `page_bm25`
- `section_bm25`
- `two_stage`
- `hybrid`

Metrics:
- `Recall@k`
- `MRR@k`
- `nDCG@k`
- `page_range_hit@k`
- `answerability_coverage`

## Non-Goals

- No answer generation.
- No grading generated answers.
- No production database writes.
- No S3.
- No cloud Lambda invocation.
- No requirement to download the full QASPER corpus in CI.

## File Structure

- Create: `experiments/rag_page_index_eval/README.md`
  - Usage and dataset notes.

- Create: `experiments/rag_page_index_eval/__init__.py`
  - Package marker.

- Create: `experiments/rag_page_index_eval/types.py`
  - Dataclasses for `PageRecord`, `IndexNodeRecord`, `QueryExample`, `RetrievalHit`, `MetricResult`.

- Create: `experiments/rag_page_index_eval/qasper_loader.py`
  - Loads QASPER from local JSON or Hugging Face when optional deps are installed.
  - Normalizes examples to retrieval-only query records.

- Create: `experiments/rag_page_index_eval/local_index_adapter.py`
  - Runs page-index builders locally and emits JSON artifacts.
  - Does not require Lambda event shape.

- Create: `experiments/rag_page_index_eval/bm25.py`
  - Tiny local BM25 implementation using Python stdlib only.

- Create: `experiments/rag_page_index_eval/retrievers.py`
  - Implements `page_bm25`, `section_bm25`, `two_stage`, `hybrid`.

- Create: `experiments/rag_page_index_eval/metrics.py`
  - Retrieval metrics.

- Create: `experiments/rag_page_index_eval/run_eval.py`
  - CLI entrypoint.

- Create: `experiments/rag_page_index_eval/tests/test_bm25.py`
- Create: `experiments/rag_page_index_eval/tests/test_metrics.py`
- Create: `experiments/rag_page_index_eval/tests/test_retrievers.py`
- Create: `experiments/rag_page_index_eval/fixtures/mini_qasper.json`
  - Tiny synthetic QASPER-shaped fixture for deterministic tests.

## Task 1: Define Retrieval Data Types

**Files:**
- Create: `experiments/rag_page_index_eval/types.py`
- Create: `experiments/rag_page_index_eval/__init__.py`

- [ ] **Step 1: Create tests through importing the types from later tests**

No separate type test needed. The following tasks will import these classes.

- [ ] **Step 2: Add dataclasses**

Create `types.py`:

```python
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
```

- [ ] **Step 3: Add package marker**

Create empty `__init__.py`.

- [ ] **Step 4: Run import smoke**

```bash
python - <<'PY'
from experiments.rag_page_index_eval.types import PageRecord
print(PageRecord(paper_id="p", page_number=1, text="ok"))
PY
```

- [ ] **Step 5: Commit**

```bash
git add experiments/rag_page_index_eval/types.py experiments/rag_page_index_eval/__init__.py
git commit -m "Add retrieval sandbox data types"
```

## Task 2: BM25 Baseline

**Files:**
- Create: `experiments/rag_page_index_eval/bm25.py`
- Create: `experiments/rag_page_index_eval/tests/test_bm25.py`

- [ ] **Step 1: Write failing tests**

```python
from experiments.rag_page_index_eval.bm25 import BM25Index


def test_bm25_ranks_matching_document_first():
    index = BM25Index()
    index.add("a", "transformer attention model")
    index.add("b", "database connection pool")

    hits = index.search("attention transformer", top_k=2)

    assert hits[0][0] == "a"
    assert hits[0][1] > hits[1][1]


def test_bm25_returns_empty_for_empty_index():
    index = BM25Index()
    assert index.search("anything") == []
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest experiments/rag_page_index_eval/tests/test_bm25.py -v
```

- [ ] **Step 3: Implement stdlib BM25**

```python
import math
import re
from collections import Counter, defaultdict


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: dict[str, Counter[str]] = {}
        self.lengths: dict[str, int] = {}
        self.df: defaultdict[str, int] = defaultdict(int)

    def add(self, doc_id: str, text: str) -> None:
        counts = Counter(tokenize(text))
        if doc_id in self.docs:
            raise ValueError(f"duplicate doc_id: {doc_id}")
        self.docs[doc_id] = counts
        self.lengths[doc_id] = sum(counts.values())
        for term in counts:
            self.df[term] += 1

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self.docs:
            return []
        terms = tokenize(query)
        avgdl = sum(self.lengths.values()) / max(len(self.lengths), 1)
        scored = []
        n_docs = len(self.docs)
        for doc_id, counts in self.docs.items():
            dl = self.lengths[doc_id] or 1
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf == 0:
                    continue
                idf = math.log(1 + (n_docs - self.df[term] + 0.5) / (self.df[term] + 0.5))
                denom = tf + self.k1 * (1 - self.b + self.b * dl / avgdl)
                score += idf * (tf * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
```

- [ ] **Step 4: Run tests**

```bash
pytest experiments/rag_page_index_eval/tests/test_bm25.py -v
```

- [ ] **Step 5: Commit**

```bash
git add experiments/rag_page_index_eval/bm25.py experiments/rag_page_index_eval/tests/test_bm25.py
git commit -m "Add BM25 retrieval baseline"
```

## Task 3: Retrieval Metrics

**Files:**
- Create: `experiments/rag_page_index_eval/metrics.py`
- Create: `experiments/rag_page_index_eval/tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

```python
from experiments.rag_page_index_eval.metrics import evaluate_hits
from experiments.rag_page_index_eval.types import QueryExample, RetrievalHit


def hit(unit_id, pages, score=1.0):
    return RetrievalHit(
        paper_id="p1",
        unit_id=unit_id,
        unit_type="page",
        score=score,
        pages=set(pages),
        text="",
    )


def test_evaluate_hits_computes_recall_and_mrr():
    query = QueryExample(
        query_id="q1",
        paper_id="p1",
        question="where is attention described?",
        gold_pages={2},
    )
    result = evaluate_hits(query, [hit("p1", [1]), hit("p2", [2])], variant="page_bm25", k=2)

    assert result.recall_at_k == 1.0
    assert result.mrr_at_k == 0.5
    assert result.page_range_hit_at_k == 1.0


def test_evaluate_hits_handles_no_gold_pages():
    query = QueryExample("q2", "p1", "unanswerable?", set())
    result = evaluate_hits(query, [hit("p1", [1])], variant="page_bm25", k=2)

    assert result.answerability_coverage == 0.0
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest experiments/rag_page_index_eval/tests/test_metrics.py -v
```

- [ ] **Step 3: Implement metrics**

```python
import math

from .types import MetricResult, QueryExample, RetrievalHit


def _relevant(hit: RetrievalHit, gold_pages: set[int]) -> bool:
    return bool(hit.pages & gold_pages)


def evaluate_hits(query: QueryExample, hits: list[RetrievalHit], variant: str, k: int) -> MetricResult:
    top = hits[:k]
    if not query.gold_pages:
        return MetricResult(query.query_id, variant, 0.0, 0.0, 0.0, 0.0, 0.0)

    relevant = [_relevant(hit, query.gold_pages) for hit in top]
    recall = 1.0 if any(relevant) else 0.0

    mrr = 0.0
    for idx, is_rel in enumerate(relevant, start=1):
        if is_rel:
            mrr = 1.0 / idx
            break

    dcg = 0.0
    for idx, is_rel in enumerate(relevant, start=1):
        if is_rel:
            dcg += 1.0 / math.log2(idx + 1)
    ideal_hits = min(1, len(top))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 0.0

    return MetricResult(
        query_id=query.query_id,
        variant=variant,
        recall_at_k=recall,
        mrr_at_k=mrr,
        ndcg_at_k=ndcg,
        page_range_hit_at_k=recall,
        answerability_coverage=1.0,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest experiments/rag_page_index_eval/tests/test_metrics.py -v
```

- [ ] **Step 5: Commit**

```bash
git add experiments/rag_page_index_eval/metrics.py experiments/rag_page_index_eval/tests/test_metrics.py
git commit -m "Add retrieval-only metrics"
```

## Task 4: Retriever Variants

**Files:**
- Create: `experiments/rag_page_index_eval/retrievers.py`
- Create: `experiments/rag_page_index_eval/tests/test_retrievers.py`

- [ ] **Step 1: Write failing tests for all retrieval variants**

```python
from experiments.rag_page_index_eval.retrievers import (
    HybridRetriever,
    PageBM25Retriever,
    SectionBM25Retriever,
    TwoStageRetriever,
)
from experiments.rag_page_index_eval.types import IndexNodeRecord, PageRecord


PAGES = [
    PageRecord("p1", 1, "intro background", "Intro", ("Intro",)),
    PageRecord("p1", 2, "transformer attention mechanism", "Methods", ("Methods",)),
    PageRecord("p1", 3, "results accuracy", "Results", ("Results",)),
]

NODES = [
    IndexNodeRecord("p1", "n_intro", "Intro", 1, 1, "background"),
    IndexNodeRecord("p1", "n_methods", "Methods", 2, 2, "transformer attention", keywords=("attention",)),
    IndexNodeRecord("p1", "n_results", "Results", 3, 3, "accuracy"),
]


def test_page_bm25_retrieves_matching_page():
    hits = PageBM25Retriever(PAGES).retrieve("attention", top_k=2)
    assert hits[0].pages == {2}


def test_section_bm25_retrieves_matching_node():
    hits = SectionBM25Retriever(NODES).retrieve("attention", top_k=2)
    assert hits[0].unit_id == "n_methods"


def test_two_stage_returns_pages_inside_best_node():
    hits = TwoStageRetriever(PAGES, NODES).retrieve("attention", top_k=2)
    assert hits[0].pages == {2}


def test_hybrid_combines_page_and_section_hits():
    hits = HybridRetriever(PAGES, NODES).retrieve("attention", top_k=2)
    assert hits[0].pages == {2}
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest experiments/rag_page_index_eval/tests/test_retrievers.py -v
```

- [ ] **Step 3: Implement retrievers**

```python
from .bm25 import BM25Index
from .types import IndexNodeRecord, PageRecord, RetrievalHit


class PageBM25Retriever:
    variant = "page_bm25"

    def __init__(self, pages: list[PageRecord]):
        self.pages = {f"{p.paper_id}:page:{p.page_number}": p for p in pages}
        self.index = BM25Index()
        for unit_id, page in self.pages.items():
            text = " ".join([page.section_name or "", " ".join(page.section_path), page.text])
            self.index.add(unit_id, text)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        hits = []
        for unit_id, score in self.index.search(query, top_k):
            page = self.pages[unit_id]
            hits.append(RetrievalHit(page.paper_id, unit_id, "page", score, {page.page_number}, page.text))
        return hits


class SectionBM25Retriever:
    variant = "section_bm25"

    def __init__(self, nodes: list[IndexNodeRecord]):
        self.nodes = {f"{n.paper_id}:node:{n.node_id}": n for n in nodes}
        self.index = BM25Index()
        for unit_id, node in self.nodes.items():
            text = " ".join([node.title, node.summary, " ".join(node.parent_path), " ".join(node.keywords)])
            self.index.add(unit_id, text)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        hits = []
        for unit_id, score in self.index.search(query, top_k):
            node = self.nodes[unit_id]
            hits.append(RetrievalHit(
                node.paper_id,
                node.node_id,
                "section",
                score,
                node.pages(),
                " ".join([node.title, node.summary]),
            ))
        return hits


class TwoStageRetriever:
    variant = "two_stage"

    def __init__(self, pages: list[PageRecord], nodes: list[IndexNodeRecord]):
        self.pages = pages
        self.section = SectionBM25Retriever(nodes)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        node_hits = self.section.retrieve(query, top_k=5)
        candidate_pages = [p for p in self.pages if any(p.paper_id == h.paper_id and p.page_number in h.pages for h in node_hits)]
        return PageBM25Retriever(candidate_pages).retrieve(query, top_k=top_k) if candidate_pages else []


class HybridRetriever:
    variant = "hybrid"

    def __init__(self, pages: list[PageRecord], nodes: list[IndexNodeRecord]):
        self.page = PageBM25Retriever(pages)
        self.section = SectionBM25Retriever(nodes)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        scores: dict[tuple[str, tuple[int, ...]], RetrievalHit] = {}
        for weight, hit_list in [(0.65, self.page.retrieve(query, top_k * 2)), (0.35, self.section.retrieve(query, top_k * 2))]:
            for hit in hit_list:
                key = (hit.paper_id, tuple(sorted(hit.pages)))
                prev = scores.get(key)
                score = hit.score * weight + (prev.score if prev else 0.0)
                scores[key] = RetrievalHit(hit.paper_id, hit.unit_id, hit.unit_type, score, hit.pages, hit.text, hit.metadata)
        return sorted(scores.values(), key=lambda h: h.score, reverse=True)[:top_k]
```

- [ ] **Step 4: Run tests**

```bash
pytest experiments/rag_page_index_eval/tests/test_retrievers.py -v
```

- [ ] **Step 5: Commit**

```bash
git add experiments/rag_page_index_eval/retrievers.py experiments/rag_page_index_eval/tests/test_retrievers.py
git commit -m "Add retrieval sandbox variants"
```

## Task 5: QASPER Loader and Fixture

**Files:**
- Create: `experiments/rag_page_index_eval/qasper_loader.py`
- Create: `experiments/rag_page_index_eval/fixtures/mini_qasper.json`
- Create: `experiments/rag_page_index_eval/tests/test_qasper_loader.py`

- [ ] **Step 1: Create mini fixture**

`mini_qasper.json`:

```json
[
  {
    "paper_id": "paper_1",
    "title": "Attention Paper",
    "full_text": [
      {"section_name": "Introduction", "paragraphs": ["This paper studies sequence models."]},
      {"section_name": "Methods", "paragraphs": ["The transformer attention mechanism is described here."]},
      {"section_name": "Results", "paragraphs": ["Accuracy improves on the benchmark."]}
    ],
    "qas": [
      {
        "question_id": "q1",
        "question": "Where is the attention mechanism described?",
        "answers": [{"answer": {"free_form_answer": "In the methods section."}}],
        "evidence": ["The transformer attention mechanism is described here."]
      }
    ]
  }
]
```

- [ ] **Step 2: Write failing loader tests**

```python
from pathlib import Path

from experiments.rag_page_index_eval.qasper_loader import load_qasper_json


def test_load_qasper_json_creates_pages_and_queries():
    fixture = Path("experiments/rag_page_index_eval/fixtures/mini_qasper.json")
    pages, queries = load_qasper_json(fixture)

    assert len(pages) == 3
    assert len(queries) == 1
    assert queries[0].gold_pages == {2}
```

- [ ] **Step 3: Run test to verify failure**

```bash
pytest experiments/rag_page_index_eval/tests/test_qasper_loader.py -v
```

- [ ] **Step 4: Implement loader**

```python
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
                out.extend(str(v) for v in value if v)
            elif value:
                out.append(str(value))
    return tuple(out)


def load_qasper_json(path: Path) -> tuple[list[PageRecord], list[QueryExample]]:
    raw = json.loads(path.read_text())
    pages: list[PageRecord] = []
    queries: list[QueryExample] = []

    for paper in raw:
        paper_id = paper.get("paper_id") or paper.get("id")
        section_to_page = {}
        page_num = 1
        for section in paper.get("full_text", []):
            name = section.get("section_name") or "Unknown"
            text = "\\n".join(section.get("paragraphs") or [])
            pages.append(PageRecord(paper_id, page_num, text, name, (name,)))
            section_to_page[name] = page_num
            page_num += 1

        for qa in paper.get("qas", []):
            evidence = qa.get("evidence") or []
            gold_pages = set()
            for ev in evidence:
                ev_text = str(ev)
                for page in pages:
                    if page.paper_id == paper_id and ev_text and ev_text in page.text:
                        gold_pages.add(page.page_number)
            queries.append(QueryExample(
                query_id=qa.get("question_id") or qa.get("id") or f"{paper_id}:{len(queries)}",
                paper_id=paper_id,
                question=qa["question"],
                gold_pages=gold_pages,
                answer_texts=_answer_texts(qa),
                metadata={"title": paper.get("title", "")},
            ))

    return pages, queries
```

- [ ] **Step 5: Run tests**

```bash
pytest experiments/rag_page_index_eval/tests/test_qasper_loader.py -v
```

- [ ] **Step 6: Commit**

```bash
git add experiments/rag_page_index_eval/qasper_loader.py experiments/rag_page_index_eval/fixtures/mini_qasper.json experiments/rag_page_index_eval/tests/test_qasper_loader.py
git commit -m "Add QASPER fixture loader"
```

## Task 6: Local Page-Index Adapter

**Files:**
- Create: `experiments/rag_page_index_eval/local_index_adapter.py`
- Create: `experiments/rag_page_index_eval/tests/test_local_index_adapter.py`

- [ ] **Step 1: Write failing adapter test**

```python
from experiments.rag_page_index_eval.local_index_adapter import build_index_records
from experiments.rag_page_index_eval.types import PageRecord


def test_build_index_records_creates_section_nodes():
    pages = [
        PageRecord("p1", 1, "Intro text", "Intro", ("Intro",)),
        PageRecord("p1", 2, "Attention text", "Methods", ("Methods",)),
    ]

    nodes = build_index_records("p1", pages)

    assert [n.title for n in nodes] == ["Intro", "Methods"]
    assert nodes[1].start_page == 2
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest experiments/rag_page_index_eval/tests/test_local_index_adapter.py -v
```

- [ ] **Step 3: Implement adapter**

```python
from itertools import groupby

from .types import IndexNodeRecord, PageRecord


def build_index_records(paper_id: str, pages: list[PageRecord]) -> list[IndexNodeRecord]:
    records = []
    ordered = sorted([p for p in pages if p.paper_id == paper_id], key=lambda p: p.page_number)
    for section_name, group in groupby(ordered, key=lambda p: p.section_name or "Unknown"):
        section_pages = list(group)
        start = section_pages[0].page_number
        end = section_pages[-1].page_number
        text = " ".join(p.text for p in section_pages)
        words = text.split()
        summary = " ".join(words[:80])
        keywords = tuple(sorted(set(w.lower().strip(".,:;()[]") for w in words if len(w) > 5))[:20])
        records.append(IndexNodeRecord(
            paper_id=paper_id,
            node_id=f"{paper_id}:{section_name}:{start}-{end}",
            title=section_name,
            start_page=start,
            end_page=end,
            summary=summary,
            node_type="section",
            parent_path=(section_name,),
            keywords=keywords,
        ))
    return records
```

- [ ] **Step 4: Run tests**

```bash
pytest experiments/rag_page_index_eval/tests/test_local_index_adapter.py -v
```

- [ ] **Step 5: Commit**

```bash
git add experiments/rag_page_index_eval/local_index_adapter.py experiments/rag_page_index_eval/tests/test_local_index_adapter.py
git commit -m "Add local page-index adapter"
```

## Task 7: CLI Eval Runner

**Files:**
- Create: `experiments/rag_page_index_eval/run_eval.py`
- Create: `experiments/rag_page_index_eval/README.md`

- [ ] **Step 1: Add CLI runner**

```python
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from .local_index_adapter import build_index_records
from .metrics import evaluate_hits
from .qasper_loader import load_qasper_json
from .retrievers import HybridRetriever, PageBM25Retriever, SectionBM25Retriever, TwoStageRetriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasper-json", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    pages, queries = load_qasper_json(Path(args.qasper_json))
    paper_ids = sorted({p.paper_id for p in pages})
    nodes = []
    for paper_id in paper_ids:
        nodes.extend(build_index_records(paper_id, pages))

    retrievers = [
        PageBM25Retriever(pages),
        SectionBM25Retriever(nodes),
        TwoStageRetriever(pages, nodes),
        HybridRetriever(pages, nodes),
    ]

    rows = []
    for retriever in retrievers:
        for query in queries:
            hits = [h for h in retriever.retrieve(query.question, top_k=args.k) if h.paper_id == query.paper_id]
            result = evaluate_hits(query, hits, retriever.variant, args.k)
            rows.append(result.__dict__)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)
    for variant, items in by_variant.items():
        recall = sum(x["recall_at_k"] for x in items) / len(items)
        mrr = sum(x["mrr_at_k"] for x in items) / len(items)
        print(f"{variant}: recall@{args.k}={recall:.3f} mrr@{args.k}={mrr:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add README**

```markdown
# RAG Page Index Retrieval Eval

Retrieval-only sandbox for testing `lambda/index_materials` page-index ideas.

Run the fixture:

```bash
python -m experiments.rag_page_index_eval.run_eval \
  --qasper-json experiments/rag_page_index_eval/fixtures/mini_qasper.json \
  --out experiments/rag_page_index_eval/out/mini_results.csv \
  --k 5
```

Variants:
- `page_bm25`: searches page text.
- `section_bm25`: searches index node title/summary/keywords.
- `two_stage`: retrieves index nodes, then searches pages in selected node ranges.
- `hybrid`: combines page and section scores.

Metrics:
- `recall_at_k`
- `mrr_at_k`
- `ndcg_at_k`
- `page_range_hit_at_k`
- `answerability_coverage`
```

- [ ] **Step 3: Run fixture eval**

```bash
python -m experiments.rag_page_index_eval.run_eval \
  --qasper-json experiments/rag_page_index_eval/fixtures/mini_qasper.json \
  --out experiments/rag_page_index_eval/out/mini_results.csv \
  --k 5
```

- [ ] **Step 4: Commit**

```bash
git add experiments/rag_page_index_eval/run_eval.py experiments/rag_page_index_eval/README.md
git commit -m "Add QASPER retrieval eval runner"
```

## Task 8: Full Verification

**Files:**
- No new files

- [ ] **Step 1: Run sandbox tests**

```bash
pytest experiments/rag_page_index_eval/tests -v
```

- [ ] **Step 2: Run fixture eval**

```bash
python -m experiments.rag_page_index_eval.run_eval \
  --qasper-json experiments/rag_page_index_eval/fixtures/mini_qasper.json \
  --out experiments/rag_page_index_eval/out/mini_results.csv \
  --k 5
```

- [ ] **Step 3: Verify output CSV**

Expected:
- one row per query per variant
- variants: `page_bm25`, `section_bm25`, `two_stage`, `hybrid`
- nonzero recall for fixture query

- [ ] **Step 4: Commit final cleanup**

```bash
git status --short
git add experiments/rag_page_index_eval
git commit -m "Complete retrieval-only QASPER sandbox"
```

## Future Extension

After fixture pass:
- Add optional Hugging Face loader guarded by `try: import datasets`.
- Add `--limit-papers`.
- Add `--cache-dir`.
- Add direct adapter from real `lambda/index_materials` JSON output once page-index improvements land.
- Add comparison baseline against `lambda/embed_materials` embeddings in a separate plan.

