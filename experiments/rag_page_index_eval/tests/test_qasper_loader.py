from pathlib import Path

from experiments.rag_page_index_eval.qasper_loader import load_qasper_json


def test_load_qasper_json_creates_pages_and_queries():
    fixture = Path("experiments/rag_page_index_eval/fixtures/mini_qasper.json")

    pages, queries = load_qasper_json(fixture)

    assert len(pages) == 3
    assert len(queries) == 1
    assert queries[0].gold_pages == {2}
