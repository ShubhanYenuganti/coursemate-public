# Page Indexing Improvements Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Improve `lambda/index_materials` as a hierarchical page-indexing system for academic and course PDFs. The index should be stable across reruns, useful for retrieval routing, and precise enough to point to page/block evidence without replacing the original page text.

## Current Shape

`lambda/index_materials/worker.py`:
- extracts page markdown with `pymupdf4llm`
- builds a `MaterialIndex` tree through `builders.route_builder(doc_type)`
- stamps pages with nearest section name
- summarizes index nodes
- stores page text, page index, course index, metadata tags, and cross-material relations

Main limitations:
- index node IDs are not guaranteed stable if generated randomly
- nodes only carry page ranges, not precise evidence spans
- page rows only know one `section_name`, not full breadcrumb context
- figures, tables, equations, and references are not first-class retrieval targets
- broad parent summaries can overrepresent child content

## File Structure

- Modify: `lambda/index_materials/builders/base.py`
  - Extend `IndexNode` with stable metadata: `node_type`, `parent_path`, `keywords`, `source`, `confidence`, `evidence_pages`, `char_start`, `char_end`.
  - Add deterministic ID helper.

- Modify: `lambda/index_materials/builders/document.py`
  - Use deterministic IDs.
  - Create recursive child nodes for long sections.
  - Preserve heading paths.

- Modify: `lambda/index_materials/builders/slides.py`
  - Use deterministic IDs.
  - Mark slide nodes with `node_type="slide"`.

- Modify: `lambda/index_materials/builders/problems.py`
  - Use deterministic IDs.
  - Mark problem/solution nodes with explicit node types.

- Modify: `lambda/index_materials/builders/assessment.py`
  - Use deterministic IDs.
  - Mark question nodes with `node_type="question"`.

- Modify: `lambda/index_materials/worker.py`
  - Stamp page rows with `section_path`, not only `section_name`.
  - Prefer leaf-node summaries for evidence and parent summaries for routing.

- Modify: `lambda/index_materials/db.py`
  - Store new fields in JSON first, without requiring schema migration for every attribute.
  - Add optional `section_path` support in `material_page_text` if schema exists.

- Test: `lambda/index_materials/tests/test_base.py`
- Test: `lambda/index_materials/tests/test_document.py`
- Test: `lambda/index_materials/tests/test_slides.py`
- Test: `lambda/index_materials/tests/test_problems.py`
- Test: `lambda/index_materials/tests/test_assessment.py`
- Test: `lambda/index_materials/tests/test_worker.py` if it already exists; otherwise create focused tests beside existing tests.

## Task 1: Stable Index Node Model

**Files:**
- Modify: `lambda/index_materials/builders/base.py`
- Test: `lambda/index_materials/tests/test_base.py`

- [ ] **Step 1: Write failing tests for deterministic IDs and metadata serialization**

Add tests:

```python
from builders.base import IndexNode, MaterialIndex, stable_node_id


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
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd /Users/shubhan/OneShotCourseMate
pytest lambda/index_materials/tests/test_base.py -v
```

- [ ] **Step 3: Implement model fields and stable ID helper**

In `builders/base.py`, add:

```python
import hashlib
import re
from dataclasses import dataclass, field


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return value[:48] or "untitled"


def stable_node_id(title: str, start_page: int, end_page: int, parent_path: list[str] | None = None) -> str:
    path = " > ".join(parent_path or [])
    raw = f"{path}|{title}|{start_page}|{end_page}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"node_{_slug(title)}_{start_page}_{end_page}_{digest}"
```

Extend `IndexNode`:

```python
@dataclass
class IndexNode:
    node_id: str
    title: str
    start_page: int
    end_page: int
    summary: str = ""
    nodes: list["IndexNode"] = field(default_factory=list)
    node_type: str = "section"
    parent_path: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source: str = "unknown"
    confidence: float = 1.0
    evidence_pages: list[int] = field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "nodes": [n.to_dict() for n in self.nodes],
            "node_type": self.node_type,
            "parent_path": self.parent_path,
            "keywords": self.keywords,
            "source": self.source,
            "confidence": self.confidence,
            "evidence_pages": self.evidence_pages or list(range(self.start_page, self.end_page + 1)),
            "char_start": self.char_start,
            "char_end": self.char_end,
        }
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest lambda/index_materials/tests/test_base.py -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/base.py lambda/index_materials/tests/test_base.py
git commit -m "Improve page index node metadata"
```

## Task 2: Breadcrumbs and Page Context

**Files:**
- Modify: `lambda/index_materials/worker.py`
- Test: `lambda/index_materials/tests/test_worker.py`

- [ ] **Step 1: Write failing tests for page breadcrumbs**

Create `lambda/index_materials/tests/test_worker.py` if missing:

```python
from builders.base import IndexNode
from worker import _resolve_section_names


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
    material_index = type("MaterialIndexStub", (), {"nodes": [root]})()

    rows = [{"page_number": 2, "text_content": "data", "has_images": False}]
    resolved = _resolve_section_names(rows, material_index)

    assert resolved[0]["section_name"] == "Dataset"
    assert resolved[0]["section_path"] == ["Methods", "Dataset"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest lambda/index_materials/tests/test_worker.py::test_resolve_section_names_adds_leaf_and_path -v
```

- [ ] **Step 3: Update `_resolve_section_names`**

Replace the walker with path-aware traversal:

```python
def _resolve_section_names(page_rows: list[dict], material_index) -> list[dict]:
    """Stamp each page row with nearest leaf section title and full breadcrumb path."""

    def _walk(nodes, page_num: int, path: list[str]) -> tuple[str | None, list[str]]:
        for node in nodes:
            if node.start_page <= page_num <= node.end_page:
                current_path = path + [node.title]
                child_title, child_path = _walk(node.nodes, page_num, current_path)
                if child_title:
                    return child_title, child_path
                return node.title, current_path
        return None, []

    result = []
    for row in page_rows:
        section, section_path = _walk(material_index.nodes, row["page_number"], [])
        result.append({**row, "section_name": section, "section_path": section_path})
    return result
```

- [ ] **Step 4: Run test**

```bash
pytest lambda/index_materials/tests/test_worker.py -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/worker.py lambda/index_materials/tests/test_worker.py
git commit -m "Add section breadcrumbs to page index"
```

## Task 3: Persist Breadcrumbs Without Breaking Existing DBs

**Files:**
- Modify: `lambda/index_materials/db.py`
- Test: `lambda/index_materials/tests/test_db.py`

- [ ] **Step 1: Write tests for tolerant storage payload**

Use a fake cursor/connection so the test does not need Postgres:

```python
from db import store_page_texts


class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_store_page_texts_accepts_section_path():
    conn = FakeConn()
    rows = [{
        "page_number": 1,
        "text_content": "Intro",
        "has_images": False,
        "section_name": "Introduction",
        "section_path": ["Paper", "Introduction"],
    }]

    store_page_texts(conn, 123, rows)

    assert conn.calls
    sql, params = conn.calls[0]
    assert "material_page_text" in sql
    assert 123 in params
```

- [ ] **Step 2: Run test to verify current behavior**

```bash
pytest lambda/index_materials/tests/test_db.py::test_store_page_texts_accepts_section_path -v
```

- [ ] **Step 3: Store `section_path` opportunistically**

If the current schema has a JSON column for page metadata, store it there. If not, keep `section_path` in `material_page_index.index_json` and leave `material_page_text` backward-compatible. Do not require a migration in this task unless the app already has migration machinery.

Add `section_path` to the page rows saved inside `material_page_index.index_json` through `material_index.to_dict()` or a `page_context` field:

```python
index_payload = {
    **index_dict,
    "page_context": [
        {
            "page_number": row["page_number"],
            "section_name": row.get("section_name"),
            "section_path": row.get("section_path", []),
            "has_images": row.get("has_images", False),
        }
        for row in page_rows
    ],
}
```

Use this payload for `store_page_index`.

- [ ] **Step 4: Run db and worker tests**

```bash
pytest lambda/index_materials/tests/test_db.py lambda/index_materials/tests/test_worker.py -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/db.py lambda/index_materials/tests/test_db.py lambda/index_materials/worker.py
git commit -m "Persist page index breadcrumb context"
```

## Task 4: Deterministic Builders

**Files:**
- Modify: `lambda/index_materials/builders/document.py`
- Modify: `lambda/index_materials/builders/slides.py`
- Modify: `lambda/index_materials/builders/problems.py`
- Modify: `lambda/index_materials/builders/assessment.py`
- Test matching files under `lambda/index_materials/tests/`

- [ ] **Step 1: Add failing tests that rerun builders twice**

For each builder test file, add a deterministic-ID test. Example for `test_document.py`:

```python
from builders.document import build_from_pages


def test_document_builder_ids_are_stable():
    pages = ["## Intro\nText", "## Methods\nMore text"]
    a = build_from_pages(pages, doc_type="reading", title="Paper").to_dict()
    b = build_from_pages(pages, doc_type="reading", title="Paper").to_dict()
    assert a == b
```

- [ ] **Step 2: Run builder tests**

```bash
pytest lambda/index_materials/tests/test_document.py lambda/index_materials/tests/test_slides.py lambda/index_materials/tests/test_problems.py lambda/index_materials/tests/test_assessment.py -v
```

- [ ] **Step 3: Replace random IDs with `stable_node_id`**

In every builder, import:

```python
from builders.base import IndexNode, MaterialIndex, stable_node_id
```

When creating a node:

```python
parent_path = existing_path
node = IndexNode(
    node_id=stable_node_id(title, start_page, end_page, parent_path),
    title=title,
    start_page=start_page,
    end_page=end_page,
    parent_path=parent_path,
    node_type="section",
    source="regex",
    confidence=0.8,
)
```

Use node types:
- `section` for reading/document headings
- `slide` for lecture slides
- `problem` for homework prompts
- `solution` for homework solutions
- `question` for quiz/exam questions

- [ ] **Step 4: Run tests**

```bash
pytest lambda/index_materials/tests -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/builders lambda/index_materials/tests
git commit -m "Make page index builders deterministic"
```

## Task 5: Long Section Leaf Splitting

**Files:**
- Modify: `lambda/index_materials/builders/document.py`
- Test: `lambda/index_materials/tests/test_document.py`

- [ ] **Step 1: Add failing test for recursive leaf splitting**

```python
from builders.document import build_from_pages


def test_long_section_creates_child_page_windows():
    pages = [f"Page {i}" for i in range(1, 8)]
    pages[0] = "## Long Section\nPage 1"

    mi = build_from_pages(
        pages,
        doc_type="reading",
        title="Paper",
        headings_override=[(0, "Long Section")],
    )

    root = mi.nodes[0]
    assert root.title == "Long Section"
    assert root.nodes
    assert all(child.end_page - child.start_page <= 2 for child in root.nodes)
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest lambda/index_materials/tests/test_document.py::test_long_section_creates_child_page_windows -v
```

- [ ] **Step 3: Add page-window children for long sections**

In `document.py`, define:

```python
MAX_LEAF_PAGES = 2


def _window_children(title: str, start_page: int, end_page: int, parent_path: list[str]) -> list[IndexNode]:
    children = []
    page = start_page
    while page <= end_page:
        child_end = min(page + MAX_LEAF_PAGES - 1, end_page)
        child_title = f"{title} pages {page}-{child_end}"
        children.append(IndexNode(
            node_id=stable_node_id(child_title, page, child_end, parent_path + [title]),
            title=child_title,
            start_page=page,
            end_page=child_end,
            node_type="page_window",
            parent_path=parent_path + [title],
            source="fallback_window",
            confidence=0.6,
            evidence_pages=list(range(page, child_end + 1)),
        ))
        page = child_end + 1
    return children
```

When a section spans more than `MAX_PAGES_PER_NODE` or retrieval leaf threshold, add children from `_window_children`.

- [ ] **Step 4: Run document tests**

```bash
pytest lambda/index_materials/tests/test_document.py -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/document.py lambda/index_materials/tests/test_document.py
git commit -m "Split long page index sections into retrieval leaves"
```

## Task 6: Figure, Table, and Equation Signals

**Files:**
- Modify: `lambda/index_materials/builders/document.py`
- Test: `lambda/index_materials/tests/test_document.py`

- [ ] **Step 1: Add failing tests for caption nodes**

```python
from builders.document import build_from_pages


def test_document_builder_creates_caption_nodes():
    pages = [
        "## Results\nFigure 1: Accuracy by model.\nTable 1: Dataset statistics.",
    ]

    mi = build_from_pages(pages, doc_type="reading", title="Paper")
    child_types = [child.node_type for node in mi.nodes for child in node.nodes]

    assert "figure" in child_types
    assert "table" in child_types
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest lambda/index_materials/tests/test_document.py::test_document_builder_creates_caption_nodes -v
```

- [ ] **Step 3: Extract caption nodes**

Add regex extraction:

```python
CAPTION_RE = re.compile(r"^(Figure|Fig\\.|Table|Equation|Eq\\.)\\s*\\d+[:.].+", re.IGNORECASE | re.MULTILINE)


def _caption_nodes(page_text: str, page_num: int, parent_path: list[str]) -> list[IndexNode]:
    nodes = []
    for m in CAPTION_RE.finditer(page_text):
        raw = m.group(0).strip()
        kind = raw.split()[0].lower().rstrip(".")
        node_type = "figure" if kind in {"figure", "fig"} else "table" if kind == "table" else "equation"
        nodes.append(IndexNode(
            node_id=stable_node_id(raw, page_num, page_num, parent_path),
            title=raw[:160],
            start_page=page_num,
            end_page=page_num,
            node_type=node_type,
            parent_path=parent_path,
            source="caption_regex",
            confidence=0.9,
            evidence_pages=[page_num],
            char_start=m.start(),
            char_end=m.end(),
        ))
    return nodes
```

Attach caption nodes to the nearest section node for that page.

- [ ] **Step 4: Run tests**

```bash
pytest lambda/index_materials/tests/test_document.py -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/document.py lambda/index_materials/tests/test_document.py
git commit -m "Add figure and table nodes to page index"
```

## Task 7: Node Keywords for Retrieval Routing

**Files:**
- Modify: `lambda/index_materials/llm_client.py`
- Modify: `lambda/index_materials/worker.py`
- Test: `lambda/index_materials/tests/test_llm_client.py`
- Test: `lambda/index_materials/tests/test_worker.py`

- [ ] **Step 1: Add tests for keyword prompt and assignment**

```python
from llm_client import build_node_keywords_prompt


def test_build_node_keywords_prompt_requests_json_array():
    prompt = build_node_keywords_prompt("reading", "Transformer attention datasets")
    assert "JSON array" in prompt
    assert "Transformer attention datasets" in prompt
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest lambda/index_materials/tests/test_llm_client.py::test_build_node_keywords_prompt_requests_json_array -v
```

- [ ] **Step 3: Add prompt builder and lightweight extractor**

In `llm_client.py`:

```python
def build_node_keywords_prompt(doc_type: str, section_text: str) -> str:
    return (
        f"Extract 5 to 15 retrieval keywords for this {doc_type} section. "
        "Return only a JSON array of short strings. Include methods, datasets, "
        "metrics, named entities, formulas, and key concepts when present.\\n\\n"
        f"{section_text[:6000]}"
    )
```

In `worker.py`, after node summary, call keyword extraction with safe fallback. If the LLM call fails, derive keywords from title words only.

- [ ] **Step 4: Run tests**

```bash
pytest lambda/index_materials/tests/test_llm_client.py lambda/index_materials/tests/test_worker.py -v
```

- [ ] **Step 5: Commit**

```bash
git add lambda/index_materials/llm_client.py lambda/index_materials/worker.py lambda/index_materials/tests
git commit -m "Add retrieval keywords to page index nodes"
```

## Task 8: Full Verification

**Files:**
- No new files

- [ ] **Step 1: Run index-materials test suite**

```bash
cd /Users/shubhan/OneShotCourseMate
pytest lambda/index_materials/tests -v
```

- [ ] **Step 2: Run a local smoke index against a small PDF fixture**

Use an existing PDF fixture if present. If none exists, create a small fixture in the retrieval sandbox plan, not here.

- [ ] **Step 3: Inspect serialized output**

Confirm `material_page_index.index_json` contains:
- deterministic `node_id`
- `node_type`
- `parent_path`
- `keywords`
- `source`
- `confidence`
- `evidence_pages`
- caption/table/equation nodes when present

- [ ] **Step 4: Commit final cleanup**

```bash
git status --short
git add lambda/index_materials
git commit -m "Complete page indexing retrieval improvements"
```

## Review Checklist

- Every node is stable across reruns.
- Every page has a leaf `section_name` and full `section_path`.
- Long sections have retrieval leaves.
- Captions/tables/equations become addressable nodes.
- Summaries remain routing hints, not final evidence.
- Raw page text remains stored and retrievable.

