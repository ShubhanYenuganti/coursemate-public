import base64
import json
import logging
import re

from builders.base import IndexNode, MaterialIndex, stable_node_id
from llm_client import describe_visuals

logger = logging.getLogger(__name__)

_EMPTY_VISUALS: dict = {"visual_summary": "", "detected_figures": [], "detected_tables": []}

# Lazy fitz reference — set by render_page_png on first use
_fitz = None


def _get_fitz():
    global _fitz
    if _fitz is None:
        import fitz as _fitz_mod
        _fitz = _fitz_mod
    return _fitz


def render_page_png(fitz_page, dpi: int = 150) -> bytes | None:
    """Render a fitz Page to PNG bytes. Returns None on any failure."""
    try:
        fitz = _get_fitz()
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        return fitz_page.get_pixmap(matrix=mat).tobytes("png")
    except Exception as exc:
        logger.warning("render_page_png failed: %s", exc)
        return None


def describe_page_visuals(png_bytes: bytes | None, api_key: str) -> dict:
    """Call vision LLM on a PNG page image. Returns parsed visuals dict.
    Always returns a valid dict — never raises."""
    if not png_bytes or not api_key:
        return dict(_EMPTY_VISUALS)
    try:
        png_b64 = base64.b64encode(png_bytes).decode("utf-8")
        raw = describe_visuals(png_b64, api_key)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        return {
            "visual_summary": str(parsed.get("visual_summary") or ""),
            "detected_figures": [
                {"label": str(f.get("label", "")), "description": str(f.get("description", ""))}
                for f in (parsed.get("detected_figures") or [])
            ],
            "detected_tables": [
                {"label": str(t.get("label", "")), "description": str(t.get("description", ""))}
                for t in (parsed.get("detected_tables") or [])
            ],
        }
    except Exception as exc:
        logger.warning("describe_page_visuals failed: %s", exc)
        return dict(_EMPTY_VISUALS)


_KEYWORD_STOPWORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "with", "is", "that", "this", "are", "from"}


def _keywords_from_text(text: str) -> list[str]:
    """Extract simple word-level keywords from a short description."""
    words = re.sub(r"[^a-zA-Z0-9 ]+", " ", text.lower()).split()
    seen: dict[str, None] = {}
    for w in words:
        if len(w) > 3 and w not in _KEYWORD_STOPWORDS:
            seen[w] = None
    return list(seen)[:10]


def make_visual_nodes(page_number: int, visuals: dict) -> list[IndexNode]:
    """Create one IndexNode per detected figure and per detected table."""
    nodes: list[IndexNode] = []

    for fig in visuals.get("detected_figures") or []:
        label = fig.get("label") or f"Figure on page {page_number}"
        desc = fig.get("description") or ""
        nodes.append(IndexNode(
            node_id=stable_node_id(label, page_number, page_number),
            title=label,
            start_page=page_number,
            end_page=page_number,
            summary=desc,
            node_type="figure",
            keywords=_keywords_from_text(desc),
            source="vision",
        ))

    for tbl in visuals.get("detected_tables") or []:
        label = tbl.get("label") or f"Table on page {page_number}"
        desc = tbl.get("description") or ""
        nodes.append(IndexNode(
            node_id=stable_node_id(label, page_number, page_number),
            title=label,
            start_page=page_number,
            end_page=page_number,
            summary=desc,
            node_type="table",
            keywords=_keywords_from_text(desc),
            source="vision",
        ))

    return nodes


def attach_visual_nodes(material_index: "MaterialIndex", page_visuals: dict[int, list[IndexNode]]) -> None:
    """Attach visual child nodes to the deepest matching section in the tree.
    Each page's nodes are attached exactly once (depth-first, leaf wins)."""
    if not page_visuals:
        return

    remaining: dict[int, list] = dict(page_visuals)

    def _walk(nodes: list) -> None:
        for node in nodes:
            _walk(node.nodes)  # recurse into children first (depth-first)
            effective = set(node.evidence_pages) if node.evidence_pages else set(range(node.start_page, node.end_page + 1))
            to_attach: list = []
            for pg in sorted(effective):
                if pg in remaining:
                    to_attach.extend(remaining.pop(pg))
            if to_attach:
                node.nodes.extend(to_attach)

    _walk(material_index.nodes)
