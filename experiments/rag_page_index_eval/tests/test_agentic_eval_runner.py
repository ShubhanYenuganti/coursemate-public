from experiments.rag_page_index_eval.agentic_eval_runner import (
    evaluate_agentic_result,
    serialize_tool_trace,
)
from experiments.rag_page_index_eval.types import QueryExample


def test_evaluate_agentic_result_scores_first_k_fetched_locations():
    query = QueryExample("q1", "paper-a", "question", {2, 4})
    result = evaluate_agentic_result(
        query,
        fetched_locations=[
            ("paper-b", 2),
            ("paper-a", 2),
            ("paper-a", 3),
            ("paper-a", 4),
        ],
        k=3,
    )

    assert result.recall_at_k == 0.5
    assert result.mrr_at_k == 0.5
    assert result.evidence_location_hit_at_k == 1.0


def test_evaluate_agentic_result_ignores_locations_after_k():
    query = QueryExample("q1", "paper-a", "question", {4})
    result = evaluate_agentic_result(
        query,
        fetched_locations=[
            ("paper-a", 1),
            ("paper-a", 2),
            ("paper-a", 3),
            ("paper-a", 4),
        ],
        k=3,
    )

    assert result.recall_at_k == 0.0
    assert result.evidence_location_hit_at_k == 0.0


def test_serialize_tool_trace_keeps_json_for_eval_debugging():
    trace = [{"tool": "get_page_content", "args": {"material_id": 1, "pages": "2,3"}}]

    assert serialize_tool_trace(trace) == '[{"tool":"get_page_content","args":{"material_id":1,"pages":"2,3"}}]'
