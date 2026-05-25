from __future__ import annotations

from .bm25 import BM25Index
from .types import IndexNodeRecord, PageRecord, RetrievalHit


class PageBM25Retriever:
    variant = "page_bm25"

    def __init__(self, pages: list[PageRecord]):
        self.pages = {f"{page.paper_id}:page:{page.page_number}": page for page in pages}
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
        self.nodes = {f"{node.paper_id}:node:{node.node_id}": node for node in nodes}
        self.index = BM25Index()
        for unit_id, node in self.nodes.items():
            text = " ".join([node.title, node.summary, " ".join(node.parent_path), " ".join(node.keywords)])
            self.index.add(unit_id, text)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        hits = []
        for unit_id, score in self.index.search(query, top_k):
            node = self.nodes[unit_id]
            hits.append(
                RetrievalHit(
                    node.paper_id,
                    node.node_id,
                    "section",
                    score,
                    node.pages(),
                    " ".join([node.title, node.summary]),
                )
            )
        return hits


class TwoStageRetriever:
    variant = "two_stage"

    def __init__(self, pages: list[PageRecord], nodes: list[IndexNodeRecord]):
        self.pages = pages
        self.section = SectionBM25Retriever(nodes)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        node_hits = self.section.retrieve(query, top_k=5)
        candidate_pages = [
            page
            for page in self.pages
            if any(page.paper_id == hit.paper_id and page.page_number in hit.pages for hit in node_hits)
        ]
        if not candidate_pages:
            return []
        return PageBM25Retriever(candidate_pages).retrieve(query, top_k=top_k)


class HybridRetriever:
    variant = "hybrid"

    def __init__(self, pages: list[PageRecord], nodes: list[IndexNodeRecord]):
        self.page = PageBM25Retriever(pages)
        self.section = SectionBM25Retriever(nodes)

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalHit]:
        scores: dict[tuple[str, tuple[int, ...]], RetrievalHit] = {}
        weighted_hits = (
            (0.65, self.page.retrieve(query, top_k * 2)),
            (0.35, self.section.retrieve(query, top_k * 2)),
        )
        for weight, hits in weighted_hits:
            for hit in hits:
                key = (hit.paper_id, tuple(sorted(hit.pages)))
                prev = scores.get(key)
                score = hit.score * weight + (prev.score if prev else 0.0)
                scores[key] = RetrievalHit(
                    hit.paper_id,
                    hit.unit_id,
                    hit.unit_type,
                    score,
                    hit.pages,
                    hit.text,
                    hit.metadata,
                )
        return sorted(scores.values(), key=lambda hit: hit.score, reverse=True)[:top_k]
