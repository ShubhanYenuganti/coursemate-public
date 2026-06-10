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
