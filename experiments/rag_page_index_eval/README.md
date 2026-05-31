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

Run the production LLM-routed PageIndex path against an already indexed SQLite store:

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.qasper_sqlite_indexer \
  --dataset-source huggingface \
  --hf-dataset allenai/qasper \
  --split test \
  --sqlite-db experiments/rag_page_index_eval/out/qasper_pageindex.sqlite \
  --course-id 1 \
  --progress-every 25
```

Use `--dataset-source json --qasper-json /path/to/qasper-test-v0.3.json` to index a
local QASPER JSON file instead.
The default indexing mode is `--index-mode llm_enriched`, which requires
`OPENAI_API_KEY_INDEXER` and calls OpenAI for node summaries, node keywords, document
summaries, metadata tags, and an index-time relation-building pass. Use
`--index-mode deterministic` only for fast local debugging.

For a condensed deterministic run, apply `--limit-papers`. By default papers are sorted by
stable QASPER `paper_id` before limiting, so `--limit-papers 200` includes the same first 100
materials as `--limit-papers 100`:

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.qasper_sqlite_indexer \
  --dataset-source huggingface \
  --hf-dataset allenai/qasper \
  --split test \
  --sqlite-db experiments/rag_page_index_eval/out/qasper_pageindex_100.sqlite \
  --course-id 1 \
  --limit-papers 100 \
  --paper-order paper_id \
  --progress-every 5
```

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.agentic_eval_runner \
  --dataset-source huggingface \
  --hf-dataset allenai/qasper \
  --split test \
  --sqlite-db experiments/rag_page_index_eval/out/qasper_pageindex.sqlite \
  --course-id 1 \
  --out experiments/rag_page_index_eval/out/qasper_agentic_results.csv \
  --summary-out experiments/rag_page_index_eval/out/qasper_agentic_summary.md \
  --model gpt-4o-mini \
  --k 5
```

The indexer creates a local SQLite store with production-shaped PageIndex tables:
`material_page_text`, `material_page_index`, `course_material_index`,
`course_material_relations`, plus `qasper_material_map` for scoring paper/material IDs.
The retrieval runner then backs the production `run_agent_pageindex(...)` tools with that
SQLite store:
`get_course_routing_index`, `get_material_structure`, `get_page_content`, and
`get_related_materials`. The metric cutoff is the first `k` unique evidence locations fetched
through `get_page_content` calls, in tool-call order. The agentic runner defaults to
`--limit 50`; pass `--limit 0` is not supported, so use an explicit full count such as
`--limit 1451` for the full QASPER test split.

The SQLite indexer runs QASPER section text through the real CourseMate document builder
before retrieval, then enriches the index with the same OpenAI-backed prompts used by
`lambda/index_materials`. This keeps indexing and retrieval as separate phases: the indexing
command updates the local PageIndex store, and the retrieval command scores the agent against
exactly what was indexed.

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
