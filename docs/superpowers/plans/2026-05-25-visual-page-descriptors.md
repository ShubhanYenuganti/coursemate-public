# Visual Page Descriptors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For every PDF page where `has_images=True`, render the page, call `gpt-4o-mini` vision, and store the result as structured figure/table child nodes in the `IndexNode` tree and as raw rows in a new `material_page_visuals` table.

**Architecture:** A new `image_helper.py` module handles rendering, LLM description, node creation, and tree attachment. `llm_client.py` gains one multimodal function. `worker.py` calls the helper in its existing page loop and passes raw visual data through to `_sync_store`. `pageindex_retrieval.py`'s `get_page_content` gains a LEFT JOIN to surface visual data at query time.

**Tech Stack:** PyMuPDF (`fitz`) for rendering, OpenAI `gpt-4o-mini` vision via existing `llm_client.py` REST pattern, `psycopg` for DB writes, `pytest` + `unittest.mock` for tests.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `lambda/index_materials/llm_client.py` | Modify | Add `describe_visuals(png_b64, api_key) -> str` |
| `lambda/index_materials/image_helper.py` | Create | Render page, call LLM, make/attach `IndexNode` children |
| `lambda/index_materials/db.py` | Modify | Add `store_page_visuals(conn, material_id, page_number, visuals)` |
| `lambda/index_materials/worker.py` | Modify | Add `_build_page_visuals()`, update `index_document` and `_sync_store` |
| `api/pageindex_retrieval.py` | Modify | LEFT JOIN `material_page_visuals` in `get_page_content()` |
| `lambda/index_materials/tests/test_image_helper.py` | Create | Unit tests for all `image_helper` functions |
| `lambda/index_materials/tests/test_llm_client.py` | Modify | Add `test_describe_visuals_sends_multimodal_message` |
| `lambda/index_materials/tests/test_db.py` | Modify | Add `test_store_page_visuals_upserts_row` |
| `lambda/index_materials/tests/test_worker.py` | Modify | Add `test_build_page_visuals_calls_helper` |

**DB migration — run directly against the database (not a script):**
```sql
CREATE TABLE material_page_visuals (
    material_id      INT  NOT NULL REFERENCES materials(id),
    page_number      INT  NOT NULL,
    visual_summary   TEXT,
    detected_figures JSONB DEFAULT '[]',
    detected_tables  JSONB DEFAULT '[]',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (material_id, page_number)
);
```

---

## Task 1: `llm_client.py` — add `describe_visuals()`

**Files:**
- Modify: `lambda/index_materials/llm_client.py`
- Modify: `lambda/index_materials/tests/test_llm_client.py`

- [x] **Step 1: Write the failing test**

Add to the import line at the top of `lambda/index_materials/tests/test_llm_client.py`:
```python
from llm_client import (
    build_doc_summary_prompt,
    build_node_keywords_prompt,
    build_node_summary_prompt,
    describe_visuals,
    extract_tags,
    summarize,
)
```

Add this test at the bottom of `test_llm_client.py`:
```python
def test_describe_visuals_sends_multimodal_message():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"visual_summary": "A diagram", "detected_figures": [], "detected_tables": []}'}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("llm_client.requests.post", return_value=mock_resp) as mock_post:
        result = describe_visuals("abc123base64encoded", "sk-test")

    assert "visual_summary" in result
    call_json = mock_post.call_args[1]["json"]
    assert call_json["model"] == "gpt-4o-mini"
    content = call_json["messages"][0]["content"]
    assert any(c.get("type") == "image_url" for c in content)
    assert any(c.get("type") == "text" for c in content)
    image_part = next(c for c in content if c.get("type") == "image_url")
    assert "abc123base64encoded" in image_part["image_url"]["url"]
```

- [x] **Step 2: Run to verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_llm_client.py::test_describe_visuals_sends_multimodal_message -v
```

Expected: `ImportError: cannot import name 'describe_visuals'`

- [ ] **Step 3: Implement `describe_visuals` in `llm_client.py`**

Add after the `extract_keywords` function (before `get_api_key`):
```python
def describe_visuals(png_b64: str, api_key: str) -> str:
    """Send a page image to gpt-4o-mini and return the raw JSON string response."""
    prompt_text = (
        "Analyze this course material page. "
        "Return ONLY a JSON object with these exact fields:\n"
        "{\n"
        '  "visual_summary": "<description of all visual content in at most 120 tokens>",\n'
        '  "detected_figures": [{"label": "<Figure N or short label>", "description": "<what it shows>"}],\n'
        '  "detected_tables": [{"label": "<Table N or short label>", "description": "<what it contains>"}]\n'
        "}\n"
        "Use empty arrays when there are no figures or tables. Output JSON only — no other text."
    )
    resp = requests.post(
        _URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_b64}"}},
                    ],
                }
            ],
            "max_tokens": 400,
            "temperature": 0.0,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_llm_client.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shubhan/OneShotCourseMate
git add lambda/index_materials/llm_client.py lambda/index_materials/tests/test_llm_client.py
git commit -m "feat(llm_client): add describe_visuals() multimodal function"
```

---

## Task 2: `image_helper.py` — scaffold + `render_page_png()` + `describe_page_visuals()`

**Files:**
- Create: `lambda/index_materials/image_helper.py`
- Create: `lambda/index_materials/tests/test_image_helper.py`

- [ ] **Step 1: Write the failing tests**

Create `lambda/index_materials/tests/test_image_helper.py`:
```python
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
    ),
)

from unittest.mock import MagicMock, patch

from image_helper import describe_page_visuals, render_page_png


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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_image_helper.py -v
```

Expected: `ModuleNotFoundError: No module named 'image_helper'`

- [ ] **Step 3: Implement `image_helper.py` (render + describe only)**

Create `lambda/index_materials/image_helper.py`:
```python
import base64
import json
import logging
import re

from builders.base import IndexNode, stable_node_id
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
```

- [ ] **Step 4: Run to verify tests pass**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_image_helper.py -v
```

Expected: all 7 tests PASS

---

## Task 3: `image_helper.py` — `make_visual_nodes()` + `attach_visual_nodes()`

**Files:**
- Modify: `lambda/index_materials/image_helper.py`
- Modify: `lambda/index_materials/tests/test_image_helper.py`

- [ ] **Step 1: Write the failing tests**

Add to the import line at the top of `test_image_helper.py`:
```python
from image_helper import (
    attach_visual_nodes,
    describe_page_visuals,
    make_visual_nodes,
    render_page_png,
)
```

Add these tests at the bottom of `test_image_helper.py`:
```python
from builders.base import IndexNode, MaterialIndex


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
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_image_helper.py -v
```

Expected: `ImportError: cannot import name 'attach_visual_nodes'`

- [ ] **Step 3: Implement `make_visual_nodes()` and `attach_visual_nodes()` in `image_helper.py`**

Add after `describe_page_visuals`:
```python
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


def attach_visual_nodes(material_index, page_visuals: dict) -> None:
    """Attach visual child nodes to the deepest matching section in the tree.
    Each page's nodes are attached exactly once (depth-first, leaf wins)."""
    if not page_visuals:
        return

    remaining: dict[int, list[IndexNode]] = dict(page_visuals)

    def _walk(nodes: list) -> None:
        for node in nodes:
            _walk(node.nodes)  # recurse into children first (depth-first)
            effective = set(node.evidence_pages) if node.evidence_pages else set(range(node.start_page, node.end_page + 1))
            to_attach: list[IndexNode] = []
            for pg in sorted(effective):
                if pg in remaining:
                    to_attach.extend(remaining.pop(pg))
            if to_attach:
                node.nodes.extend(to_attach)

    _walk(material_index.nodes)
```

- [ ] **Step 4: Run to verify all tests pass**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_image_helper.py -v
```

Expected: all 15 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shubhan/OneShotCourseMate
git add lambda/index_materials/image_helper.py lambda/index_materials/tests/test_image_helper.py
git commit -m "feat(image_helper): render, describe, make nodes, attach to tree"
```

---

## Task 4: `db.py` — `store_page_visuals()`

**Files:**
- Modify: `lambda/index_materials/db.py`
- Modify: `lambda/index_materials/tests/test_db.py`

- [x] **Step 1: Write the failing test**

Add to the imports in `test_db.py`:
```python
from db import store_page_texts, store_page_visuals
```

Add at the bottom of `test_db.py`:
```python
def test_store_page_visuals_upserts_correct_columns():
    conn = FakeConn()
    visuals = {
        "visual_summary": "A slide with a neural network diagram",
        "detected_figures": [{"label": "Figure 1", "description": "3-layer network"}],
        "detected_tables": [],
    }
    store_page_visuals(conn, material_id=7, page_number=3, visuals=visuals)

    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "material_page_visuals" in sql
    assert "ON CONFLICT" in sql
    assert params[0] == 7        # material_id
    assert params[1] == 3        # page_number
    assert "neural network" in params[2]   # visual_summary
    assert "Figure 1" in params[3]         # detected_figures JSON
    assert params[4] == "[]"               # detected_tables JSON


def test_store_page_visuals_handles_empty_visuals():
    conn = FakeConn()
    store_page_visuals(conn, material_id=1, page_number=1, visuals={
        "visual_summary": "",
        "detected_figures": [],
        "detected_tables": [],
    })
    sql, params = conn.calls[0]
    assert params[2] == ""
    assert params[3] == "[]"
    assert params[4] == "[]"
```

- [x] **Step 2: Run to verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_db.py -v
```

Expected: `ImportError: cannot import name 'store_page_visuals'`

- [x] **Step 3: Implement `store_page_visuals` in `db.py`**

Add after `store_page_texts` in `lambda/index_materials/db.py`:
```python
def store_page_visuals(conn, material_id: int, page_number: int, visuals: dict) -> None:
    """Upsert one row into material_page_visuals."""
    conn.execute(
        """INSERT INTO material_page_visuals
               (material_id, page_number, visual_summary, detected_figures, detected_tables)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (material_id, page_number) DO UPDATE
           SET visual_summary    = EXCLUDED.visual_summary,
               detected_figures  = EXCLUDED.detected_figures,
               detected_tables   = EXCLUDED.detected_tables""",
        (
            material_id,
            page_number,
            visuals.get("visual_summary") or "",
            json.dumps(visuals.get("detected_figures") or []),
            json.dumps(visuals.get("detected_tables") or []),
        ),
    )
```

- [x] **Step 4: Run to verify tests pass**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_db.py -v
```

Expected: all tests PASS

- [x] **Step 5: Commit**

```bash
cd /Users/shubhan/OneShotCourseMate
git add lambda/index_materials/db.py lambda/index_materials/tests/test_db.py
git commit -m "feat(db): add store_page_visuals() upsert"
```

---

## Task 5: `worker.py` — integrate visual extraction

**Files:**
- Modify: `lambda/index_materials/worker.py`
- Modify: `lambda/index_materials/tests/test_worker.py`

- [ ] **Step 1: Write the failing test**

Add to `test_worker.py` at the bottom (before the last test or at the end):
```python
def test_build_page_visuals_calls_helper_for_image_pages(monkeypatch):
    import types as _types

    fake_page = MagicMock()
    fake_doc = MagicMock()
    fake_doc.__getitem__ = lambda self, i: fake_page

    monkeypatch.setattr("worker.fitz.open", lambda path: fake_doc)

    fake_visuals = {
        "visual_summary": "a diagram",
        "detected_figures": [{"label": "Figure 1", "description": "network"}],
        "detected_tables": [],
    }
    monkeypatch.setattr("worker.image_helper.render_page_png", lambda page: b"png")
    monkeypatch.setattr("worker.image_helper.describe_page_visuals", lambda png, key: fake_visuals)

    from worker import _build_page_visuals
    result = _build_page_visuals("/tmp/test.pdf", image_pages=[2, 5], api_key="sk-test")

    assert 2 in result
    assert 5 in result
    assert result[2] == fake_visuals
    assert result[5] == fake_visuals
    fake_doc.close.assert_called_once()
```

Also add `from unittest.mock import MagicMock` to the imports at the top of `test_worker.py` if not already present.

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_worker.py::test_build_page_visuals_calls_helper_for_image_pages -v
```

Expected: `ImportError: cannot import name '_build_page_visuals'`

- [ ] **Step 3: Add `import image_helper` to `worker.py` imports**

At the top of `lambda/index_materials/worker.py`, add after the existing local imports:
```python
import image_helper
```

Also add `store_page_visuals` to the `db` imports block:
```python
from db import (
    store_course_index,
    store_metadata_tags,
    store_page_index,
    store_page_texts,
    store_page_visuals,
)
```

- [ ] **Step 4: Add `_build_page_visuals()` to `worker.py`**

Add this function after `_extract_pages`:
```python
def _build_page_visuals(pdf_path: str, image_pages: list[int], api_key: str) -> dict[int, dict]:
    """For each page in image_pages, render and describe visuals.
    Returns {page_number: visuals_dict}. Never raises — failures produce empty dicts."""
    if not image_pages or not api_key:
        return {}
    doc = fitz.open(pdf_path)
    result: dict[int, dict] = {}
    try:
        for pg in image_pages:
            page = doc[pg - 1]  # fitz uses 0-based index
            png_bytes = image_helper.render_page_png(page)
            visuals = image_helper.describe_page_visuals(png_bytes, api_key)
            result[pg] = visuals
    finally:
        doc.close()
    return result
```

- [ ] **Step 5: Run to verify the new test passes**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/test_worker.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Update `index_document` to call visual extraction and attach nodes**

In `lambda/index_materials/worker.py`, find the `index_document` function. After `api_key = get_api_key()` and before `await _summarize_all_nodes(...)`, insert:
```python
        # Visual extraction for image pages
        image_pages = [row["page_number"] for row in page_rows_list if row.get("has_images")]
        page_visuals_raw: dict[int, dict] = await asyncio.to_thread(
            _build_page_visuals, pdf_path, image_pages, api_key
        )
        visual_nodes_by_page: dict[int, list] = {}
        for pg, visuals in page_visuals_raw.items():
            nodes = image_helper.make_visual_nodes(pg, visuals)
            if nodes:
                visual_nodes_by_page[pg] = nodes
        image_helper.attach_visual_nodes(material_index, visual_nodes_by_page)
```

The full block in `index_document` should now look like:
```python
        api_key = get_api_key()

        # Visual extraction for image pages
        image_pages = [row["page_number"] for row in page_rows_list if row.get("has_images")]
        page_visuals_raw: dict[int, dict] = await asyncio.to_thread(
            _build_page_visuals, pdf_path, image_pages, api_key
        )
        visual_nodes_by_page: dict[int, list] = {}
        for pg, visuals in page_visuals_raw.items():
            nodes = image_helper.make_visual_nodes(pg, visuals)
            if nodes:
                visual_nodes_by_page[pg] = nodes
        image_helper.attach_visual_nodes(material_index, visual_nodes_by_page)

        await _summarize_all_nodes(material_index.nodes, page_rows, doc_type, api_key)
        await _assign_keywords_all_nodes(material_index.nodes, page_rows, doc_type, api_key)
```

- [ ] **Step 7: Pass `page_visuals_raw` through `_sync_store`**

Update the `_sync_store` function signature (add `page_visuals_raw` as the last param with default `None`):
```python
def _sync_store(
    _async_conn,
    material_id,
    course_id,
    material_title,
    doc_type,
    material_index,
    page_rows_list,
    doc_summary,
    metadata_tags,
    page_visuals_raw=None,
) -> None:
    import psycopg

    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as sync_conn:
        store_page_texts(sync_conn, material_id, page_rows_list)
        store_page_index(sync_conn, material_id, material_index.to_dict())
        if page_visuals_raw:
            for page_number, visuals in page_visuals_raw.items():
                store_page_visuals(sync_conn, material_id, page_number, visuals)
        if course_id:
            store_course_index(
                sync_conn,
                material_id,
                course_id,
                material_title,
                doc_type,
                material_index.page_count,
                doc_summary,
            )
            if metadata_tags:
                store_metadata_tags(sync_conn, course_id, material_id, metadata_tags)
        sync_conn.commit()
```

Update the call site in `index_document` to pass `page_visuals_raw`:
```python
        async with pool.acquire() as conn:
            await asyncio.to_thread(
                _sync_store,
                conn,
                material_id,
                course_id,
                material_title,
                doc_type,
                material_index,
                page_rows_list,
                doc_summary,
                metadata_tags,
                page_visuals_raw,
            )
```

- [ ] **Step 8: Run full test suite**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
cd /Users/shubhan/OneShotCourseMate
git add lambda/index_materials/worker.py lambda/index_materials/tests/test_worker.py
git commit -m "feat(worker): integrate visual page extraction and node attachment"
```

---

## Task 6: `pageindex_retrieval.py` — LEFT JOIN `material_page_visuals`

**Files:**
- Modify: `api/pageindex_retrieval.py`
- Modify: `lambda/index_materials/tests/test_pageindex_retrieval.py` (or wherever retrieval tests live)

- [ ] **Step 1: Locate the retrieval test file**

```bash
find /Users/shubhan/OneShotCourseMate -name "test_pageindex_retrieval.py" | head -5
```

Use the file that was found. If it lives under `lambda/index_materials/tests/`, use that path in the steps below.

- [ ] **Step 2: Write the failing test**

Add this test to `test_pageindex_retrieval.py`:
```python
def test_get_page_content_includes_visual_fields():
    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows
        def execute(self, sql, params):
            self._sql = sql
            self._params = params
        def fetchall(self):
            return self._rows
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor([
                {
                    "page_number": 3,
                    "text_content": "transformer attention",
                    "has_images": True,
                    "visual_summary": "Attention heatmap diagram",
                    "detected_figures": [{"label": "Figure 1", "description": "heatmap"}],
                    "detected_tables": None,
                }
            ])

    from pageindex_retrieval import get_page_content
    result = get_page_content(FakeConn(), material_id=1, pages="3")

    assert len(result) == 1
    assert result[0]["visual_summary"] == "Attention heatmap diagram"
    assert "LEFT JOIN material_page_visuals" in FakeConn().cursor()._sql if hasattr(FakeConn().cursor(), "_sql") else True
```

Note: since the FakeCursor doesn't retain `_sql` on FakeConn's cursor, the important assertion is that the fields are present in the returned dict. To also verify the SQL contains the JOIN, check directly:

```python
def test_get_page_content_sql_has_visual_join():
    sqls = []

    class CaptureCursor:
        def execute(self, sql, params):
            sqls.append(sql)
        def fetchall(self):
            return []
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return CaptureCursor()

    from pageindex_retrieval import get_page_content
    get_page_content(FakeConn(), material_id=1, pages="1")

    assert sqls, "execute was not called"
    assert "material_page_visuals" in sqls[0]
    assert "LEFT JOIN" in sqls[0]
```

- [ ] **Step 3: Run to verify the test fails**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest lambda/index_materials/tests/test_pageindex_retrieval.py::test_get_page_content_sql_has_visual_join -v
```

Expected: `AssertionError: assert "material_page_visuals" in ...`

- [ ] **Step 4: Update `get_page_content` in `api/pageindex_retrieval.py`**

Replace the existing `get_page_content` function body:
```python
def get_page_content(conn, material_id: int, pages: str) -> list[dict]:
    page_numbers = _parse_pages(pages)
    if not page_numbers:
        return []
    cursor = conn.cursor()
    cursor.execute(
        """SELECT mpt.page_number, mpt.text_content, mpt.has_images,
                  mpv.visual_summary, mpv.detected_figures, mpv.detected_tables
           FROM material_page_text mpt
           LEFT JOIN material_page_visuals mpv
                  ON mpv.material_id = mpt.material_id
                 AND mpv.page_number = mpt.page_number
           WHERE mpt.material_id = %s AND mpt.page_number = ANY(%s)
           ORDER BY mpt.page_number""",
        (material_id, page_numbers),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest lambda/index_materials/tests/test_pageindex_retrieval.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Run the full test suite to confirm nothing broke**

```bash
cd /Users/shubhan/OneShotCourseMate/lambda/index_materials && python -m pytest tests/ -q
```

Expected: all tests PASS, no failures

- [ ] **Step 7: Commit**

```bash
cd /Users/shubhan/OneShotCourseMate
git add api/pageindex_retrieval.py
git commit -m "feat(retrieval): LEFT JOIN material_page_visuals in get_page_content"
```

---

## Post-implementation checklist

- [ ] Run the DB migration against your database:
  ```sql
  CREATE TABLE material_page_visuals (
      material_id      INT  NOT NULL REFERENCES materials(id),
      page_number      INT  NOT NULL,
      visual_summary   TEXT,
      detected_figures JSONB DEFAULT '[]',
      detected_tables  JSONB DEFAULT '[]',
      created_at       TIMESTAMPTZ DEFAULT NOW(),
      PRIMARY KEY (material_id, page_number)
  );
  ```
- [ ] Confirm `OPENAI_API_KEY_INDEXER` is set in the Lambda environment (it was already used for text summarization — no new key needed)
- [ ] Re-index one slide deck and verify: `material_page_visuals` has rows for image pages; `material_page_index.index_json` tree contains `"node_type": "figure"` and `"node_type": "table"` child nodes
