import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub fitz before importing image_helper (PyMuPDF may not be installed in CI)
sys.modules.setdefault(
    "fitz",
    types.SimpleNamespace(
        Matrix=lambda x, y: object(),
        open=lambda path: None,
        Page=object,  # needed so worker.py type hints don't fail when both test files run
    ),
)

from unittest.mock import MagicMock, patch

from builders.base import IndexNode, MaterialIndex
from image_helper import (
    attach_visual_nodes,
    describe_page_visuals,
    make_visual_nodes,
    render_page_png,
)


def test_render_page_png_returns_bytes():
    fake_pixmap = MagicMock()
    fake_pixmap.tobytes.return_value = b"\x89PNG\r\n"
    fake_page = MagicMock()
    fake_page.get_pixmap.return_value = fake_pixmap

    # fitz is stubbed via sys.modules; Matrix returns a plain object passed to get_pixmap
    result = render_page_png(fake_page, dpi=150)

    assert result == b"\x89PNG\r\n"
    fake_page.get_pixmap.assert_called_once()


def test_render_page_png_returns_none_on_error():
    bad_page = MagicMock()
    bad_page.get_pixmap.side_effect = RuntimeError("fitz error")

    result = render_page_png(bad_page)

    assert result is None


def test_describe_page_visuals_returns_empty_when_no_png():
    result = describe_page_visuals(None, "sk-test")
    assert result == {"visual_summary": "", "detected_figures": [], "detected_tables": []}


def test_describe_page_visuals_returns_empty_when_no_api_key():
    result = describe_page_visuals(b"png_bytes", "")
    assert result == {"visual_summary": "", "detected_figures": [], "detected_tables": []}


def test_describe_page_visuals_parses_valid_json():
    fake_json = (
        '{"visual_summary": "3-layer network", '
        '"detected_figures": [{"label": "Figure 1", "description": "feedforward network"}], '
        '"detected_tables": []}'
    )
    with patch("image_helper.describe_visuals", return_value=fake_json):
        result = describe_page_visuals(b"png", "sk-test")

    assert result["visual_summary"] == "3-layer network"
    assert result["detected_figures"] == [{"label": "Figure 1", "description": "feedforward network"}]
    assert result["detected_tables"] == []


def test_describe_page_visuals_strips_markdown_fences():
    fenced = "```json\n{\"visual_summary\": \"diagram\", \"detected_figures\": [], \"detected_tables\": []}\n```"
    with patch("image_helper.describe_visuals", return_value=fenced):
        result = describe_page_visuals(b"png", "sk-test")
    assert result["visual_summary"] == "diagram"


def test_describe_page_visuals_returns_empty_on_parse_failure():
    with patch("image_helper.describe_visuals", return_value="not json at all"):
        result = describe_page_visuals(b"png", "sk-test")
    assert result == {"visual_summary": "", "detected_figures": [], "detected_tables": []}


def test_describe_page_visuals_returns_empty_on_api_error():
    import requests
    with patch("image_helper.describe_visuals", side_effect=requests.RequestException("timeout")):
        result = describe_page_visuals(b"png", "sk-test")
    assert result == {"visual_summary": "", "detected_figures": [], "detected_tables": []}


def test_make_visual_nodes_creates_figure_nodes():
    visuals = {
        "visual_summary": "slide with diagram",
        "detected_figures": [
            {"label": "Figure 1", "description": "feedforward network with 3 layers"},
        ],
        "detected_tables": [],
    }
    nodes = make_visual_nodes(page_number=5, visuals=visuals)

    assert len(nodes) == 1
    assert nodes[0].node_type == "figure"
    assert nodes[0].title == "Figure 1"
    assert nodes[0].summary == "feedforward network with 3 layers"
    assert nodes[0].start_page == 5
    assert nodes[0].end_page == 5


def test_make_visual_nodes_creates_table_nodes():
    visuals = {
        "visual_summary": "table of results",
        "detected_figures": [],
        "detected_tables": [{"label": "Table 2", "description": "hyperparameter grid search results"}],
    }
    nodes = make_visual_nodes(page_number=3, visuals=visuals)

    assert len(nodes) == 1
    assert nodes[0].node_type == "table"
    assert nodes[0].title == "Table 2"
    assert nodes[0].start_page == 3


def test_make_visual_nodes_mixed():
    visuals = {
        "visual_summary": "dense page",
        "detected_figures": [{"label": "Figure 1", "description": "loss curve"}],
        "detected_tables": [{"label": "Table 1", "description": "accuracy comparison"}],
    }
    nodes = make_visual_nodes(page_number=7, visuals=visuals)

    assert len(nodes) == 2
    types_found = {n.node_type for n in nodes}
    assert types_found == {"figure", "table"}


def test_make_visual_nodes_empty_returns_empty_list():
    visuals = {"visual_summary": "", "detected_figures": [], "detected_tables": []}
    assert make_visual_nodes(page_number=1, visuals=visuals) == []


def test_make_visual_nodes_stable_ids_are_deterministic():
    visuals = {
        "visual_summary": "x",
        "detected_figures": [{"label": "Figure 1", "description": "x"}],
        "detected_tables": [],
    }
    nodes1 = make_visual_nodes(2, visuals)
    nodes2 = make_visual_nodes(2, visuals)
    assert nodes1[0].node_id == nodes2[0].node_id


def test_attach_visual_nodes_attaches_to_deepest_section():
    figure_node = IndexNode(
        node_id="node_fig1_2_2_aaaa",
        title="Figure 1",
        start_page=2, end_page=2,
        node_type="figure",
        summary="Neural network diagram",
    )
    child = IndexNode(
        node_id="node_dataset", title="Dataset",
        start_page=2, end_page=3, node_type="section",
    )
    root = IndexNode(
        node_id="node_methods", title="Methods",
        start_page=1, end_page=4, node_type="section",
        nodes=[child],
    )
    mi = MaterialIndex(title="Paper", doc_type="reading", page_count=4, nodes=[root])

    attach_visual_nodes(mi, {2: [figure_node]})

    # depth-first: figure attached to child (deepest), not root
    assert figure_node in child.nodes
    assert figure_node not in root.nodes


def test_attach_visual_nodes_no_page_match_leaves_tree_unchanged():
    root = IndexNode(
        node_id="node_intro", title="Introduction",
        start_page=1, end_page=2, node_type="section",
    )
    mi = MaterialIndex(title="Paper", doc_type="reading", page_count=4, nodes=[root])

    orphan = IndexNode(node_id="x", title="Fig", start_page=9, end_page=9, node_type="figure")
    attach_visual_nodes(mi, {9: [orphan]})

    assert root.nodes == []


def test_attach_visual_nodes_empty_page_visuals_is_noop():
    root = IndexNode(
        node_id="node_intro", title="Introduction",
        start_page=1, end_page=2, node_type="section",
    )
    mi = MaterialIndex(title="Paper", doc_type="reading", page_count=2, nodes=[root])
    attach_visual_nodes(mi, {})
    assert root.nodes == []


def test_attach_visual_nodes_uses_evidence_pages_when_nonempty():
    """evidence_pages=[5] on a node spanning pages 2-8 should match only page 5."""
    fig_node = IndexNode(
        node_id="node_fig_evid_5_5_aaaa",
        title="Figure on page 5",
        start_page=5, end_page=5,
        node_type="figure",
        summary="Some figure",
    )
    section = IndexNode(
        node_id="node_results", title="Results",
        start_page=2, end_page=8, node_type="section",
        evidence_pages=[5],
    )
    mi = MaterialIndex(title="Paper", doc_type="reading", page_count=10, nodes=[section])

    attach_visual_nodes(mi, {5: [fig_node]})

    assert fig_node in section.nodes
