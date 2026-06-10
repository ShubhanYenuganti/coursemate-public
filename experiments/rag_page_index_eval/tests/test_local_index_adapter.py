from experiments.rag_page_index_eval.local_index_adapter import build_index_records
from experiments.rag_page_index_eval.types import PageRecord


def test_build_index_records_creates_section_nodes():
    pages = [
        PageRecord("p1", 1, "Intro text", "Intro", ("Intro",)),
        PageRecord("p1", 2, "Attention text", "Methods", ("Methods",)),
    ]

    nodes = build_index_records("p1", pages)

    assert [node.title for node in nodes] == ["Intro", "Methods"]
    assert nodes[1].start_page == 2
