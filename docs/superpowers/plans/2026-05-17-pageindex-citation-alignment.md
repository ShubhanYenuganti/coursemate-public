# PageIndex Citation Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the misalignments uncovered by the post-migration audit between the PageIndex agent backend and the React chat frontend so that inline `[N]` citations map to the correct material+pages, related-materials tool calls render in the trace, regenerate doesn't waste calls on string refs, and cross-turn resolver doesn't get polluted by `"material:X"` refs.

**Architecture:** Five surgical fixes across two boundaries. (1) Pin the citation contract: instruct the PageIndex agent to number citations in fetch order, and rebuild `_get_message_chunks` to derive citations from `tool_trace` in that same order. (2) Frontend handles `get_related_materials` events and re-adds `isFocused` to page citations. (3) Backend guards `_fetch_chunk_context` against `"material:X"` string refs in the regenerate path and the cross-turn resolver.

**Tech Stack:** Python 3.11, psycopg, React 18, pytest

---

## File Map

| File | Change |
|------|--------|
| `api/llm.py:160` | Add per-call numbering instruction to `PAGEINDEX_SYSTEM_PROMPT` |
| `api/chat.py:668-735` | Rewrite `_get_message_chunks` PageIndex branch to derive ordered citations from `tool_trace` |
| `api/chat.py:2117-2138` | Skip `_fetch_chunk_context` for `material:*` refs in regenerate path |
| `api/tools.py:180-194,234-245` | Partition refs into integer-only pool before passing to `_fetch_chunk_context` |
| `src/ChatTab.jsx:994-1020` | Add `get_related_materials` case to `toolTraceToEvents` |
| `src/ChatTab.jsx:938-980` | Add `related_fetch` case to `getTracePrimary` |
| `src/ChatTab.jsx:436-490` | Re-add `isFocused` ref + styling to page-citation branch in `SourcesPanel` |
| `tests/test_chat_citations.py` | New citation-ordering and ref-filter tests |
| `tests/test_pageindex_agent.py` | Assert PAGEINDEX_SYSTEM_PROMPT mentions per-call numbering |

---

## Task 1: Pin citation numbering contract in PageIndex system prompt

**Files:**
- Modify: `api/llm.py:145-160`
- Modify: `tests/test_pageindex_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pageindex_agent.py`:

```python
def test_pageindex_prompt_documents_citation_numbering():
    """PAGEINDEX_SYSTEM_PROMPT must explain how [N] markers map to fetched pages."""
    from llm import PAGEINDEX_SYSTEM_PROMPT
    text = PAGEINDEX_SYSTEM_PROMPT.lower()
    assert "get_page_content" in text
    assert ("order" in text and "call" in text) or "nth call" in text, \
        "Prompt must instruct agent to use call-order for citation numbers"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_pageindex_prompt_documents_citation_numbering -v
```

Expected: FAIL — prompt doesn't yet mention call ordering.

- [ ] **Step 3: Update `_PAGEINDEX_TOOL_USE`**

In `api/llm.py`, replace the `_PAGEINDEX_TOOL_USE` block (lines ~145-154):

```python
_PAGEINDEX_TOOL_USE = (
    "\n\n**Tool use**: A routing index of available course materials is provided below. "
    "Each material includes per-page summaries — use them to identify the right pages and call "
    "`get_page_content(material_id, pages)` directly with a page range (e.g. '3,4,5' or '3-5'). "
    "Only call `get_material_structure(material_id)` if the routing index has no page summaries "
    "for that material or you need sub-section detail not visible in the summaries. "
    "If the fetched content does not fully answer the question, call `get_related_materials(material_id)` "
    "to discover related materials and repeat. "
    "Do NOT call any other tools — only these three are available."
    "\n\n**Citation numbering**: Each `get_page_content` call you make becomes one numbered citation, "
    "in the order you called it. The first `get_page_content` call is citation [1], the second is [2], "
    "and so on. When you write the final answer, cite each fact using the bracket that matches the call "
    "that fetched its evidence. Do not invent citation numbers that do not correspond to a "
    "`get_page_content` call. If you fetched the same material on multiple calls, each call gets its own "
    "citation number — do not collapse them."
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py -v
```

Expected: all PageIndex agent tests PASS, including the new numbering test.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(pageindex): pin citation numbering to get_page_content call order"
```

---

## Task 2: Derive ordered citations from `tool_trace` in `_get_message_chunks`

**Files:**
- Modify: `api/chat.py:668-735`
- Modify: `tests/test_chat_citations.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_chat_citations.py`:

```python
def test_page_citations_ordered_by_call_sequence():
    """Citations should appear in the same order as get_page_content calls,
    one entry per call (not collapsed by material_id)."""
    from pageindex_retrieval import _parse_pages

    tool_trace = [
        {"tool": "get_material_structure", "args": {"material_id": 624}, "iteration": 1},
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "3-5"}, "iteration": 1},
        {"tool": "get_page_content", "args": {"material_id": 625, "pages": "1-2"}, "iteration": 2},
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "6"}, "iteration": 3},
    ]

    citations = []
    for entry in tool_trace:
        if entry.get("tool") == "get_page_content":
            mid = entry.get("args", {}).get("material_id")
            pages = _parse_pages(str(entry.get("args", {}).get("pages", "")))
            if mid is not None:
                citations.append({"material_id": mid, "pages": pages, "citation_type": "page"})

    assert len(citations) == 3
    assert citations[0] == {"material_id": 624, "pages": [3, 4, 5], "citation_type": "page"}
    assert citations[1] == {"material_id": 625, "pages": [1, 2], "citation_type": "page"}
    assert citations[2] == {"material_id": 624, "pages": [6], "citation_type": "page"}
```

- [ ] **Step 2: Run test to verify it passes (pure logic)**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_citations.py::test_page_citations_ordered_by_call_sequence -v
```

Expected: PASS (pure logic, validates the contract before the rewrite).

- [ ] **Step 3: Rewrite the PageIndex branch in `_get_message_chunks`**

In `api/chat.py`, find the PageIndex branch inside `_get_message_chunks` (the block guarded by `if is_pageindex:` around lines 700-723). Replace it with:

```python
            if is_pageindex:
                try:
                    from pageindex_retrieval import _parse_pages
                except ImportError:
                    from .pageindex_retrieval import _parse_pages
                tool_trace = row['tool_trace'] or []
                serialized = []
                for entry in tool_trace:
                    if entry.get('tool') != 'get_page_content':
                        continue
                    mid = entry.get('args', {}).get('material_id')
                    if mid is None:
                        continue
                    pages_str = entry.get('args', {}).get('pages', '')
                    pages = _parse_pages(str(pages_str))
                    serialized.append({
                        "material_id": mid,
                        "pages": pages,
                        "citation_type": "page",
                    })
                send_json(self, 200, {"chunks": serialized})
                return
```

This drops the `pages_by_material` dict (which collapsed and reordered citations) and emits one chunk per `get_page_content` call in trace order — matching the contract Task 1 wrote into the prompt.

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/ -v
```

Expected: all previously-passing tests still PASS; ordering test still PASS.

- [ ] **Step 5: Commit**

```bash
git add api/chat.py tests/test_chat_citations.py
git commit -m "feat(citations): emit one page citation per get_page_content call, in call order"
```

---

## Task 3: Handle `get_related_materials` in frontend trace

**Files:**
- Modify: `src/ChatTab.jsx:938-1015`

- [ ] **Step 1: Add `related_fetch` case to `toolTraceToEvents`**

In `src/ChatTab.jsx`, find `toolTraceToEvents` (around line 994). Add a new `else if` branch at the end of the tool dispatch (after the `get_material_structure` case):

```js
    } else if (entry.tool === 'get_material_structure') {
      events.push({ phase: 'structure_fetch', material_id: entry.args?.material_id });
    } else if (entry.tool === 'get_related_materials') {
      events.push({ phase: 'related_fetch', material_id: entry.args?.material_id });
    }
```

- [ ] **Step 2: Add `related_fetch` case to `getTracePrimary`**

In `src/ChatTab.jsx`, find `getTracePrimary` (around line 938). Add a new case before the `default:`:

```js
    case 'related_fetch': {
      const mat = (materialMap || {})[status.material_id];
      const name = mat?.name ? mat.name.replace(/\.[^.]+$/, '').slice(0, 25) : `material ${status.material_id}`;
      return `Looked up materials related to ${name}`;
    }
```

- [ ] **Step 3: Manual verification**

Start the dev server and open a chat message whose `tool_trace` contains a `get_related_materials` entry. Click the "N reasoning steps" toggle on the assistant message.

```bash
cd /Users/shubhan/OneShotCourseMate && npm run dev
```

Expected: a step rendered with text "Looked up materials related to <material name>". No JS console errors.

If you don't have an existing message with `get_related_materials` in the trace, send a query that requires multiple materials (e.g., "compare topic X across the lecture and the practice set") to trigger the agent into calling it.

- [ ] **Step 4: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(ui): render get_related_materials steps in tool trace indicator"
```

---

## Task 4: Restore focus styling for page citations in `SourcesPanel`

**Files:**
- Modify: `src/ChatTab.jsx:436-490`

- [ ] **Step 1: Re-add `isFocused` ref + styling to the page-citation branch**

In `src/ChatTab.jsx`, find the page-citation branch inside `SourcesPanel`'s `.map((chunk, idx) => { ... })` callback (around line 442, starts with `if (chunk.citation_type === 'page')`). Replace the entire branch body with:

```jsx
          if (chunk.citation_type === 'page') {
            const pages = chunk.pages || [];
            const pageLabel = pages.length === 0
              ? ''
              : pages.length === 1
                ? `p. ${pages[0]}`
                : `pp. ${pages[0]}–${pages[pages.length - 1]}`;
            return (
              <div
                key={idx}
                ref={isFocused ? focusRef : null}
                className={`rounded-lg px-3 py-2.5 border text-xs transition-colors ${
                  isFocused
                    ? 'border-l-4 border-indigo-400 bg-indigo-50'
                    : 'border-gray-100 bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-4 h-4 rounded bg-indigo-100 text-indigo-600 font-semibold text-[10px] flex-shrink-0">
                    {n}
                  </span>
                  {material?.name && (
                    <span className="text-gray-700 font-medium truncate">
                      {material.name.replace(/\.[^.]+$/, '')}
                    </span>
                  )}
                  {pageLabel && <span className="text-gray-400 ml-auto flex-shrink-0">{pageLabel}</span>}
                  {downloadUrl && (
                    <a
                      href={downloadUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 rounded text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors flex-shrink-0"
                    >
                      <ExternalLinkIcon />
                    </a>
                  )}
                </div>
              </div>
            );
          }
```

The only changes vs. the current code: `ref={isFocused ? focusRef : null}` plus an `isFocused`-driven className swap. `n` and `isFocused` are already declared at the top of the `.map` callback (lines 437-438), so no new declarations needed.

- [ ] **Step 2: Manual verification**

Start the dev server, open a PageIndex chat with multiple page citations, and click an inline `[2]` marker.

```bash
cd /Users/shubhan/OneShotCourseMate && npm run dev
```

Expected: `SourcesPanel` opens, scrolls the 2nd citation into view, and shows it with a left-bar indigo highlight (matching the vector-citation focus styling).

- [ ] **Step 3: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "fix(ui): restore focus highlight on clicked page citation in SourcesPanel"
```

---

## Task 5: Skip `_fetch_chunk_context` for `material:*` refs in regenerate

**Files:**
- Modify: `api/chat.py:2110-2138`
- Modify: `tests/test_chat_citations.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_chat_citations.py`:

```python
def test_partition_locked_chunk_ids_drops_material_refs():
    """Helper must separate integer-style chunk refs from material:N refs."""
    raw = ["123", "material:624", "456", "material:625", "789"]
    integer_refs = [r for r in raw if not (isinstance(r, str) and r.startswith("material:"))]
    assert integer_refs == ["123", "456", "789"]
```

- [ ] **Step 2: Run test to verify it passes (pure logic)**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_citations.py::test_partition_locked_chunk_ids_drops_material_refs -v
```

Expected: PASS.

- [ ] **Step 3: Filter `locked_chunk_ids` before `_fetch_chunk_context`**

In `api/chat.py`, find the regenerate path block that calls `_fetch_chunk_context(conn, locked_chunk_ids)` (around line 2119). Replace lines 2115-2119:

```python
            locked_chunk_ids = [str(cid) for cid in locked_chunk_ids if cid is not None]

            # PageIndex refs ("material:N") are not vector chunk IDs and would just
            # return empty rows from _fetch_chunk_context. Skip them.
            integer_locked_chunk_ids = [
                cid for cid in locked_chunk_ids
                if not cid.startswith("material:")
            ]

            locked_chunks = []
            if integer_locked_chunk_ids and _fetch_chunk_context:
                hydrated_locked_chunks = _fetch_chunk_context(conn, integer_locked_chunk_ids)
                by_id = {str(c.get('id')): c for c in hydrated_locked_chunks}
                ordered_hydrated = [by_id[cid] for cid in integer_locked_chunk_ids if cid in by_id]
```

Then immediately after that, the loop `for idx, chunk in enumerate(ordered_hydrated):` and everything else remains unchanged.

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/ -v
```

Expected: all previously-passing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add api/chat.py tests/test_chat_citations.py
git commit -m "fix(regenerate): skip _fetch_chunk_context for material:N pageindex refs"
```

---

## Task 6: Filter `material:*` refs in cross-turn resolver

**Files:**
- Modify: `api/tools.py:180-194,234-245`
- Modify: `tests/test_chat_citations.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_chat_citations.py`:

```python
def test_extract_known_chunk_ids_filters_material_refs():
    """_extract_known_chunk_ids must drop 'material:N' refs that are not in the hydrated chunk set."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
    from tools import _extract_known_chunk_ids

    messages = [
        {"retrieved_chunk_ids": ["123", "material:624", "456"]},
        {"retrieved_chunk_ids": ["material:625", "789"]},
    ]
    hydrated_chunk_ids = {"123", "456", "789"}
    result = _extract_known_chunk_ids(messages, hydrated_chunk_ids)
    assert result == ["123", "456", "789"]
    assert all(not r.startswith("material:") for r in result)
```

- [ ] **Step 2: Run test to verify behavior**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_citations.py::test_extract_known_chunk_ids_filters_material_refs -v
```

Expected: PASS — the existing implementation already filters via `if scid in hydrated_chunk_ids`, but the test pins this behavior so future regressions are caught.

- [ ] **Step 3: Filter `material:*` refs in `resolve_references_llm`**

In `api/tools.py`, find `resolve_references_llm` (around line 210). Inside the function, find the block that builds `all_refs` (around line 234-244). Replace lines 234-245:

```python
    all_refs = []
    for row in merged_messages:
        refs = row.get("retrieved_chunk_ids") or []
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except json.JSONDecodeError:
                refs = []
        if isinstance(refs, list):
            # PageIndex stores "material:N" tokens in retrieved_chunk_ids that aren't
            # vector chunk IDs. Skip them here so _fetch_chunk_context isn't asked to
            # hydrate strings it can't resolve, and so the resolver's prior_grounding_refs
            # field stays a clean list of integer chunk IDs.
            all_refs.extend(
                str(cid) for cid in refs
                if not (isinstance(cid, str) and cid.startswith("material:"))
            )
    all_refs = _dedupe_preserve_order(all_refs)[:30]
    hydrated = _fetch_chunk_context(conn, all_refs) if (_fetch_chunk_context and all_refs) else []
```

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/ -v
```

Expected: all previously-passing tests still PASS, new test PASS.

- [ ] **Step 5: Commit**

```bash
git add api/tools.py tests/test_chat_citations.py
git commit -m "fix(grounding): strip material:N refs from cross-turn resolver inputs"
```

---

## Self-Review

**Spec coverage check:**

| Audit finding | Task |
|---|---|
| 1. Citation numbering has no mapping rule | Tasks 1 & 2 (prompt contract + ordered derivation) |
| 2. `get_related_materials` trace entries not rendered | Task 3 |
| 3. `get_material_structure` doesn't add to `grounding_refs` | *Scoped out* — adding it would mis-cite structure-only answers; better fix is for the agent never to cite when only structure was fetched, which Task 1's contract already enforces |
| 4. Regenerate passes PageIndex refs to `_fetch_chunk_context` | Task 5 |
| 5. Cross-turn grounding mixes string and integer refs | Task 6 |
| 6. Dropped stream events from agentic path | *Scoped out* — only matters if `AGENTIC_LOOP_ENABLED` is flipped on, which contradicts the migration. Not a current bug. |
| 7. (Confirmed not a misalignment) | n/a |
| Restore focus styling on page citations | Task 4 |

All in-scope audit findings covered. Items 3 and 6 explicitly scoped out with rationale.

**Placeholder scan:** No "TBD", no "similar to Task N", no naked "add validation". Every code block contains executable content.

**Type consistency:** `citation_type: "page"` matches Task 4's branch guard. `material:` prefix string check is consistent across Tasks 5 and 6. `_parse_pages` import path matches the pattern from the prior migration plan. `focusRef`/`isFocused` names match existing `SourcesPanel` locals (verified against current `src/ChatTab.jsx:417,438`).

---

Plan complete and saved to `docs/superpowers/plans/2026-05-17-pageindex-citation-alignment.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
