import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.base import IndexNode, MaterialIndex
import dataclasses


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
