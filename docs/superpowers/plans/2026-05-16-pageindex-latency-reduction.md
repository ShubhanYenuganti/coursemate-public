# PageIndex Latency Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut PageIndex retrieval median latency from ~7.5s to ≤5s by eliminating one LLM round trip per query, and add eval instrumentation to prove it.

**Architecture:** The agent's first tool call is always `search_course_materials`, which returns deterministic data given `(course_id, context_material_ids)`. We compute that data once before the agent loop and inject it directly into the system prompt — the agent skips straight to `get_material_structure` on turn 1. Eval runner gains iteration-count logging, latency percentiles, and an opt-in concurrency flag for faster eval wall-clock.

**Tech Stack:** Python 3, `requests` (existing), `psycopg` (existing), `pytest` + `unittest.mock`, `concurrent.futures.ThreadPoolExecutor`.

**Spec:** [`docs/superpowers/specs/2026-05-16-pageindex-latency-reduction-design.md`](../specs/2026-05-16-pageindex-latency-reduction-design.md)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `api/llm.py` | Modify (lines ~1319-1572, `run_agent_pageindex`) | Add `_format_routing_index_block` helper; preload routing index into system prompt; drop `search_course_materials` from tools list and dispatch branch |
| `tests/test_pageindex_agent.py` | Create | Unit tests for the routing-index helper and the run_agent_pageindex wiring (mocked OpenAI) |
| `tests/pageindex_eval/eval_runner.py` | Modify | Add `--concurrency` flag; persist `tool_iteration_count`; extend summary with p50/p95/max |
| `tests/pageindex_eval/test_eval_runner_helpers.py` | Create | Unit tests for the new `_iteration_count` and `_latency_percentiles` helpers |

No new top-level dependencies.

---

## Task 1: Routing-index formatting helper

**Files:**
- Modify: `api/llm.py` (add helper near the existing `run_agent_pageindex` block, ~line 1310)
- Create: `tests/test_pageindex_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pageindex_agent.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from llm import _format_routing_index_block


def test_format_routing_index_block_basic():
    materials = [
        {
            "material_id": 624,
            "title": "Lecture 1 - Intro",
            "doc_type": "lecture",
            "page_count": 42,
            "summary": "Overview of networking concepts.",
            "tags": ["networking", "intro"],
        },
        {
            "material_id": 625,
            "title": "HW 1",
            "doc_type": "homework",
            "page_count": 5,
            "summary": "Subnetting practice problems.",
            "tags": ["subnetting"],
        },
    ]
    block = _format_routing_index_block(materials)
    assert "<course_materials>" in block
    assert "</course_materials>" in block
    assert "[624]" in block
    assert "[625]" in block
    assert "Lecture 1 - Intro" in block
    assert "lecture" in block
    assert "42p" in block
    assert "networking" in block
    assert "Subnetting practice problems." in block


def test_format_routing_index_block_empty():
    block = _format_routing_index_block([])
    assert "<course_materials>" in block
    assert "(no materials available)" in block


def test_format_routing_index_block_handles_missing_optional_fields():
    materials = [
        {
            "material_id": 1,
            "title": "T",
            "doc_type": None,
            "page_count": None,
            "summary": None,
            "tags": [],
        }
    ]
    block = _format_routing_index_block(materials)
    assert "[1]" in block
    assert "T" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && PYTHONPATH=api pytest tests/test_pageindex_agent.py -v`
Expected: `ImportError` or `AttributeError` because `_format_routing_index_block` doesn't exist yet.

- [ ] **Step 3: Add the helper to `api/llm.py`**

Insert immediately above `def run_agent_pageindex(` (currently line 1319):

```python
def _format_routing_index_block(materials: list[dict]) -> str:
    if not materials:
        return "<course_materials>\n(no materials available)\n</course_materials>"
    lines = ["<course_materials>"]
    for m in materials:
        mid = m.get("material_id")
        title = m.get("title") or ""
        doc_type = m.get("doc_type") or "unknown"
        page_count = m.get("page_count")
        pages_str = f"{page_count}p" if page_count else "?p"
        tags = ", ".join(m.get("tags") or []) or "none"
        summary = (m.get("summary") or "").strip().replace("\n", " ")
        if len(summary) > 240:
            summary = summary[:237] + "..."
        lines.append(
            f"[{mid}] {title} | {doc_type} | {pages_str} | tags: {tags} | summary: {summary}"
        )
    lines.append("</course_materials>")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && PYTHONPATH=api pytest tests/test_pageindex_agent.py -v`
Expected: 3 passing tests.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(pageindex): add routing-index formatter for system prompt preload"
```

---

## Task 2: Preload routing index + drop search_course_materials tool

**Files:**
- Modify: `api/llm.py` (`run_agent_pageindex`, lines ~1319-1572)
- Modify: `tests/test_pageindex_agent.py` (add wiring test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pageindex_agent.py`:

```python
import json
from unittest.mock import patch, MagicMock


def _stub_openai_response_no_tools(content: str = "All done.") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ]
    }
    return resp


def test_run_agent_pageindex_preloads_routing_and_drops_search_tool():
    """The agent should receive the routing index in the system prompt
    and the search_course_materials tool should not be exposed."""
    from llm import run_agent_pageindex

    conn = MagicMock()

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _stub_openai_response_no_tools(
            '{"reply": "ok", "summary": "ok", "follow_ups": [], "clarifying_question": null}'
        )

    routing_rows = [
        {
            "material_id": 10,
            "title": "L1",
            "doc_type": "lecture",
            "page_count": 5,
            "summary": "s",
            "tags": ["t"],
        }
    ]

    with patch("llm.requests.post", side_effect=fake_post), \
         patch("pageindex_retrieval.get_course_routing_index", return_value=routing_rows):
        run_agent_pageindex(
            conn=conn,
            user_message="What is in lecture 1?",
            model="gpt-4o-mini",
            api_key="sk-test",
            chat_id=None,
            course_id=7,
            context_material_ids=[10],
        )

    payload = captured["payload"]
    system_msg = payload["messages"][0]
    assert system_msg["role"] == "system"
    assert "<course_materials>" in system_msg["content"]
    assert "[10]" in system_msg["content"]

    tool_names = [t["function"]["name"] for t in payload["tools"]]
    assert "search_course_materials" not in tool_names
    assert "get_material_structure" in tool_names
    assert "get_page_content" in tool_names
    assert "get_related_materials" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && PYTHONPATH=api pytest tests/test_pageindex_agent.py::test_run_agent_pageindex_preloads_routing_and_drops_search_tool -v`
Expected: AssertionError — `<course_materials>` is not in the system prompt and `search_course_materials` is still in the tools list.

- [ ] **Step 3: Modify `run_agent_pageindex` to preload and drop the tool**

In `api/llm.py`:

(a) Remove the `search_course_materials` entry from the `tools` list (currently the first entry, ~lines 1336-1346). After removal, `tools` should start with `get_material_structure`.

(b) Update the `pageindex_retrieval` import (currently ~line 1329) to include `get_course_routing_index`:

```python
    from pageindex_retrieval import (
        get_course_routing_index,
        get_material_structure,
        get_page_content,
    )
```

(c) Just before the `messages = [...]` line (~line 1412), compute and inject the routing block:

```python
    routing_materials = get_course_routing_index(
        conn, course_id, context_material_ids or None
    )
    routing_block = _format_routing_index_block(routing_materials)
    system_content = (
        AGENTIC_SYSTEM_PROMPT
        + "\n\n"
        + routing_block
        + "\n\nUse the material IDs above when calling get_material_structure or get_page_content."
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_message},
    ]
```

(d) Remove the `search_course_materials` dispatch branch from the tool-call handling loop (currently ~lines 1484-1489):

```python
            if name == "search_course_materials":
                tool_result = get_course_routing_index(
                    conn, course_id, context_material_ids or None
                )
                if on_event:
                    on_event({"type": "tool_call", "tool": "search_course_materials"})
            elif name == "get_material_structure":
```

Replace with the dispatch starting at `if name == "get_material_structure":` (drop the `elif`, make it the first `if`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && PYTHONPATH=api pytest tests/test_pageindex_agent.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Smoke-check the full module still imports**

Run: `cd /Users/shubhan/OneShotCourseMate && PYTHONPATH=api python -c "import llm; print(llm.run_agent_pageindex.__name__)"`
Expected: prints `run_agent_pageindex` with no exceptions.

- [ ] **Step 6: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(pageindex): preload routing index into system prompt, drop search_course_materials tool"
```

---

## Task 3: Eval runner — iteration count + latency percentiles

**Files:**
- Modify: `tests/pageindex_eval/eval_runner.py`
- Create: `tests/pageindex_eval/test_eval_runner_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/pageindex_eval/test_eval_runner_helpers.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from eval_runner import _iteration_count, _latency_percentiles


def test_iteration_count_counts_tool_entries():
    trace = [
        {"tool": "get_material_structure", "args": {}, "iteration": 0},
        {"tool": "get_page_content", "args": {}, "iteration": 1},
        {"iteration": 2, "finish_reason": "stop", "tool_calls": 0, "latency_ms": 800},
    ]
    assert _iteration_count(trace) == 2


def test_iteration_count_empty():
    assert _iteration_count([]) == 0


def test_latency_percentiles_basic():
    values = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
    out = _latency_percentiles(values)
    assert out["p50"] == 5500
    assert out["p95"] == 9500
    assert out["max"] == 10000


def test_latency_percentiles_empty():
    out = _latency_percentiles([])
    assert out == {"p50": 0, "p95": 0, "max": 0}


def test_latency_percentiles_single():
    out = _latency_percentiles([1234])
    assert out["p50"] == 1234
    assert out["p95"] == 1234
    assert out["max"] == 1234
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && pytest tests/pageindex_eval/test_eval_runner_helpers.py -v`
Expected: ImportError — neither helper exists.

- [ ] **Step 3: Add the helpers to `eval_runner.py`**

In `tests/pageindex_eval/eval_runner.py`, add these two helpers immediately below the existing `_page_hit_rate` function (~line 62):

```python
def _iteration_count(tool_trace: list) -> int:
    return sum(1 for entry in tool_trace if "tool" in entry)


def _latency_percentiles(values: list[int]) -> dict:
    if not values:
        return {"p50": 0, "p95": 0, "max": 0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def _pct(p: float) -> int:
        if n == 1:
            return int(sorted_vals[0])
        rank = p * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return int(round(sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])))

    return {"p50": _pct(0.5), "p95": _pct(0.95), "max": int(sorted_vals[-1])}
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run: `cd /Users/shubhan/OneShotCourseMate && pytest tests/pageindex_eval/test_eval_runner_helpers.py -v`
Expected: 5 passing tests.

- [ ] **Step 5: Wire the helpers into the eval loop**

In `tests/pageindex_eval/eval_runner.py`:

(a) Update `run_pageindex_rag` (currently lines 93-126) so it also returns the tool trace. Change the return dict to include `tool_trace`:

```python
    return {
        "answer": answer,
        "fetched_pages": sorted(set(fetched_pages)),
        "latency_ms": int((time.time() - t0) * 1000),
        "tool_trace": tool_trace if 'tool_trace' in dir() else [],
    }
```

Replace the inner body to keep `tool_trace` in scope from the call:

```python
def run_pageindex_rag(
    conn,
    question: str,
    course_id: int,
    material_ids: list[int],
    openai_key: str,
) -> dict:
    from llm import DEFAULT_AGENTIC_MODEL, run_agent_pageindex

    t0 = time.time()
    fetched_pages = []
    tool_trace = []
    try:
        answer, _grounding_refs, tool_trace, _, _, _, _ = run_agent_pageindex(
            conn=conn,
            user_message=question,
            model=DEFAULT_AGENTIC_MODEL,
            api_key=openai_key,
            chat_id=None,
            course_id=course_id,
            context_material_ids=material_ids,
        )
        for trace in tool_trace:
            if trace.get("tool") == "get_page_content":
                from services.query.pageindex_retrieval import _parse_pages

                pages_spec = trace.get("args", {}).get("pages", "")
                fetched_pages.extend(_parse_pages(pages_spec))
    except Exception as exc:
        answer = f"ERROR: {exc}"
    return {
        "answer": answer,
        "fetched_pages": sorted(set(fetched_pages)),
        "latency_ms": int((time.time() - t0) * 1000),
        "tool_trace": tool_trace,
    }
```

(b) In `main()`, when building the per-test-case `result` dict (~line 170), add `iteration_count` under `pageindex`:

```python
            "pageindex": {
                "page_hit_rate": pageindex_hit,
                "answer_score": pageindex_score,
                "latency_ms": pageindex_result["latency_ms"],
                "iteration_count": _iteration_count(pageindex_result["tool_trace"]),
            },
```

(c) Extend the summary block at the bottom of `main()` (~line 207). Replace the existing `Summary:` block with:

```python
    vector_latencies = [r["vector"]["latency_ms"] for r in results]
    pageindex_latencies = [r["pageindex"]["latency_ms"] for r in results]
    avg_iterations = sum(r["pageindex"]["iteration_count"] for r in results) / len(results)
    vec_pct = _latency_percentiles(vector_latencies)
    pi_pct = _latency_percentiles(pageindex_latencies)

    print("\nSummary:")
    print(
        f"  Vector    avg hit={avg_vector_hit:.2f}  avg score={avg_vector_score:.2f}  "
        f"p50={vec_pct['p50']}ms p95={vec_pct['p95']}ms max={vec_pct['max']}ms"
    )
    print(
        f"  PageIndex avg hit={avg_pageindex_hit:.2f}  avg score={avg_pageindex_score:.2f}  "
        f"p50={pi_pct['p50']}ms p95={pi_pct['p95']}ms max={pi_pct['max']}ms  "
        f"avg_iters={avg_iterations:.2f}"
    )
```

- [ ] **Step 6: Smoke-check the runner still imports**

Run: `cd /Users/shubhan/OneShotCourseMate && python -c "import sys; sys.path.insert(0, 'api'); sys.path.insert(0, 'tests/pageindex_eval'); import eval_runner; print(eval_runner._iteration_count([]))"`
Expected: prints `0` with no exceptions.

- [ ] **Step 7: Commit**

```bash
git add tests/pageindex_eval/eval_runner.py tests/pageindex_eval/test_eval_runner_helpers.py
git commit -m "feat(eval): log iteration_count and report p50/p95/max latency"
```

---

## Task 4: Eval runner — `--concurrency` flag

**Files:**
- Modify: `tests/pageindex_eval/eval_runner.py`

- [ ] **Step 1: Add the flag and refactor the per-case loop**

In `tests/pageindex_eval/eval_runner.py`:

(a) Add the flag to the argparse block in `main()` (currently ~line 130):

```python
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of test cases to run in parallel (each opens its own DB connection). Default 1.",
    )
```

(b) Extract the per-test-case work into a helper, placed above `main()`:

```python
def _run_one_test_case(
    db_url: str,
    tc: dict,
    course_id: int,
    material_ids: list[int],
    openai_key: str,
) -> dict:
    import psycopg

    conn = psycopg.connect(db_url, row_factory=psycopg.rows.dict_row)
    try:
        vector_result = run_vector_rag(conn, tc["question"], course_id, material_ids)
        pageindex_result = run_pageindex_rag(
            conn, tc["question"], course_id, material_ids, openai_key
        )
        vector_hit = _page_hit_rate(tc["expected_pages"], vector_result["fetched_pages"])
        pageindex_hit = _page_hit_rate(
            tc["expected_pages"], pageindex_result["fetched_pages"]
        )
        vector_score = _llm_judge(
            tc["question"], vector_result["answer"], tc["judge_criteria"], openai_key
        )
        pageindex_score = _llm_judge(
            tc["question"],
            pageindex_result["answer"],
            tc["judge_criteria"],
            openai_key,
        )
        return {
            "id": tc["id"],
            "difficulty": tc["difficulty"],
            "vector": {
                "page_hit_rate": vector_hit,
                "answer_score": vector_score,
                "latency_ms": vector_result["latency_ms"],
            },
            "pageindex": {
                "page_hit_rate": pageindex_hit,
                "answer_score": pageindex_score,
                "latency_ms": pageindex_result["latency_ms"],
                "iteration_count": _iteration_count(pageindex_result["tool_trace"]),
            },
            "winner": (
                "pageindex"
                if pageindex_score > vector_score
                else ("vector" if vector_score > pageindex_score else "tie")
            ),
        }
    finally:
        conn.close()
```

(c) Replace the existing test-case loop in `main()` (currently ~lines 146-198) with:

```python
    import psycopg
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if args.concurrency <= 1:
        results = []
        for tc in test_cases:
            print(f"\nRunning {tc['id']}: {tc['question'][:60]}...")
            result = _run_one_test_case(
                args.db_url, tc, args.course_id, material_ids, args.openai_key
            )
            results.append(result)
            print(
                f"  Vector:    hit={result['vector']['page_hit_rate']:.2f} "
                f"score={result['vector']['answer_score']}/3 "
                f"({result['vector']['latency_ms']}ms)"
            )
            print(
                f"  PageIndex: hit={result['pageindex']['page_hit_rate']:.2f} "
                f"score={result['pageindex']['answer_score']}/3 "
                f"({result['pageindex']['latency_ms']}ms) "
                f"iters={result['pageindex']['iteration_count']}"
            )
    else:
        results = []
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = {
                ex.submit(
                    _run_one_test_case,
                    args.db_url,
                    tc,
                    args.course_id,
                    material_ids,
                    args.openai_key,
                ): tc["id"]
                for tc in test_cases
            }
            for fut in as_completed(futures):
                result = fut.result()
                results.append(result)
                print(
                    f"  [{result['id']}] vec score={result['vector']['answer_score']}/3 "
                    f"({result['vector']['latency_ms']}ms)  "
                    f"pi score={result['pageindex']['answer_score']}/3 "
                    f"({result['pageindex']['latency_ms']}ms) "
                    f"iters={result['pageindex']['iteration_count']}"
                )
        results.sort(key=lambda r: r["id"])
```

(d) Remove the now-orphaned `conn = psycopg.connect(...)` / `conn.close()` lines at the top/bottom of `main()` — they've been pushed into `_run_one_test_case`.

- [ ] **Step 2: Smoke-test the argparse + serial path still works**

Run: `cd /Users/shubhan/OneShotCourseMate && python tests/pageindex_eval/eval_runner.py --help`
Expected: prints help, includes `--concurrency` with default `1`.

- [ ] **Step 3: Re-run the existing helper tests to confirm no regression**

Run: `cd /Users/shubhan/OneShotCourseMate && pytest tests/pageindex_eval/test_eval_runner_helpers.py -v`
Expected: 5 passing tests.

- [ ] **Step 4: Commit**

```bash
git add tests/pageindex_eval/eval_runner.py
git commit -m "feat(eval): add --concurrency flag for parallel test-case execution"
```

---

## Task 5: Validate against success criteria

**Files:** none modified. This task runs the eval suite end-to-end to confirm the change meets the spec's success criteria.

- [ ] **Step 1: Run the eval suite serially**

Use the same invocation as the baseline run (course 7, materials 624-637). Set `OPENAI_API_KEY` and `DATABASE_URL` from your environment.

```bash
cd /Users/shubhan/OneShotCourseMate
PYTHONPATH=api python tests/pageindex_eval/eval_runner.py \
  --db-url "$DATABASE_URL" \
  --openai-key "$OPENAI_API_KEY" \
  --course-id 7 \
  --material-ids 624,625,626,627,628,629,630,631,632,633,634,635,636,637
```

Expected output: a `Summary:` block with `PageIndex p50=<ms> p95=<ms> max=<ms> avg_iters=<n>` plus an average score.

- [ ] **Step 2: Verify success criteria from the spec**

Check each:
1. PageIndex `avg score ≥ 2.85` — quality preserved.
2. PageIndex `p50 ≤ 5000ms`.
3. PageIndex `p95 ≤ 15000ms`.
4. PageIndex `avg_iters ≤ 2.5` (was ~3-4 before).

If all four pass → ship.
If (1) fails → revert (`git revert` the commits from Tasks 1-4) and re-plan. The preload likely confused the model on some question type; inspect the failed cases in `results_<date>.jsonl` for clues.
If (2)-(4) fail but (1) passes → the change is still a win; capture the actual numbers and decide whether to layer Approach B (preload structures) per the spec follow-ups.

- [ ] **Step 3: Inspect the new JSONL output**

Open `tests/pageindex_eval/results_<today>.jsonl` and verify each line has `pageindex.iteration_count` populated.

- [ ] **Step 4: Spot-check with `--concurrency 4`**

Run again with concurrency to confirm the parallel path produces the same average score (within noise — judge has temperature 0, so should be identical):

```bash
PYTHONPATH=api python tests/pageindex_eval/eval_runner.py \
  --db-url "$DATABASE_URL" \
  --openai-key "$OPENAI_API_KEY" \
  --course-id 7 \
  --material-ids 624,625,626,627,628,629,630,631,632,633,634,635,636,637 \
  --concurrency 4
```

Expected: average score within ±0.05 of the serial run; wall-clock noticeably shorter.

- [ ] **Step 5: Commit the new results file**

```bash
git add tests/pageindex_eval/results_*.jsonl
git commit -m "test(pageindex): record post-preload eval results"
```

---

## Self-Review

**Spec coverage:**
- Change 1 (preload routing index, drop tool) → Tasks 1 + 2 ✓
- Change 2 (eval instrumentation: --concurrency, iteration_count, p50/p95/max) → Tasks 3 + 4 ✓
- Success criteria validation → Task 5 ✓
- Out-of-scope items (model swaps, structure preload, vector RAG fix, prompt caching) → correctly excluded ✓

**Placeholder scan:** none — every code step contains real code, every command is concrete.

**Type/name consistency:**
- `_format_routing_index_block` consistent across Tasks 1 and 2 ✓
- `_iteration_count` / `_latency_percentiles` consistent across Tasks 3 and 4 ✓
- `tool_trace` field added to `run_pageindex_rag` return in Task 3 and consumed in Task 4 ✓
- Result dict shape: `pageindex.iteration_count` added in Task 3 and re-asserted in `_run_one_test_case` (Task 4) ✓
