import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.base import IndexNode, MaterialIndex, stable_node_id
import dataclasses


def test_stable_node_id_is_deterministic():
    a = stable_node_id("Methods", 2, 5, ["Paper", "Methods"])
    b = stable_node_id("Methods", 2, 5, ["Paper", "Methods"])
    assert a == b
    assert a.startswith("node_")


def test_index_node_serializes_retrieval_metadata():
    node = IndexNode(
        node_id="node_methods",
        title="Methods",
        start_page=2,
        end_page=5,
        node_type="section",
        parent_path=["Paper"],
        keywords=["dataset", "annotation"],
        source="regex",
        confidence=0.82,
        evidence_pages=[2, 3],
        char_start=10,
        char_end=200,
    )

    d = node.to_dict()

    assert d["node_type"] == "section"
    assert d["parent_path"] == ["Paper"]
    assert d["keywords"] == ["dataset", "annotation"]
    assert d["source"] == "regex"
    assert d["confidence"] == 0.82
    assert d["evidence_pages"] == [2, 3]
    assert d["char_start"] == 10
    assert d["char_end"] == 200


def test_index_node_defaults():
    node = IndexNode(node_id="0000", title="Intro", start_page=1, end_page=3)
    assert node.summary == ""
    assert node.nodes == []


def test_material_index_to_dict():
    child = IndexNode(node_id="0001", title="Sub", start_page=2, end_page=2)
    root = IndexNode(node_id="0000", title="Intro", start_page=1, end_page=3, nodes=[child])
    mi = MaterialIndex(title="Lecture 1", doc_type="lecture_slide", page_count=10, nodes=[root])
    d = mi.to_dict()
    assert d["title"] == "Lecture 1"
    assert d["doc_type"] == "lecture_slide"
    assert d["page_count"] == 10
    assert len(d["nodes"]) == 1
    assert d["nodes"][0]["nodes"][0]["title"] == "Sub"
