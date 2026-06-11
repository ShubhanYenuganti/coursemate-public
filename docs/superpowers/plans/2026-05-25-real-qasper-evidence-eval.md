# Real QASPER Evidence Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run CourseMate retrieval evals against real QASPER-style academic QA data using only evidence-location metrics.

**Architecture:** Extend the existing `experiments/rag_page_index_eval` package instead of creating a new pipeline. The loader will support real QASPER schema, preserve evidence strings, resolve them into retrievable evidence locations, and expose corpus stats. The runner will output Recall@k, MRR@k, NDCG@k, Evidence Location Hit@k, and Answerability Coverage.

**Tech Stack:** Python dataclasses, pytest, local BM25 retrievers, CSV/Markdown output.

---

### Task 1: Loader Evidence Metadata

**Files:**
- Modify: `experiments/rag_page_index_eval/types.py`
- Modify: `experiments/rag_page_index_eval/qasper_loader.py`
- Test: `experiments/rag_page_index_eval/tests/test_qasper_loader.py`

- [ ] Write failing tests for real QASPER nested answers and evidence string matching.
- [ ] Run loader tests and verify failure.
- [ ] Add evidence-location fields and loader stats metadata.
- [ ] Run loader tests and verify pass.

### Task 2: Evidence-Location Metric Naming

**Files:**
- Modify: `experiments/rag_page_index_eval/types.py`
- Modify: `experiments/rag_page_index_eval/metrics.py`
- Test: `experiments/rag_page_index_eval/tests/test_metrics.py`

- [ ] Write failing tests for `evidence_location_hit_at_k`.
- [ ] Run metric tests and verify failure.
- [ ] Rename page-range metric output while keeping compatibility for page fixture code.
- [ ] Run metric tests and verify pass.

### Task 3: Runner Outputs

**Files:**
- Modify: `experiments/rag_page_index_eval/run_eval.py`
- Test: `experiments/rag_page_index_eval/tests/test_run_eval.py`

- [ ] Write failing CLI test for CSV fields and Markdown summary.
- [ ] Run runner test and verify failure.
- [ ] Add `--summary-out`, corpus stats, and aggregate metric output.
- [ ] Run runner test and verify pass.

### Task 4: Documentation

**Files:**
- Modify: `experiments/rag_page_index_eval/README.md`
- Modify: `docs/page-indexing-flow-and-eval.md`

- [ ] Document real QASPER input expectations.
- [ ] Document in-scope metrics only.
- [ ] Avoid PDF page accuracy or answer correctness claims.

### Task 5: Verification

**Files:**
- Existing tests under `experiments/rag_page_index_eval/tests`

- [ ] Run focused eval tests.
- [ ] If a real QASPER file is available locally, run the eval and report metrics.
- [ ] If not available, report exact command to run once the dataset JSON is placed locally.
