# RAG Page Index Retrieval Eval

Retrieval-only sandbox for testing `lambda/index_materials` page-index ideas.

Run the fixture:

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.run_eval \
  --qasper-json experiments/rag_page_index_eval/fixtures/mini_qasper.json \
  --out experiments/rag_page_index_eval/out/mini_results.csv \
  --summary-out experiments/rag_page_index_eval/out/mini_summary.md \
  --k 5
```

Run a real QASPER JSON file:

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.run_eval \
  --qasper-json /path/to/qasper-test-v0.3.json \
  --out experiments/rag_page_index_eval/out/qasper_real_results.csv \
  --summary-out experiments/rag_page_index_eval/out/qasper_real_summary.md \
  --k 5
```

The real QASPER path evaluates evidence-location retrieval. QASPER supplies paper text,
questions, answers, and human evidence strings; it does not provide PDF page boundaries in
this JSON flow.

Run the production LLM-routed PageIndex path:

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.agentic_eval_runner \
  --qasper-json /path/to/qasper-test-v0.3.json \
  --out experiments/rag_page_index_eval/out/qasper_agentic_results.csv \
  --summary-out experiments/rag_page_index_eval/out/qasper_agentic_summary.md \
  --model gpt-4o-mini \
  --k 5
```

This adapter backs the production `run_agent_pageindex(...)` tools with QASPER data:
`get_course_routing_index`, `get_material_structure`, `get_page_content`, and
`get_related_materials`. The metric cutoff is the first `k` unique evidence locations fetched
through `get_page_content` calls, in tool-call order. The agentic runner defaults to
`--limit 50`; pass `--limit 0` is not supported, so use an explicit full count such as
`--limit 1451` for the full QASPER test split.

The adapter runs QASPER section text through the real CourseMate document builder before
exposing production-shaped tools. This exercises deterministic section/page-window summaries
and keyword enrichment from `lambda/index_materials/builders/document.py`.

Variants:

- `page_bm25`: searches page text.
- `section_bm25`: searches index node title, summary, and keywords.
- `two_stage`: retrieves index nodes, then searches pages in selected node ranges.
- `hybrid`: combines page and section scores.

Metrics:

- `recall_at_k`
- `mrr_at_k`
- `ndcg_at_k`
- `evidence_location_hit_at_k`
- `answerability_coverage`
