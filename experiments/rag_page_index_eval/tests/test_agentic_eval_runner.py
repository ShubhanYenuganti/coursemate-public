from experiments.rag_page_index_eval.agentic_eval_runner import (
    evaluate_agentic_result,
    run_agentic_eval,
    serialize_tool_trace,
)
from experiments.rag_page_index_eval.types import PageRecord, QueryExample


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


def test_run_agentic_eval_accepts_huggingface_source(monkeypatch, tmp_path):
    from experiments.rag_page_index_eval import agentic_eval_runner

    def fake_loader(dataset_name, split):
        assert dataset_name == "allenai/qasper"
        assert split == "test"
        return (
            [PageRecord("paper-a", 1, "evidence", "Intro", ("Intro",))],
            [QueryExample("q1", "paper-a", "question?", {1}, metadata={"title": "Paper A"})],
        )

    class FakeAdapter:
        paper_to_material_id = {"paper-a": 1}
        material_id_to_paper = {1: "paper-a"}

        def __init__(self, pages, queries):
            pass

        def patch_production_pageindex(self):
            from contextlib import nullcontext

            return nullcontext()

    def fake_run_agent_pageindex(**kwargs):
        return (
            "answer",
            [],
            [{"tool": "get_page_content", "args": {"material_id": 1, "pages": "1"}}],
            {},
            None,
            [],
            None,
        )

    monkeypatch.setattr(agentic_eval_runner, "load_qasper_huggingface", fake_loader)
    monkeypatch.setattr(agentic_eval_runner, "QasperPageIndexAdapter", FakeAdapter)
    import llm

    monkeypatch.setattr(llm, "run_agent_pageindex", fake_run_agent_pageindex)

    rows = run_agentic_eval(
        qasper_json=None,
        dataset_source="huggingface",
        hf_dataset="allenai/qasper",
        split="test",
        out=tmp_path / "results.csv",
        openai_key="sk-test",
        model="gpt-4o-mini",
        limit=1,
        progress_every=0,
    )

    assert rows[0]["recall_at_k"] == 1.0
