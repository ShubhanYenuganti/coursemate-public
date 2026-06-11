# PageIndex Client Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PageIndex the default retrieval path, eliminate wasted vector-RAG Lambda calls, fix the eval runner, remove the streaming status bubble, and replace chunk-based citations with page-based citations.

**Architecture:** The flag default flip in `llm.py` makes PageIndex win by default; `chat.py` gates `retrieve_chunks` behind the same flag check to avoid the now-useless embed Lambda call. Citation data is derived from `tool_trace` (which pages were fetched) rather than `retrieved_chunk_ids` (vector chunk IDs). The frontend removes the agentic-loop status bubble and adapts the sources panel to display material + page range.

**Tech Stack:** Python 3.11, psycopg, React 18, pytest

---

## File Map

| File | Change |
|------|--------|
| `api/llm.py:1735` | Flip `default=False` → `default=True` |
| `api/chat.py:214–219` | Add `_is_pageindex_active()` helper |
| `api/chat.py:915,1153,1364,2107` | Gate `retrieve_chunks` calls |
| `api/chat.py:661–706` | Update `_get_message_chunks` for page citations |
| `tests/pageindex_eval/eval_runner.py:89–92,139` | Fix two broken imports |
| `src/ChatTab.jsx:993–1052` | Update `toolTraceToEvents` + `getTracePrimary`/`getTraceSecondary` |
| `src/ChatTab.jsx:416–415` | Update `SourcesPanel` to handle `citation_type: "page"` |
| `src/ChatTab.jsx:1054–1092` | Remove `StreamingHistoryBubble` component |
| `src/ChatTab.jsx:1239` | Remove `streamingHistory` state |
| `src/ChatTab.jsx:1743–1777,1870,1979–1998,2033,2121–2181,2321–2403,2862` | Remove all `setStreamingHistory` calls + `PHASE_EVENTS` + render site |
| `tests/test_chat_citations.py` | New: unit tests for citation detection logic |

---

## Task 1: Flip PAGEINDEX_RETRIEVAL_ENABLED default

**Files:**
- Modify: `api/llm.py:1735`

- [ ] **Step 1: Edit the flag default**

In `api/llm.py` at line 1735, change:

```python
use_pageindex = _is_enabled("PAGEINDEX_RETRIEVAL_ENABLED", default=False)
```

to:

```python
use_pageindex = _is_enabled("PAGEINDEX_RETRIEVAL_ENABLED", default=True)
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py -v
```

Expected: all 4 tests PASS (they mock out the HTTP call so the flag doesn't matter to them directly).

- [ ] **Step 3: Commit**

```bash
git add api/llm.py
git commit -m "feat(pageindex): flip PAGEINDEX_RETRIEVAL_ENABLED default to True"
```

---

## Task 2: Add `_is_pageindex_active()` and gate `retrieve_chunks`

**Files:**
- Modify: `api/chat.py`
- Create: `tests/test_chat_citations.py`

- [ ] **Step 1: Write a failing test for the helper**

Create `tests/test_chat_citations.py`:

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_is_pageindex_active_default():
    """Unset env var → active (default True)."""
    os.environ.pop('PAGEINDEX_RETRIEVAL_ENABLED', None)
    from chat import _is_pageindex_active
    assert _is_pageindex_active() is True


def test_is_pageindex_active_false():
    os.environ['PAGEINDEX_RETRIEVAL_ENABLED'] = 'false'
    # Re-import to pick up env change (function reads os.environ at call time)
    from chat import _is_pageindex_active
    assert _is_pageindex_active() is False
    os.environ.pop('PAGEINDEX_RETRIEVAL_ENABLED', None)


def test_is_pageindex_active_true():
    os.environ['PAGEINDEX_RETRIEVAL_ENABLED'] = 'true'
    from chat import _is_pageindex_active
    assert _is_pageindex_active() is True
    os.environ.pop('PAGEINDEX_RETRIEVAL_ENABLED', None)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_citations.py::test_is_pageindex_active_default -v
```

Expected: FAIL — `ImportError: cannot import name '_is_pageindex_active' from 'chat'`

- [ ] **Step 3: Add `_is_pageindex_active()` to `chat.py`**

In `api/chat.py`, after the existing `_is_enabled` function (around line 219), add:

```python
def _is_pageindex_active() -> bool:
    return os.environ.get("PAGEINDEX_RETRIEVAL_ENABLED", "true").lower() != "false"
```

- [ ] **Step 4: Run tests to verify helper passes**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_citations.py -v -k "is_pageindex"
```

Expected: 3 tests PASS.

- [ ] **Step 5: Gate the four `retrieve_chunks` call sites**

**Site 1 — `_send_message` (line ~915):**

```python
# Before
chunks = retrieve_chunks(conn, content, context_material_ids)

# After
chunks = retrieve_chunks(conn, content, context_material_ids) if not _is_pageindex_active() else []
```

**Site 2 — `_stream_send_message` (line ~1153):**

```python
# Before
chunks = retrieve_chunks(
    conn, content or "", context_material_ids,
    image_s3_keys=image_s3_keys or [],
    current_message_id=user_message['id'],
)

# After
chunks = retrieve_chunks(
    conn, content or "", context_material_ids,
    image_s3_keys=image_s3_keys or [],
    current_message_id=user_message['id'],
) if not _is_pageindex_active() else []
```

**Site 3 — `_edit_message` (line ~1364):**

```python
# Before
chunks = retrieve_chunks(conn, content, context_material_ids)

# After
chunks = retrieve_chunks(conn, content, context_material_ids) if not _is_pageindex_active() else []
```

**Site 4 — `_regenerate_message` (line ~2107):**

```python
# Before
chunks = locked_chunks or retrieve_chunks(conn, user_msg['content'], context_material_ids)

# After
chunks = locked_chunks or (retrieve_chunks(conn, user_msg['content'], context_material_ids) if not _is_pageindex_active() else [])
```

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/ -v
```

Expected: all existing tests PASS, 3 new tests PASS.

- [ ] **Step 7: Commit**

```bash
git add api/chat.py tests/test_chat_citations.py
git commit -m "feat(pageindex): skip retrieve_chunks when PageIndex is active, add _is_pageindex_active helper"
```

---

## Task 3: Fix eval_runner broken imports

**Files:**
- Modify: `tests/pageindex_eval/eval_runner.py:89–92,139`

- [ ] **Step 1: Fix `retrieve_context` → `retrieve_chunks` in `run_vector_rag`**

In `tests/pageindex_eval/eval_runner.py`, replace the `run_vector_rag` function body (lines ~89–92):

```python
# Before
from rag import retrieve_context
from llm import synthesize

chunks = retrieve_context(conn, question, material_ids=material_ids)

# After
from rag import retrieve_chunks
from llm import synthesize

chunks = retrieve_chunks(conn, question, material_ids)
```

- [ ] **Step 2: Fix `_parse_pages` import path in `run_pageindex_rag`**

In the same file, replace line ~139:

```python
# Before
from services.query.pageindex_retrieval import _parse_pages

# After
from pageindex_retrieval import _parse_pages
```

- [ ] **Step 3: Verify import-level correctness**

```bash
cd /Users/shubhan/OneShotCourseMate && python -c "
import sys, os
sys.path.insert(0, 'api')
# Verify the imports resolve without errors
from rag import retrieve_chunks
from pageindex_retrieval import _parse_pages
print('imports OK')
"
```

Expected output: `imports OK`

- [ ] **Step 4: Commit**

```bash
git add tests/pageindex_eval/eval_runner.py
git commit -m "fix(eval): replace broken retrieve_context and _parse_pages import paths in eval_runner"
```

---

## Task 4: Page-based citations in `_get_message_chunks`

**Files:**
- Modify: `api/chat.py:661–706`
- Modify: `tests/test_chat_citations.py`

- [ ] **Step 1: Write failing tests for citation detection**

Add to `tests/test_chat_citations.py`:

```python
def _make_tool_trace(entries):
    import json
    return json.dumps(entries)


def test_pageindex_citation_detection():
    """retrieved_chunk_ids with 'material:X' entries → PageIndex path detected."""
    chunk_ids = ['material:624', 'material:625']
    is_pageindex = any(isinstance(cid, str) and cid.startswith('material:') for cid in chunk_ids)
    assert is_pageindex is True


def test_vector_citation_not_detected():
    """Integer chunk IDs → vector path, not PageIndex."""
    chunk_ids = [101, 202, 303]
    is_pageindex = any(isinstance(cid, str) and cid.startswith('material:') for cid in chunk_ids)
    assert is_pageindex is False


def test_page_citations_derived_from_tool_trace():
    """Tool trace get_page_content entries are grouped into page citations."""
    import json
    from pageindex_retrieval import _parse_pages

    tool_trace = [
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "3,4,5"}, "iteration": 1},
        {"tool": "get_material_structure", "args": {"material_id": 624}, "iteration": 1},
        {"tool": "get_page_content", "args": {"material_id": 625, "pages": "1-2"}, "iteration": 2},
        {"tool": "get_page_content", "args": {"material_id": 624, "pages": "6"}, "iteration": 3},
    ]

    pages_by_material = {}
    for entry in tool_trace:
        if entry.get("tool") == "get_page_content":
            mid = entry.get("args", {}).get("material_id")
            pages_str = entry.get("args", {}).get("pages", "")
            if mid is not None:
                pages = _parse_pages(str(pages_str))
                existing = pages_by_material.get(mid, [])
                pages_by_material[mid] = sorted(set(existing + pages))

    assert pages_by_material[624] == [3, 4, 5, 6]
    assert pages_by_material[625] == [1, 2]
```

- [ ] **Step 2: Run tests to verify they pass (pure logic, no DB)**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_citations.py -v -k "citation or page"
```

Expected: 3 tests PASS (pure logic, no DB needed).

- [ ] **Step 3: Update `_get_message_chunks` in `chat.py`**

Replace the `_get_message_chunks` method (lines ~661–706) with:

```python
def _get_message_chunks(self, user, params):
    message_id_raw = params.get('message_id', [None])[0]
    if not message_id_raw or not message_id_raw.isdigit():
        send_json(self, 400, {"error": "message_id query parameter is required"})
        return
    message_id = int(message_id_raw)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cm.retrieved_chunk_ids, cm.tool_trace, c.user_id
            FROM chat_messages cm
            JOIN chats c ON c.id = cm.chat_id
            WHERE cm.id = %s AND cm.is_deleted = FALSE
        """, (message_id,))
        row = cursor.fetchone()
        cursor.close()

        if not row:
            send_json(self, 404, {"error": "Message not found"})
            return
        if row['user_id'] != user['id']:
            send_json(self, 403, {"error": "Access denied"})
            return

        chunk_ids = row['retrieved_chunk_ids'] or []
        if not chunk_ids:
            send_json(self, 200, {"chunks": []})
            return

        is_pageindex = any(isinstance(cid, str) and cid.startswith('material:') for cid in chunk_ids)

        if is_pageindex:
            try:
                from pageindex_retrieval import _parse_pages
            except ImportError:
                from .pageindex_retrieval import _parse_pages
            tool_trace = row['tool_trace'] or []
            pages_by_material = {}
            for entry in tool_trace:
                if entry.get('tool') == 'get_page_content':
                    mid = entry.get('args', {}).get('material_id')
                    pages_str = entry.get('args', {}).get('pages', '')
                    if mid is not None:
                        pages = _parse_pages(str(pages_str))
                        existing = pages_by_material.get(mid, [])
                        pages_by_material[mid] = sorted(set(existing + pages))
            serialized = [
                {"material_id": mid, "pages": pages, "citation_type": "page"}
                for mid, pages in pages_by_material.items()
            ]
            send_json(self, 200, {"chunks": serialized})
            return

        raw_chunks = _fetch_chunk_context(conn, chunk_ids)

    chunk_map = {str(c['id']): c for c in raw_chunks}
    ordered = [chunk_map[str(cid)] for cid in chunk_ids if str(cid) in chunk_map]
    serialized = [
        {
            "chunk_text":  c.get("chunk_text", ""),
            "chunk_type":  c.get("chunk_type", ""),
            "page_number": c.get("page_number"),
            "similarity":  None,
            "source_type": c.get("source_type", ""),
            "material_id": c.get("material_id"),
        }
        for c in ordered
    ]
    send_json(self, 200, {"chunks": serialized})
```

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/chat.py tests/test_chat_citations.py
git commit -m "feat(citations): derive page-based citations from tool_trace for PageIndex messages"
```

---

## Task 5: Remove `StreamingHistoryBubble` from `ChatTab.jsx`

**Files:**
- Modify: `src/ChatTab.jsx`

This task is purely subtractive — remove dead code. No new tests needed; absence of JS errors and UI rendering correctly is the verification.

- [ ] **Step 1: Remove the `StreamingHistoryBubble` component**

Delete lines 1054–1092 in `ChatTab.jsx` — the entire `StreamingHistoryBubble` function:

```js
// DELETE this entire block:
function StreamingHistoryBubble({ history, materials }) {
  ...
}
```

- [ ] **Step 2: Remove `streamingHistory` state declaration**

At line ~1239, delete:

```js
// DELETE:
const [streamingHistory, setStreamingHistory] = useState([]);
```

- [ ] **Step 3: Remove the render site**

At line ~2862, delete:

```jsx
// DELETE:
<StreamingHistoryBubble history={streamingHistory} materials={materials} />
```

- [ ] **Step 4: Remove all `setStreamingHistory` calls and `PHASE_EVENTS` blocks**

There are three streaming handlers (`_stream_send_message` / `_stream_edit_message` / `_stream_regenerate_message`). In each, remove:

**a) The init call at the top of the handler:**
```js
// DELETE in each handler:
setStreamingHistory([{ phase: 'init' }]);
```

**b) The `PHASE_EVENTS` set and `scheduledDelay` accumulation:**
```js
// DELETE in each handler:
const PHASE_EVENTS = new Set(['handoff_decision', 'loop_start', 'sources_found', 'web_search_start', 'web_result', 'rerank']);
...
if (PHASE_EVENTS.has(evt.type)) scheduledDelay += 400;
```

**c) All individual `setStreamingHistory` calls inside `case` blocks:**
```js
// DELETE all of these patterns:
setStreamingHistory((prev) => [...prev, { phase: 'handoff_decision', ... }]);
setStreamingHistory((prev) => [...prev, { phase: 'loop_start', ... }]);
setStreamingHistory((prev) => [...prev, { phase: 'sources_found', ... }]);
setStreamingHistory((prev) => [...prev, { phase: 'web_search_start', ... }]);
setStreamingHistory((prev) => [...prev, { phase: 'web_result', ... }]);
setStreamingHistory((prev) => [...prev, { phase: 'rerank', ... }]);
setStreamingHistory([]);  // all reset calls in the handlers
```

Lines affected: 1743, 1759, 1762, 1765, 1770, 1774, 1777, 1796, 1870, 1979, 1993, 1998, 2033, 2121–2122, 2135, 2139, 2167, 2176, 2181, 2188, 2321, 2346–2347, 2364, 2382, 2391, 2396, 2403.

- [ ] **Step 5: Verify no remaining references**

```bash
grep -n 'StreamingHistoryBubble\|streamingHistory\|setStreamingHistory\|PHASE_EVENTS' /Users/shubhan/OneShotCourseMate/src/ChatTab.jsx
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(ui): remove streaming status bubble — PageIndex does not emit phase events"
```

---

## Task 6: Update `ToolTraceIndicator` and `SourcesPanel` for PageIndex

**Files:**
- Modify: `src/ChatTab.jsx`

- [ ] **Step 1: Update `toolTraceToEvents` to handle PageIndex tool entries**

Replace the `toolTraceToEvents` function body (lines ~994–1014) with:

```js
function toolTraceToEvents(toolTrace) {
  const events = [];
  const seenIterations = new Set();
  for (const entry of (toolTrace || [])) {
    if (entry.iteration != null && !seenIterations.has(entry.iteration)) {
      seenIterations.add(entry.iteration);
      events.push({ phase: 'loop_start', iteration: entry.iteration, maxIteration: null });
    }
    if (entry.tool === 'search_materials') {
      events.push({ phase: 'sources_found', result_count: entry.result_count || 0, chunks: [] });
    } else if (entry.tool === 'web_search') {
      events.push({ phase: 'web_search_start', query: '' });
      for (const u of (entry.urls || [])) {
        let hostname = u.url || '';
        try { hostname = new URL(u.url).hostname.replace(/^www\./, ''); } catch {}
        events.push({ phase: 'web_result', url: u.url, hostname, excerpt: u.title || '' });
      }
    } else if (entry.tool === 'rerank_results') {
      events.push({ phase: 'rerank', input_count: entry.result_count, output_count: entry.result_count });
    } else if (entry.tool === 'get_page_content') {
      events.push({ phase: 'page_fetch', material_id: entry.args?.material_id, pages: entry.args?.pages });
    } else if (entry.tool === 'get_material_structure') {
      events.push({ phase: 'structure_fetch', material_id: entry.args?.material_id });
    }
  }
  return events;
}
```

- [ ] **Step 2: Add `page_fetch` and `structure_fetch` cases to `getTracePrimary`**

In `getTracePrimary` (line ~938), add before the `default` case:

```js
case 'page_fetch': {
  const mat = (materialMap || {})[status.material_id];
  const name = mat?.name ? mat.name.replace(/\.[^.]+$/, '').slice(0, 25) : `material ${status.material_id}`;
  return `Fetched pages ${status.pages || '?'} from ${name}`;
}
case 'structure_fetch': {
  const mat = (materialMap || {})[status.material_id];
  const name = mat?.name ? mat.name.replace(/\.[^.]+$/, '').slice(0, 25) : `material ${status.material_id}`;
  return `Retrieved structure of ${name}`;
}
```

Note: `getTracePrimary` currently takes `status` but not `materialMap`. Update the function signature and the call site in `ToolTraceIndicator` to pass `materialMap`:

```js
// Signature change:
function getTracePrimary(status, materialMap) {

// Call site in ToolTraceIndicator map:
<p className="text-[11px] text-indigo-500 leading-snug">{getTracePrimary(s, materialMap)}</p>
```

- [ ] **Step 3: Update `SourcesPanel` to render page-based citations**

In `SourcesPanel`, inside the `.map((chunk, idx) => { ... })` callback (line ~436), add a branch at the top before the existing `return`:

```jsx
if (chunk.citation_type === 'page') {
  const material = chunk.material_id != null ? materialMap[chunk.material_id] : null;
  const pages = chunk.pages || [];
  const pageLabel = pages.length === 0
    ? ''
    : pages.length === 1
      ? `p. ${pages[0]}`
      : `pp. ${pages[0]}–${pages[pages.length - 1]}`;
  const downloadUrl = getMaterialUrl(material) || null;
  return (
    <div
      key={idx}
      className="rounded-lg px-3 py-2.5 border border-gray-100 bg-gray-50 text-xs"
    >
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center justify-center w-4 h-4 rounded bg-indigo-100 text-indigo-600 font-semibold text-[10px] flex-shrink-0">
          {idx + 1}
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

- [ ] **Step 4: Verify no JS errors in the browser**

Start the dev server and open a chat with a PageIndex message (or any chat):

```bash
cd /Users/shubhan/OneShotCourseMate && npm run dev
```

Check browser console: no `setStreamingHistory is not defined`, no `StreamingHistoryBubble` errors. The `ToolTraceIndicator` should render PageIndex tool steps when a message's `tool_trace` contains `get_page_content` entries.

- [ ] **Step 5: Run the Python test suite one final time**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(ui): adapt ToolTraceIndicator and SourcesPanel for PageIndex page-based citations"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Flip `PAGEINDEX_RETRIEVAL_ENABLED` default to True | Task 1 |
| `_is_pageindex_active()` helper, gate 4 `retrieve_chunks` sites | Task 2 |
| Fix `retrieve_context` → `retrieve_chunks` in eval_runner | Task 3 |
| Fix `_parse_pages` import path in eval_runner | Task 3 |
| `_get_message_chunks` returns page citations for PageIndex messages | Task 4 |
| Remove `StreamingHistoryBubble` + `streamingHistory` state | Task 5 |
| Remove `PHASE_EVENTS` + `scheduledDelay` blocks | Task 5 |
| `toolTraceToEvents` handles `get_page_content` / `get_material_structure` | Task 6 |
| `SourcesPanel` renders material + page range for `citation_type: "page"` | Task 6 |
| Web search scoped out — no changes | ✓ (documented, no task) |

All spec sections covered.
