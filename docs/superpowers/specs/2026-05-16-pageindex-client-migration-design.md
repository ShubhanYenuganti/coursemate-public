# PageIndex Client Migration Design

**Branch:** `feat-pageindex-client`  
**Date:** 2026-05-16  
**Status:** Approved

## Goal

Make PageIndex the default retrieval path by flipping one flag default, skipping the now-wasted vector RAG embed call in `chat.py`, and fixing two broken call sites in the eval runner. No code is deleted — the vector RAG and agentic loop remain as dormant fallbacks behind the kill-switch.

## Changes

### 1. `api/llm.py` — flip flag default

In `synthesize()`, change:

```python
use_pageindex = _is_enabled("PAGEINDEX_RETRIEVAL_ENABLED", default=False)
```

to:

```python
use_pageindex = _is_enabled("PAGEINDEX_RETRIEVAL_ENABLED", default=True)
```

No other changes to `synthesize()`. The 3-tier dispatch (PageIndex → Agentic → Vector RAG) is structurally preserved. Agentic loop and vector RAG paths remain reachable if `PAGEINDEX_RETRIEVAL_ENABLED=false` is set explicitly.

### 2. `api/chat.py` — skip wasted retrieve_chunks

Add a module-level helper:

```python
def _is_pageindex_active() -> bool:
    return os.environ.get("PAGEINDEX_RETRIEVAL_ENABLED", "true").lower() != "false"
```

At each of the 4 `retrieve_chunks` call sites, wrap the call:

```python
chunks = retrieve_chunks(...) if not _is_pageindex_active() else []
```

The `chunks` variable is still passed to `synthesize()` unchanged. When PageIndex is active, the Lambda embed call is never made and `chunks=[]`.

**Call sites (line numbers approximate, verify before editing):**
- `chat.py:915` — main message send path
- `chat.py:1153` — clarification send path
- `chat.py:1364` — second send variant
- `chat.py:2107` — locked_chunks fallback

### 3. `tests/pageindex_eval/eval_runner.py` — fix broken call sites

**Fix 1:** `run_vector_rag` imports and calls `retrieve_context` which does not exist in `rag.py`. Rename to `retrieve_chunks`:

```python
# Before
from rag import retrieve_context
chunks = retrieve_context(conn, question, material_ids=material_ids)

# After
from rag import retrieve_chunks
chunks = retrieve_chunks(conn, question, material_ids)
```

**Fix 2:** `run_pageindex_rag` imports `_parse_pages` from a non-existent path:

```python
# Before
from services.query.pageindex_retrieval import _parse_pages

# After
from pageindex_retrieval import _parse_pages
```

Side-by-side comparison structure (vector vs PageIndex) stays intact.

### 4. `src/ChatTab.jsx` — remove streaming status bubble

The `StreamingHistoryBubble` component and all associated state are built around agentic loop phase events (`handoff_decision`, `loop_start`, `sources_found`, `web_search_start`, `web_result`, `rerank`). PageIndex emits `tool_call` events instead — these are not phase events and the bubble never meaningfully fires.

**Remove:**
- `StreamingHistoryBubble` function component (~60 lines)
- `streamingHistory` state and all `setStreamingHistory` calls
- `PHASE_EVENTS` set and the conditional `scheduledDelay += 400` block in all three streaming handlers (`stream_send`, `stream_edit`, `stream_regenerate`)
- The `<StreamingHistoryBubble>` render site (~line 2862)

**Keep:**
- `ToolTraceIndicator` — renders post-completion from the persisted `tool_trace`. Adapt `toolTraceToEvents` to handle `get_page_content` tool entries (see Section 6).
- All other streaming event handling (`done`, `user_message`, `tool_call`, `error`)

### 5. Web retrieval — scoped out

Web search is currently only wired into `run_agent_openai`, not `run_agent_pageindex`. With PageIndex as the primary path, web search is unreachable. Adding it to `run_agent_pageindex` is a non-trivial tool addition deferred to a future branch. The frontend changes in Section 4 already make the client agnostic to web search events — when web search is added to PageIndex later, it will surface silently in `ToolTraceIndicator`.

No changes to `run_agent_pageindex` or web search logic in this branch.

### 6. Citations — page-based instead of chunk-based

**Current system:**
- `retrieved_chunk_ids` in DB = vector chunk integer IDs
- `GET /api/chat?resource=chunks` → `_fetch_chunk_context` → returns `chunk_text`, `chunk_type`, `page_number`, `similarity`
- `SourcesPanel` renders chunk excerpts with similarity scores

**PageIndex system:**
- `grounding_refs` = `["material:624", "material:625"]` — no chunk IDs
- Full page detail lives in `tool_trace`: entries with `tool="get_page_content"`, `args.material_id`, `args.pages`

**Backend (`_get_message_chunks` in `chat.py`):**

Detect PageIndex messages by checking if any entry in `retrieved_chunk_ids` is a string starting with `"material:"`. If so, load `tool_trace` for that message and derive page citations grouped by material:

```python
# PageIndex path: derive citations from tool_trace
[
  {"material_id": 624, "pages": [3, 4, 5]},
  {"material_id": 625, "pages": [1, 2]},
]
```

Return these as the `chunks` array with a `citation_type: "page"` marker so the frontend can branch on display.

**Frontend (`SourcesPanel` in `ChatTab.jsx`):**

When `chunk.citation_type === "page"`, render material title + page numbers (e.g. "Lecture 3 — pp. 4–7"). Drop `chunk_text` and `similarity` display for PageIndex citations.

**`toolTraceToEvents` in `ToolTraceIndicator`:**

Add a case for `get_page_content` tool entries:

```js
} else if (entry.tool === 'get_page_content') {
  events.push({ phase: 'page_fetch', material_id: entry.args?.material_id, pages: entry.args?.pages });
}
```

Add corresponding `getTracePrimary` case: `"Fetched pages ${pages} from material ${material_id}"`.

## What Does Not Change

- `api/rag.py` — not modified or deleted
- `api/tools.py` — `search_course_materials` / `retrieve_chunks` inside the agentic loop stays; it's dormant when PageIndex is active
- `eval_runner.py` comparison structure — vector column stays, just fixed to call the right function
- Web search logic in `run_agent_pageindex` — deferred to future branch
- All existing unit tests — no test targets are affected by these changes

## Success Criteria

1. `PAGEINDEX_RETRIEVAL_ENABLED` unset in env → PageIndex is used (default=True)
2. `PAGEINDEX_RETRIEVAL_ENABLED=false` → falls through to agentic/vector path as before
3. No Lambda embed call made when PageIndex is active (observable via logs)
4. `eval_runner.py` runs end-to-end without import errors
5. Streaming status bubble is gone; no console errors from removed state
6. `GET /api/chat?resource=chunks` returns page-based citations for PageIndex messages
7. `SourcesPanel` renders material + page numbers for PageIndex messages
8. `ToolTraceIndicator` shows `get_page_content` steps in completed message trace
9. All existing unit tests pass (`pytest tests/`)
