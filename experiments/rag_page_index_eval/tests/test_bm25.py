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
