# Legacy Chunk/Vector RAG Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the legacy `retrieve_chunks` path as eval-only so it cannot drift back into production, without breaking the QASPER eval baseline that uses it.

**Architecture:** Add a regression guard test that forbids production imports of `retrieve_chunks`, document the function as eval-only, and remove the dead "exact-chunk replay" comment/branch in `api/chat.py` only if confirmed unreachable.

**Tech Stack:** Python, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-legacy-rag-retirement-design.md`

---

### Task 1: Regression guard — no production import of `retrieve_chunks`

**Files:**
- Create: `tests/test_no_legacy_rag_in_production.py`

- [ ] **Step 1: Write the failing-if-violated test**

```python
# tests/test_no_legacy_rag_in_production.py
"""Guard: the legacy chunk retriever must stay eval-only (no production caller)."""
import pathlib

API_DIR = pathlib.Path(__file__).resolve().parent.parent / "api"

def test_no_production_module_references_retrieve_chunks():
    offenders = []
    for path in API_DIR.rglob("*.py"):
        if path.name == "rag.py":          # definition lives here; allowed
            continue
        text = path.read_text(encoding="utf-8")
        if "retrieve_chunks" in text:
            offenders.append(str(path.relative_to(API_DIR.parent)))
    assert offenders == [], (
        "retrieve_chunks is legacy/eval-only and must not be used in production: "
        + ", ".join(offenders)
    )
```

- [ ] **Step 2: Run the test (should already pass — it documents the invariant)**

Run: `pytest tests/test_no_legacy_rag_in_production.py -v`
Expected: PASS (no production module currently references it). If it FAILS, a production caller
exists — STOP and reassess the spec's finding before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_no_legacy_rag_in_production.py
git commit -m "test: guard against legacy retrieve_chunks in production code"
```

---

### Task 2: Mark `retrieve_chunks` eval-only

**Files:**
- Modify: `api/rag.py:123` (docstring on `retrieve_chunks`)

- [ ] **Step 1: Update the docstring**

Replace the opening of `retrieve_chunks` (line 123) so the first docstring line reads:

```python
def retrieve_chunks(conn, query: str, material_ids: list, top_k: int = TOP_K,
                    ...):
    """EVAL-ONLY legacy hybrid chunk/vector search.

    No production caller exists (PageIndex is the only live retrieval path; see api/llm.py:315).
    This function is retained solely as the comparison baseline in
    tests/pageindex_eval/eval_runner.py. Do not call it from api/ production modules — a regression
    guard (tests/test_no_legacy_rag_in_production.py) enforces this.
    """
```

Preserve the existing parameter list exactly; only the docstring changes.

- [ ] **Step 2: Run the eval-import smoke check**

Run: `python -c "import sys; sys.path.insert(0,'api'); import rag; assert hasattr(rag,'retrieve_chunks')"`
Expected: no output, exit 0 (function still importable for the eval).

- [ ] **Step 3: Commit**

```bash
git add api/rag.py
git commit -m "docs: mark retrieve_chunks as eval-only legacy baseline"
```

---

### Task 3: Remove dead "exact-chunk replay" branch in chat.py (conditional)

**Files:**
- Modify: `api/chat.py` (~line 2119 comment "legacy exact-chunk replay")

- [ ] **Step 1: Inspect the branch**

Read `api/chat.py` around lines 2110–2140. Determine whether the "legacy exact-chunk replay" branch
is reachable — specifically whether it hydrates IDs from a table retired by
`migrations/002_retire_legacy_chat_rag_tables.sql`.

- [ ] **Step 2: Decide and act**

- **If unreachable** (reads a retired table / guarded by a condition that is always false): remove
  the dead branch and its comment. Keep the surrounding live logic intact.
- **If reachable**: leave it. Add a one-line code comment `# TODO(legacy): reachable — retirement
  deferred, see 2026-06-10-legacy-rag-retirement plan` and note the finding in the commit message.
  Do not guess or force-remove.

- [ ] **Step 3: Run the chat test suite**

Run: `pytest tests/test_chat_citations.py tests/test_chat_memory.py tests/test_chat_search_snippets.py -v`
Expected: PASS (no behavioral regression).

- [ ] **Step 4: Commit**

```bash
git add api/chat.py
git commit -m "chore: retire dead legacy exact-chunk replay branch in chat (or document if reachable)"
```

---

## Self-Review

- **Spec coverage:** guard test (T1), eval-only doc (T2), conditional chat.py cleanup (T3). ✓
- **Safety:** the live helpers `_invoke_embed_query`/`_search_chat_images` are never touched; T3 is
  explicitly conditional to avoid guessing. ✓
- **No placeholders:** the only branch is an explicit if/else decision in T3 with concrete criteria. ✓
