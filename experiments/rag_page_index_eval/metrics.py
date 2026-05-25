import math

from .types import MetricResult, QueryExample, RetrievalHit


def _relevant(hit: RetrievalHit, query: QueryExample) -> bool:
    return hit.paper_id == query.paper_id and bool(hit.pages & query.gold_pages)


def evaluate_hits(query: QueryExample, hits: list[RetrievalHit], variant: str, k: int) -> MetricResult:
    top = hits[:k]
    if not query.gold_pages:
        return MetricResult(query.query_id, variant, 0.0, 0.0, 0.0, 0.0, 0.0)

    found_pages = set()
    for hit in top:
        if hit.paper_id == query.paper_id:
            found_pages.update(hit.pages & query.gold_pages)
    recall = len(found_pages) / len(query.gold_pages)

    relevant = [_relevant(hit, query) for hit in top]
    evidence_location_hit = 1.0 if any(relevant) else 0.0

    mrr = 0.0
    for idx, is_rel in enumerate(relevant, start=1):
        if is_rel:
            mrr = 1.0 / idx
            break

    dcg = 0.0
    for idx, is_rel in enumerate(relevant, start=1):
        if is_rel:
            dcg += 1.0 / math.log2(idx + 1)

    ideal_hits = min(len(query.gold_pages), len(top))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 0.0

    return MetricResult(
        query_id=query.query_id,
        variant=variant,
        recall_at_k=recall,
        mrr_at_k=mrr,
        ndcg_at_k=ndcg,
        evidence_location_hit_at_k=evidence_location_hit,
        answerability_coverage=1.0,
    )
