# Visual Page Descriptors — Design Spec

**Date:** 2026-05-25  
**Branch:** feat-pageindex-rag  
**Status:** Approved

## Problem

The `index_materials` pipeline extracts text and detects image presence (`has_images BOOLEAN`) but captures nothing about what images contain. Lecture slides in particular are predominantly visual — diagrams, neural network figures, loss curves, tables of hyperparameters — and a text-only index misses all of it. Queries about "the diagram showing backpropagation" or "the table comparing activation functions" return nothing useful.

## Goal

For every page where `has_images=True`, render the page, call a vision LLM, and store the result as:
1. Structured rows in a new `material_page_visuals` table (raw, re-generatable)
2. Individual `IndexNode` children of type `"figure"` or `"table"` in the existing section tree (first-class retrieval targets)

## Decisions

| Decision | Choice |
|----------|--------|
| Storage | Separate `material_page_visuals` table + child nodes in tree |
| Model | `gpt-4o-mini` vision, reuses `OPENAI_API_KEY_INDEXER` |
| Scope | All doc types when `has_images=True` |
| Architecture | New `image_helper.py` module; called from `worker.py` page loop |
| Granularity | One child `IndexNode` per detected figure + per detected table |
| Output format | Structured JSON: `visual_summary`, `detected_figures`, `detected_tables` |

---

## Architecture

### New module: `lambda/index_materials/image_helper.py`

Four functions, each with one responsibility:

**`render_page_png(fitz_page, dpi=150) -> bytes`**  
Renders the fitz page to PNG bytes using `page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72)).tobytes("png")`. 150 DPI is sufficient for `gpt-4o-mini` to identify figures, read labels, and distinguish table structure.

**`describe_page_visuals(png_bytes, api_key) -> dict`**  
Base64-encodes the PNG, calls `llm_client.describe_visuals()`, parses the JSON response. Returns:
```json
{
  "visual_summary": "Slide showing a 3-layer neural network diagram with labeled weights",
  "detected_figures": [
    {"label": "Figure 1", "description": "Feedforward network with input, hidden, output layers"}
  ],
  "detected_tables": [
    {"label": "Table 1", "description": "Comparison of activation functions: sigmoid, tanh, ReLU"}
  ]
}
```
On any failure (timeout, parse error, API error) returns `{"visual_summary": "", "detected_figures": [], "detected_tables": []}`. Vision failure is never fatal to the pipeline.

**`make_visual_nodes(page_number, visuals) -> list[IndexNode]`**  
Creates one `IndexNode` per entry in `detected_figures` + `detected_tables`. Each node:
- `node_type` = `"figure"` or `"table"`
- `title` = the label string (e.g. `"Figure 1"`)
- `summary` = the description string
- `start_page = end_page = page_number`
- `keywords` = derived from the description (reuse existing keyword extraction)
- `node_id` = `stable_node_id(title, page_number, page_number)`

Returns `[]` when both arrays are empty — no phantom nodes.

**`attach_visual_nodes(material_index, page_visuals) -> None`** (mutates in place)  
Called after `route_builder()` returns. Walks the `MaterialIndex` node tree. For each `IndexNode`, determines its effective page set as `node.evidence_pages or range(node.start_page, node.end_page + 1)` (matching the same fallback used in `IndexNode.to_dict()`). If any page in that set appears in `page_visuals`, appends the corresponding visual nodes as children. Keeps all builders unmodified.

---

### `llm_client.py` extension

New function: **`describe_visuals(png_b64, api_key) -> str`**

Follows the identical pattern as the existing `summarize()` — one POST to `https://api.openai.com/v1/chat/completions` with `gpt-4o-mini`. The user message is multimodal:
```json
[
  {"type": "text", "text": "<prompt>"},
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,<b64>"}}
]
```
Prompt instructs the model to return **only** a JSON object with `visual_summary` (≤120 tokens prose), `detected_figures` (array of `{label, description}`), `detected_tables` (array of `{label, description}`). Returns raw content string; `image_helper` owns JSON parsing.

---

### DB schema: new `material_page_visuals` table

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

`db.py` gets one new function:
```python
store_page_visuals(conn, material_id, page_number, visuals_dict) -> None
```
Upserts a single row. No changes to existing `store_page_texts` or `store_material_index`.

---

### `worker.py` integration

**During the page loop** — collect visual data per page:
```python
page_visuals: dict[int, list[IndexNode]] = {}

for i, page in enumerate(doc):
    md = ...
    has_img = _has_images(page)
    page_rows.append({...})

    if has_img and api_key:
        png = image_helper.render_page_png(page)
        visuals = image_helper.describe_page_visuals(png, api_key)
        db.store_page_visuals(conn, material_id, i + 1, visuals)
        nodes = image_helper.make_visual_nodes(i + 1, visuals)
        if nodes:
            page_visuals[i + 1] = nodes
```

**After `route_builder()` returns** — attach to tree before storing:
```python
material_index = route_builder(...)
image_helper.attach_visual_nodes(material_index, page_visuals)
db.store_material_index(conn, material_id, material_index)
```

No changes to any builder (`slides.py`, `document.py`, `problems.py`, `assessment.py`).

---

### `pageindex_retrieval.py` update

`get_page_content()` gains a LEFT JOIN on `material_page_visuals (material_id, page_number)`. The returned page dict includes `visual_summary`, `detected_figures`, `detected_tables` when present, `None` otherwise. No breaking change to callers.

---

## Error Handling

All vision errors are non-fatal:

| Failure | Behaviour |
|---------|-----------|
| API timeout / HTTP error | `describe_page_visuals` returns empty fallback dict |
| JSON parse failure | Same empty fallback |
| `fitz` render error | `render_page_png` returns `None`; `describe_page_visuals` skips API call and returns fallback |
| Empty model response | `make_visual_nodes` returns `[]`; no nodes attached, no DB row written |

---

## Testing

**`lambda/index_materials/tests/test_image_helper.py`**

| Test | What it verifies |
|------|-----------------|
| `test_make_visual_nodes_figures` | Two `detected_figures` → two `IndexNode` with `node_type="figure"` |
| `test_make_visual_nodes_tables` | One `detected_table` → one `IndexNode` with `node_type="table"` |
| `test_make_visual_nodes_mixed` | Mix of figures and tables → correct types assigned |
| `test_make_visual_nodes_empty` | Empty arrays → `[]` returned |
| `test_describe_page_visuals_parse_failure` | Mock returns malformed JSON → empty fallback returned, no exception |
| `test_describe_page_visuals_api_error` | Mock raises `requests.RequestException` → empty fallback returned |
| `test_attach_visual_nodes` | `MaterialIndex` with one section covering page 2, `page_visuals={2: [figure_node]}` → figure_node appears as child |
| `test_attach_visual_nodes_no_match` | `page_visuals` keys don't overlap evidence_pages → tree unchanged |

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `lambda/index_materials/image_helper.py` | Create | Render, describe, make nodes, attach to tree |
| `lambda/index_materials/llm_client.py` | Modify | Add `describe_visuals()` multimodal function |
| `lambda/index_materials/db.py` | Modify | Add `store_page_visuals()` |
| `lambda/index_materials/worker.py` | Modify | Call image_helper in page loop + attach after builder |
| `lambda/index_materials/tests/test_image_helper.py` | Create | Unit tests for all image_helper functions |
| `api/services/query/pageindex_retrieval.py` | Modify | LEFT JOIN material_page_visuals in get_page_content() |

**DB migration (run directly against DB — not a script):**
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
