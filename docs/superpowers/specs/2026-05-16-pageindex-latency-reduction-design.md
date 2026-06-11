# PageIndex Latency Reduction — Design

**Date:** 2026-05-16
**Status:** Draft, awaiting review
**Owner:** Shubhan
**Branch:** `feat-pageindex-rag`

## Problem

PageIndex retrieval latency, measured against the 48-case evaluation suite (`tests/pageindex_eval/results_2026-05-16.jsonl`), is too high for production use.

Baseline (gpt-4o-mini, current `api/llm.py::run_agent_pageindex`):

| Metric | Value |
|---|---|
| Median | 7,522 ms |
| P75 | 9,684 ms |
| P90 | 17,546 ms |
| P95 | 23,013 ms |
| Max | 28,574 ms |
| Mean | 8,995 ms |
| Queries >5s | 40 / 48 (83%) |
| Queries >10s | 11 / 48 (23%) |
| Average answer score | 2.85 / 3 |

The dominant latency contributor is the number of sequential LLM round trips inside the agent loop. Each iteration is ~2-4s of TTFT + generation on gpt-4o-mini. The current flow typically takes 3-4 iterations:

1. `search_course_materials` → returns the routing index
2. `get_material_structure` → returns the chosen material's tree
3. `get_page_content` → returns page text
4. Final answer (no tool calls)

## Goal

Reduce median PageIndex latency from ~7.5s to ~4-5s and P95 from ~23s to ~12s **without regressing the 2.85/3 answer-quality floor**.

## Non-Goals

- Swapping the agent model (gpt-4o-mini stays; model A/B is a separate change).
- Preloading material structures (Approach B in brainstorm — deferred).
- Heuristic pre-routing that skips the agent loop (Approach C — incompatible with the quality floor).
- Fixing the vector RAG hit-rate bug (tracked separately per memory 3338).

## Design

One retrieval change plus one eval-runner instrumentation change.

A second change — parallel tool execution within an iteration — was considered and dropped. All four PageIndex tools are pure DB calls; psycopg cannot have two queries in-flight on a single connection, so any lock-based mitigation would serialize the work anyway. The only path to real parallelism is per-worker connections, which adds connection-pool churn for a small (~50-300ms) win that is dwarfed by the per-iteration LLM round trip. Deferred until profiling shows DB latency dominates.

### Change 1 — Preload routing index into the system prompt

**File:** `api/llm.py::run_agent_pageindex`

The first tool call in every observed trace is `search_course_materials`. Its result depends only on `(course_id, context_material_ids)` and is deterministic. There is no reason to spend an LLM round trip on it.

Implementation:
- Before the agent loop, call `get_course_routing_index(conn, course_id, context_material_ids)`.
- Render the result as a compact text block — one line per material with the fields the LLM needs to pick:
  ```
  [<material_id>] <title> | <doc_type> | <page_count>p | tags: <comma-sep tags> | summary: <one-line summary>
  ```
- Append the block to the system message under a `<course_materials>` section header so the agent has it on turn 1.
- Remove `search_course_materials` from the `tools` array — the data is already in context, and leaving the tool would tempt the LLM to call it redundantly.
- Keep the remaining three tools unchanged: `get_material_structure`, `get_page_content`, `get_related_materials`.

Expected effect: one LLM round trip eliminated per query (~2-4s saved on every call).

Risk: prompt grows by roughly N × ~150 tokens. For typical course sizes (≤30 materials) this is well under 5K extra tokens — negligible vs the ~2-4s saved.

### Change 2 — Eval runner instrumentation

**File:** `tests/pageindex_eval/eval_runner.py`

Three additions, all backward compatible:

1. **`--concurrency N` flag** (default 1). When >1, test cases run through a `ThreadPoolExecutor`; each worker opens its own psycopg connection (test cases are independent, so this is safe). Default of 1 preserves today's behavior for reproducibility. This change is purely about wall-clock during eval runs — it does not change per-query latency measurement.
2. **Iteration count per query**. Extract `tool_iteration_count` from the returned `tool_trace` (count of entries with a `"tool"` key) and persist it in the JSONL output alongside `latency_ms`. This lets us verify Change 1 actually eliminated an iteration on average.
3. **Latency distribution in the summary**. Extend the final summary block to print p50, p95, and max latency for both vector and pageindex paths, plus average iteration count for pageindex. Keep existing averages so the format remains additive.

No model changes. No `--agent-models` flag. Judge model (`_llm_judge`) stays on `gpt-4o-mini`.

## Success Criteria

A single eval run against the existing 48-case suite (course_id=7, material_ids=624-637) must show:

1. PageIndex average answer score ≥ **2.85 / 3** (no quality regression).
2. PageIndex median latency ≤ **5,000 ms**.
3. PageIndex P95 latency ≤ **15,000 ms**.
4. PageIndex average iteration count ≤ **2.5** (the current trace shows ~3-4 iterations; if Change 1 worked, the routing-index round trip is gone and most queries should finish in 2 iterations: structure → page-content → answer). The pre-change baseline cannot be measured retroactively because the existing JSONL doesn't record iteration count — Change 3 ships iteration logging, so the first run after this change establishes both the new value and (by re-running once with Change 1 reverted) the baseline if needed for audit.

If 1 fails, revert. If 2-4 fail but 1 passes, the change is still a win but the design assumptions need a second look before moving to Approach B.

## Out-of-Scope / Follow-ups

- **Approach B (preload structures)** — layers cleanly on top of this change if more latency is needed after.
- **Model A/B (gpt-5-nano, gpt-4.1-nano, gpt-4.1-mini)** — a separate change with its own eval run.
- **Vector RAG page-hit-rate bug** — `retrieve_context` fails silently at 0ms; tracked separately.
- **Prompt caching** — OpenAI auto-caches 1024+ token prefixes; the routing-index preload makes the system prompt large enough to benefit. No code change needed.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Removing `search_course_materials` from `tools` breaks a path that depended on it (e.g. when `context_material_ids` is None and the LLM expected to discover materials) | Low | The preload runs the same DB query regardless of filter, so the LLM gets the same data in either case. |
| Routing-index block grows past the model's effective context for very large courses | Low | Courses today have <30 materials. If a course exceeds, say, 100 materials, we should chunk or filter the preload — flag for follow-up, not blocker. |
| Eval concurrency masks intermittent DB errors that show up only under load | Low | Default `--concurrency` stays 1. Concurrency is opt-in. |
