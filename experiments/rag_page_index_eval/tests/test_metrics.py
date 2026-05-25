from experiments.rag_page_index_eval.metrics import evaluate_hits
from experiments.rag_page_index_eval.types import QueryExample, RetrievalHit


def hit(unit_id, pages, score=1.0, paper_id="p1"):
    return RetrievalHit(
        paper_id=paper_id,
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
    assert result.evidence_location_hit_at_k == 1.0
    assert 0.0 <= result.ndcg_at_k <= 1.0


def test_evaluate_hits_handles_no_gold_pages():
    query = QueryExample("q2", "p1", "unanswerable?", set())
    result = evaluate_hits(query, [hit("p1", [1])], variant="page_bm25", k=2)

    assert result.answerability_coverage == 0.0


def test_evaluate_hits_uses_fractional_page_recall():
    query = QueryExample("q3", "p1", "multi page?", {2, 4})
    result = evaluate_hits(query, [hit("p2", [2])], variant="page_bm25", k=1)

    assert result.recall_at_k == 0.5
    assert result.evidence_location_hit_at_k == 1.0


def test_evaluate_hits_ndcg_is_capped_for_multiple_relevant_hits():
    query = QueryExample("q4", "p1", "multi page?", {2, 4})
    result = evaluate_hits(
        query,
        [hit("p2", [2]), hit("p4", [4])],
        variant="page_bm25",
        k=2,
    )

    assert result.ndcg_at_k == 1.0


def test_wrong_paper_hits_count_against_rank():
    query = QueryExample("q5", "p1", "attention?", {2})
    result = evaluate_hits(
        query,
        [hit("wrong", [2], paper_id="p2"), hit("right", [2], paper_id="p1")],
        variant="page_bm25",
        k=2,
    )

    assert result.mrr_at_k == 0.5
