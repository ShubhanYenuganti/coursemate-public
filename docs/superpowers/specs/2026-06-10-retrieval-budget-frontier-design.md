# Retrieval Budget Frontier - Design

**Date:** 2026-06-10
**Status:** Drafted from brainstorming, pending implementation
**Scope:** PageIndex agent loop in `api/llm.py` and PageIndex retrieval helpers in `api/pageindex_retrieval.py`.

## Problem

PageIndex retrieval currently asks the agent to choose a few page ranges from the routing tree and then fetches full raw text for those pages. This works for narrow questions, but it has two failure modes:

1. Broad questions may require coverage across many sections, more than the current "2-4 candidate evidence locations" prompt encourages.
2. Retrieved evidence has no explicit context-window budget. Each selected range is passed as raw page text into synthesis, so broad retrieval can either miss coverage or consume too much context.

The model cannot reliably decide that evidence coverage is weak after reading only a few raw page ranges. Coverage selection needs to happen earlier, while the agent is looking at the routing tree.

## Goal

Support broad questions by letting the model select a larger candidate frontier from the routing tree, while the system deterministically budgets how much of that frontier becomes raw page text versus compact summaries. The budget must scale with the selected synthesis model's context window and must not starve chat history or final output.

## Decisions

1. **Hybrid strategy:** use a base retrieval budget plus staged expansion for broad questions.
2. **Model-selected candidates:** the model chooses the candidate frontier and ranks it. The system does not rerank candidates by route score.
3. **Budget-enforced materialization:** the system decides how much raw text and summary evidence can be admitted.
4. **Mixed representation:** the top model-selected subset gets raw page text; the remaining selected candidates become compact summary evidence.
5. **Index-time token accounting:** raw and summary admission use token counts computed by the document indexer, not an average page-cost estimate.
6. **Output remains protected:** retrieval must not borrow from the output cap. If expansion needs room, it should first reduce replayed chat history within its existing cap.

## Existing Budget Slices

Current budget constants in `api/llm.py`:

- `HISTORY_CONTEXT_RATIO = 0.35`
- `OUTPUT_CONTEXT_RATIO = 0.05`
- `SAFETY_MARGIN_RATIO = 0.15`
- `RESPONSE_RESERVE_TOKENS = 4096`
- `MIN_OUTPUT_TOKENS = 2048`
- `MAX_OUTPUT_TOKENS = 8192`

History is capped by model window and reduced by system text, current user text, response reserve, and safety margin. Output is capped by model window and clamped to 2048-8192 tokens. Retrieval evidence has no explicit slice today.

## Proposed Retrieval Budget

Add a retrieval budget model:

```text
retrieval_base_budget = model_window * 0.12
retrieval_max_budget = model_window * 0.25
raw_budget = active_retrieval_budget * 0.65
summary_budget = active_retrieval_budget * 0.35
```

Clamp retrieval budgets to avoid extreme behavior:

```text
MIN_RETRIEVAL_TOKENS = 4096
MAX_RETRIEVAL_TOKENS = 48000
```

The raw/summary split is enforced with stored token counts:

```text
raw_candidates use material_page_text.token_count
summary_candidates use IndexNode.token_count for the selected section span
```

For broad questions, the active retrieval budget can expand from base to max. For narrow questions, use the base budget only.

## Budget Interaction

Retrieval becomes a reserved budget before chat history is composed:

```text
history_budget = window
  - system_tokens
  - current_user_tokens
  - response_reserve
  - safety_margin
  - active_retrieval_budget
```

The existing `HISTORY_CONTEXT_RATIO` cap still applies after this subtraction. This means retrieval expansion borrows from replayed history first. Output remains protected by `_output_token_cap` and is not reduced by retrieval expansion.

Before composing history, make a small agent classification call that labels the current query as `broad` or `specific`.

- `broad`: questions that likely need coverage across many sections, many concepts, comparisons, surveys, overviews, or cross-material synthesis.
- `specific`: narrow lookups, single-definition requests, page-specific questions, or questions likely answerable from a small number of pages.

The classification result only decides whether the retrieval budget uses the max or base slice:

```text
scope == "broad"    -> active_retrieval_budget = retrieval_max_budget
scope == "specific" -> active_retrieval_budget = retrieval_base_budget
```

If the classifier output is malformed or unavailable, default to `specific` so the system keeps the cheaper base slice. The model still chooses the candidate frontier after the budget is selected.

## Index-Time Token Accounting

Add a shared `TokenCounter` class in `lambda/index_materials` and call it from the index-building pipeline after each builder returns a `MaterialIndex`.

The counter should provide one canonical heuristic for now:

```text
token_count = max(1, len(text) // 4)
```

This mirrors the backend estimator used in `api/llm.py` and avoids adding tokenizer dependencies. If a real tokenizer is added later, the `TokenCounter` class becomes the single indexer-side implementation to upgrade.

Persist token counts in two places:

- `material_page_text.token_count`: the estimated token count of each extracted raw page.
- `material_page_index.index_json.nodes[*].token_count`: the estimated token count of each section/node span. Child nodes carry their own counts.

The section token count is stored in `index_json` because sections are nested tree nodes, not table rows. The raw page token count belongs in `material_page_text` because materialization fetches raw pages from that table.

## Candidate Frontier Flow

### 1. Candidate selection

Add a PageIndex tool that lets the model propose a ranked frontier without fetching raw text:

```text
select_page_candidates(candidates)
```

Each candidate contains:

- `material_id`
- `pages`
- `reason`
- `priority`: `core`, `supporting`, or `background`

The prompt instructs the agent:

- For narrow questions, select a small frontier.
- For broad, comparative, survey, "explain all", or cross-topic questions, select all plausible candidate ranges from the routing tree.
- Order candidates by expected importance; the first candidates are eligible for raw text.

### 2. Candidate validation

The backend parses and normalizes the candidate list:

- Drop malformed candidates.
- Clamp page ranges to positive integers.
- De-duplicate `(material_id, page_number)` while preserving model order.
- Split ranges into page-level candidates for budgeting.
- Retain source metadata for trace and citations.

### 3. Materialization

Materialize selected candidates under the active retrieval budget:

- Iterate normalized candidates in priority order: `core`, then `supporting`, then `background`, preserving model order within each priority.
- Add raw page text while `running_raw_tokens + page.token_count <= raw_budget`.
- If a candidate does not fit in the raw budget, leave it for summary evidence.
- Continue scanning later candidates so shorter later pages can still use remaining raw budget.
- Every normalized selected page that is not admitted as raw evidence becomes summary evidence unless doing so would exceed `summary_budget`, the page has no available section summary, or the candidate was dropped during validation.
- If summary evidence exceeds `summary_budget`, keep candidates in model order until budget is exhausted and report the drop count in metadata.

### 4. Synthesis

Synthesis receives a single evidence block with two sections:

```text
Raw retrieved course material:
...

Candidate coverage summaries:
...
```

The synthesis prompt should make this distinction explicit:

- Raw material is direct evidence.
- Candidate summaries are coverage evidence from the course index and should be used for orientation, caveats, and deciding what was covered.
- If a key answer detail is only in a summary, say the page/section appears relevant but raw text was not included.

## Interaction With Existing Tools

`get_page_content` remains available for direct raw fetches and backwards compatibility. The new broad frontier path should not remove the existing narrow retrieval behavior.

The preferred retrieval behavior becomes:

- Use direct `get_page_content` for narrow lookup questions.
- Use candidate frontier selection for broad questions.
- Use `web_search` when enabled and course evidence does not cover the requested concept.

## Data Flow

1. `run_agent_pageindex` computes retrieval budget from the selected synthesis model.
2. Retrieval prompt includes budget instructions and the new candidate-selection tool.
3. The model either calls `get_page_content` directly or submits a candidate frontier.
4. The backend materializes candidates into raw and summary evidence under budget.
5. `_format_pageindex_evidence` includes raw evidence, summary evidence, and web evidence.
6. Final synthesis runs as a clean no-tool call using the selected model.

## Error Handling

- Empty frontier: fall back to existing direct retrieval behavior if any raw evidence exists; otherwise synthesize with an insufficient-evidence response.
- Malformed candidates: ignore malformed entries and record a trace warning.
- Over-budget frontier: keep ordered candidates until budget is exhausted; record omitted counts in `tool_trace`.
- Missing page text: include the candidate summary if available and mark raw page text missing.
- Provider differences: candidate selection and materialization live in the shared backend path, while provider-specific loops only need to expose the tool schema.

## Testing

Unit tests should cover:

- Retrieval budget calculation for 128k, 200k, 400k, and 1M model windows.
- Raw top-N derivation and clamps.
- Candidate parsing, page expansion, de-duplication, and malformed candidate dropping.
- Materialization splitting candidates into raw and summary buckets.
- Evidence formatting with raw course evidence, summary evidence, and web evidence.
- Prompt/tool schema includes broad frontier instructions for OpenAI, Claude, and Gemini tool paths.

Integration-style unit tests should simulate a broad candidate frontier and verify that synthesis receives both raw and summary evidence under budget.

## Out Of Scope

- Rebuilding the PageIndex indexer.
- Adding embeddings or semantic search over page text.
- Asking the backend to rerank model-selected candidates.
- UI changes.
- Real tokenizer integration.
- New database tables.
