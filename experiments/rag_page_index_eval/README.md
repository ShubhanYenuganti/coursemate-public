# RAG Page Index Retrieval Eval

Retrieval-only sandbox for testing `lambda/index_materials` page-index ideas.

Run the fixture:

```bash
PYTHONPATH=. python -m experiments.rag_page_index_eval.run_eval \
  --qasper-json experiments/rag_page_index_eval/fixtures/mini_qasper.json \
  --out experiments/rag_page_index_eval/out/mini_results.csv \
  --k 5
```

Variants:

- `page_bm25`: searches page text.
- `section_bm25`: searches index node title, summary, and keywords.
- `two_stage`: retrieves index nodes, then searches pages in selected node ranges.
- `hybrid`: combines page and section scores.

Metrics:

- `recall_at_k`
- `mrr_at_k`
- `ndcg_at_k`
- `page_range_hit_at_k`
- `answerability_coverage`
