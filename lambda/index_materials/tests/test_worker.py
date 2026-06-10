import os
import sys
import types
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault("asyncpg", types.SimpleNamespace())
sys.modules.setdefault("fitz", types.SimpleNamespace(Page=object))
sys.modules.setdefault("pymupdf4llm", types.SimpleNamespace())

from builders.base import IndexNode, MaterialIndex
from token_counter import TokenCounter
from worker import _annotate_index_token_counts, _assign_keywords_all_nodes, _extract_pages, _resolve_section_names


def test_resolve_section_names_adds_leaf_and_path():
    child = IndexNode(
        node_id="node_child",
        title="Dataset",
        start_page=2,
        end_page=3,
        parent_path=["Methods"],
    )
    root = IndexNode(
        node_id="node_root",
        title="Methods",
        start_page=1,
        end_page=4,
        nodes=[child],
    )
    material_index = MaterialIndex(
        title="Paper",
        doc_type="reading",
        page_count=4,
        nodes=[root],
    )

    resolved = _resolve_section_names(
        [{"page_number": 2, "text_content": "data", "has_images": False}],
        material_index,
    )

    assert resolved[0]["section_name"] == "Dataset"
    assert resolved[0]["section_path"] == ["Methods", "Dataset"]


def test_resolve_section_names_ignores_evidence_leaf_for_page_label():
    caption = IndexNode(
        node_id="node_caption",
        title="Figure 1: Results",
        start_page=2,
        end_page=2,
        node_type="figure",
        parent_path=["Methods"],
    )
    root = IndexNode(
        node_id="node_root",
        title="Methods",
        start_page=1,
        end_page=4,
        nodes=[caption],
    )
    material_index = MaterialIndex(
        title="Paper",
        doc_type="reading",
        page_count=4,
        nodes=[root],
    )

    resolved = _resolve_section_names(
        [{"page_number": 2, "text_content": "Figure 1: Results", "has_images": True}],
        material_index,
    )

    assert resolved[0]["section_name"] == "Methods"
    assert resolved[0]["section_path"] == ["Methods"]


def test_assign_keywords_all_nodes_uses_extractor(monkeypatch):
    node = IndexNode(
        node_id="node_attention",
        title="Attention",
        start_page=1,
        end_page=1,
    )
    page_rows = {
        1: {"page_number": 1, "text_content": "Transformer attention datasets"}
    }

    monkeypatch.setattr(
        "worker.extract_keywords",
        lambda prompt, api_key: ["transformer", "attention", "datasets"],
    )

    asyncio.run(_assign_keywords_all_nodes([node], page_rows, "reading", "sk-test"))

    assert node.keywords == ["transformer", "attention", "datasets"]


def test_assign_keywords_all_nodes_falls_back_to_title_words(monkeypatch):
    node = IndexNode(
        node_id="node_gradient_descent",
        title="Gradient Descent",
        start_page=1,
        end_page=1,
    )
    page_rows = {
        1: {"page_number": 1, "text_content": "optimizer details"}
    }

    def fail_extract(prompt, api_key):
        raise RuntimeError("api unavailable")

    monkeypatch.setattr("worker.extract_keywords", fail_extract)

    asyncio.run(_assign_keywords_all_nodes([node], page_rows, "reading", "sk-test"))

    assert node.keywords == ["gradient", "descent"]


def test_extract_pages_sets_token_count(monkeypatch):
    class FakePage:
        def get_images(self, full=False):
            return []

    class FakeDoc:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            return FakePage()

        def close(self):
            pass

    import types as _types
    monkeypatch.setattr("worker.fitz", _types.SimpleNamespace(open=lambda path: FakeDoc()))
    monkeypatch.setattr("worker.pymupdf4llm", _types.SimpleNamespace(to_markdown=lambda doc, pages: "a" * 400))

    rows = _extract_pages("/tmp/fake.pdf")

    assert rows[0]["token_count"] == TokenCounter().estimate_text("a" * 400)


def test_annotate_index_token_counts_sets_node_span_tokens():
    node = IndexNode(node_id="node_intro", title="Intro", start_page=1, end_page=2)
    material_index = MaterialIndex(title="Lecture", doc_type="lecture_slide", page_count=2, nodes=[node])
    page_rows = {
        1: {"page_number": 1, "text_content": "a" * 400, "token_count": 100},
        2: {"page_number": 2, "text_content": "b" * 200, "token_count": 50},
    }

    _annotate_index_token_counts(material_index, page_rows)

    assert material_index.nodes[0].token_count == 150
