# Agentic QASPER Builder Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the agentic PageIndex QASPER evaluation by routing QASPER papers through the real document builder and enriching deterministic node summaries/keywords for better tool selection.

**Architecture:** Keep production `run_agent_pageindex(...)` unchanged. Improve `lambda/index_materials/builders/document.py` so document indexes carry useful non-LLM summaries and keywords, then update `QasperPageIndexAdapter` to expose those real `MaterialIndex` nodes instead of synthetic per-page nodes.

**Tech Stack:** Python dataclasses, pytest, existing `lambda/index_materials` builders, QASPER eval adapter.

---

### Task 1: Deterministic Document Node Summaries and Keywords

**Files:**
- Modify: `lambda/index_materials/builders/document.py`
- Test: `lambda/index_materials/tests/test_document.py`

- [ ] Write tests proving section nodes and page-window children get summaries and keywords.
- [ ] Run tests and verify failure.
- [ ] Add deterministic text summarization and keyword extraction helpers.
- [ ] Populate summaries/keywords for section, fallback root, page-window, and caption nodes.
- [ ] Run tests and verify pass.

### Task 2: QASPER Adapter Uses Real Document Builder

**Files:**
- Modify: `experiments/rag_page_index_eval/agentic_adapter.py`
- Test: `experiments/rag_page_index_eval/tests/test_agentic_adapter.py`

- [ ] Write tests proving adapter material structure comes from `build_from_pages`.
- [ ] Run tests and verify failure.
- [ ] Build one `MaterialIndex` per QASPER paper using real `build_from_pages`.
- [ ] Expose routing sections from builder nodes recursively.
- [ ] Run tests and verify pass.

### Task 3: Eval Defaults and Verification

**Files:**
- Modify: `experiments/rag_page_index_eval/README.md`
- Modify: `docs/page-indexing-flow-and-eval.md`

- [ ] Document that agentic QASPER eval defaults to 50 questions.
- [ ] Document that the adapter uses the real document builder.
- [ ] Run focused tests for document builder and agentic adapter.
