# Page Indexing Flow and Fixture Eval

## End-to-End Page Indexing Flow

```text
PDF bytes
  |
  v
lambda/index_materials/worker.py::index_document
  |
  +-- write PDF to temp file
  |
  +-- _extract_pages(pdf_path)
  |     |
  |     +-- PyMuPDF opens PDF
  |     +-- pymupdf4llm converts each page to markdown
  |     +-- emits page rows:
  |           page_number
  |           text_content
  |           has_images
  |
  +-- route_builder(doc_type)
  |     |
  |     +-- reading/unknown -> builders/document.py
  |     +-- lecture slides -> builders/slides.py
  |     +-- homework -> builders/problems.py
  |     +-- quiz/exam -> builders/assessment.py
  |
  +-- builder creates MaterialIndex
  |     |
  |     +-- deterministic node_id
  |     +-- node_type: section, slide, problem, solution, question, page_window, figure, table, equation
  |     +-- start_page / end_page
  |     +-- parent_path
  |     +-- source + confidence
  |     +-- evidence_pages
  |     +-- child nodes for long sections and captions
  |
  +-- _resolve_section_names(page_rows, material_index)
  |     |
  |     +-- stamps each page with:
  |           section_name
  |           section_path
  |     +-- skips synthetic evidence leaves for page labels
  |
  +-- _summarize_all_nodes(...)
  |     |
  |     +-- summarizes each index node from original page text
  |
  +-- _assign_keywords_all_nodes(...)
  |     |
  |     +-- extracts retrieval keywords
  |     +-- falls back to title words if LLM keyword extraction fails
  |
  +-- _sync_store(...)
        |
        +-- material_page_text
        |     per-page text, images flag, section_name
        |
        +-- material_page_index
        |     full MaterialIndex JSON, including page_context
        |
        +-- course_material_index
        |     document-level summary and metadata tags
        |
        +-- course_material_relations
              optional cross-material relation graph
```

## Retrieval Model Intent

The page index is a routing layer, not the final evidence by itself.

Intended retrieval shape:

1. Use index nodes to narrow the search space by title, breadcrumb, summary, keywords, and node type.
2. Use page ranges and evidence pages to select candidate pages.
3. Return original page text or smaller page/block evidence as the answer-support material.
4. Fall back to global page search when section detection confidence is low.

This keeps summaries useful for navigation while avoiding summary-only retrieval.

## Fixture Eval

### Sandbox path

```text
experiments/rag_page_index_eval/
```

### Fixture

```text
experiments/rag_page_index_eval/fixtures/mini_qasper.json
```

The fixture contains **3 synthetic papers, 30 pages (sections), and 18 queries**. All three
papers cover overlapping vocabulary (attention, sequences, training, models), creating genuine
cross-paper hard negatives for BM25-based retrieval.

| Paper | Sections | Queries | Topic |
| --- | ---: | ---: | --- |
| `transformers_nlp` | 10 | 6 | Transformer architecture and training objectives |
| `efficient_attention` | 10 | 6 | Sparse, linear, and hardware-efficient attention |
| `rnn_sequence` | 10 | 6 | LSTM, GRU, vanishing gradients, seq2seq |

**Design properties that make scores non-trivial:**

- Questions are paraphrased — they do not quote the evidence text directly.
- Two questions (`t1_q6`, `r1_q1`, `r1_q3`) require retrieving evidence from **two separate
  sections**, so a single hit cannot achieve full recall.
- `efficient_attention` paper heavily overlaps `transformers_nlp` in vocabulary (both discuss
  quadratic complexity, self-attention, sequence length), creating cross-paper interference.

### How the eval runs

```
qasper_loader.py         reads papers → PageRecord list (one record per section/page)
                         resolves gold_pages by substring-matching each evidence string
                         against page text
local_index_adapter.py   groups consecutive same-section pages → IndexNodeRecord list
                         uses page text as summary, extracts keywords (words > 5 chars)
retrievers.py            4 variants each build BM25 indexes and return RetrievalHit lists
metrics.py               evaluate_hits() computes recall, MRR, NDCG, page_range_hit
run_eval.py              orchestrates loader → adapter → retrievers → metrics → CSV
```

Gold page resolution (`qasper_loader.py:42`):

```python
for item in evidence:
    evidence_text = str(item)
    for page in pages:
        if page.paper_id == paper_id and evidence_text and evidence_text in page.text:
            gold_pages.add(page.page_number)
```

Gold pages are determined by substring matching, so evidence strings must appear verbatim in
a page's text. Queries with `gold_pages = {}` are skipped by `evaluate_hits` (returns all
zeros) and count against the answerability_coverage metric.

### Command

```bash
PYTHONPATH=. python3 -m experiments.rag_page_index_eval.run_eval \
  --qasper-json experiments/rag_page_index_eval/fixtures/mini_qasper.json \
  --out /tmp/mini_results.csv \
  --k 5
```

### Scores (k=5, 18 queries)

| Variant | Recall@5 | MRR@5 | NDCG@5 | Page Range Hit@5 |
| --- | ---: | ---: | ---: | ---: |
| `page_bm25` | 0.917 | 0.917 | 0.902 | 0.944 |
| `section_bm25` | 0.917 | 0.907 | 0.895 | 0.944 |
| `two_stage` | 0.917 | 0.889 | 0.882 | 0.944 |
| `hybrid` | 0.917 | 0.917 | 0.902 | 0.944 |

### Failure analysis

Two systematic failure modes surface on this fixture:

**1 — Vocabulary mismatch (`t1_q3`, recall=0.000 across all variants)**

Query: *"How does using multiple attention heads expand what the model can simultaneously focus on?"*  
Gold: `transformers_nlp` page 6 (Multi-Head Attention section).

The question uses "multiple", "heads", "expand", "simultaneously", "focus" — none of which
appear in the evidence text ("different representation subspaces", "jointly attend",
"concatenated"). BM25 has no shared tokens to match on; the Abstract (page 1) and the RNN
Comparison section outscore the gold page. This is a textbook lexical gap — the failure case
that motivates embedding-based retrieval.

**2 — Multi-page recall miss (`t1_q6`, recall=0.500 across all variants)**

Query: *"What property of standard self-attention makes it impractical for very long documents?"*  
Gold: pages 3 (Self-Attention) and 10 (Limitations) of `transformers_nlp`.

Page 10 lands at rank 1 (score 10.2) but page 3 is displaced by three `efficient_attention`
pages (ranks 2–4) that also discuss "quadratic", "self-attention", and "long sequences".
Cross-paper interference from the thematically overlapping paper consumes top-5 slots.

**3 — MRR degradation without recall loss (`e1_q1`)**

Query: *"How does restricting which positions each token attends to reduce attention cost?"*  
Gold: `efficient_attention` page 3 (Sparse Attention).

All variants retrieve the correct page within top-5 (recall=1.0) but not at rank 1 (MRR 0.33–0.5).
Generic tokens ("positions", "token", "attend", "reduce") match multiple pages across the corpus
before the specific Sparse Attention section.

## Retrieval Variants

`page_bm25`
: Searches raw page text plus page section context.

`section_bm25`
: Searches index node title, summary, parent path, and keywords.

`two_stage`
: Retrieves sections first, then searches pages inside selected section page ranges.
  Can underperform when the first-stage section ranking is confused by cross-paper noise.

`hybrid`
: Combines page and section scores (0.65 page weight, 0.35 section weight).
  Matches `page_bm25` on this fixture; the page signal dominates.

## Metrics

`recall_at_k`
: Fraction of gold evidence pages recovered by the top-k hits.

`mrr_at_k`
: Reciprocal rank of the first hit that overlaps a gold evidence page in the correct paper.

`ndcg_at_k`
: Rank-quality score capped against the ideal number of relevant evidence pages.

`page_range_hit_at_k`
: Binary hit showing whether any top-k result overlaps a gold evidence page.

`answerability_coverage`
: `1.0` when the query has gold evidence pages; `0.0` for examples without gold page evidence.

## Manual Verification for Real PDFs

After running a real `index_materials` job, inspect `material_page_index.index_json` and confirm:

- node IDs are stable across reruns for the same document
- `section_path` preserves real semantic breadcrumbs
- synthetic nodes like `page_window`, `figure`, and `table` do not overwrite page `section_name`
- long sections get child page windows
- figure/table/equation captions are addressable nodes
- keywords exist on nodes or fall back to title words
- retrieved evidence ultimately points back to original page text
