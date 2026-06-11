# Streaming Retrieval Progress — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 2.3
**Scope:** `api/llm.py::run_agent_pageindex` (retrieval loop, line ~2409), `api/chat.py` SSE response (do_POST ~337), `src/ChatTab.jsx` (render progress). No retrieval-quality change.

## Problem

Retrieval averages ~9.6s (and the planner timeout was just raised to 300s for gpt-5.x models). The
user stares at a frozen composer with no signal that anything is happening. The agent loop already
knows exactly what it is doing each step — it calls named tools (`get_material_structure`,
`get_page_content`, `get_related_materials`) — but none of that is surfaced.

## Goal

While retrieval runs, the chat streams short, ephemeral status lines into the UI:
- "Reading the structure of Lecture 4…"
- "Fetching pages 10–14 of Homework 3…"
Then they are replaced by the streamed answer. Dead air becomes visible, legible progress.

## Decisions

1. **Progress callback, not a new transport.** `run_agent_pageindex` gains an optional
   `on_progress: Callable[[dict], None] | None = None` parameter. Each time the loop dispatches a
   tool, it calls `on_progress({"phase": "...", "tool": "...", "label": "...", "detail": "..."})`.
   Default `None` preserves all existing callers/behavior and the eval path.
2. **Human-readable labels built server-side.** The callback payload carries a ready-to-show `label`
   string (e.g. "Fetching pages 10–14 of Homework 3"), derived from the tool name + args + the
   material title already known to the loop. The frontend does not interpret tool internals.
3. **Reuse the existing SSE stream.** `api/chat.py` already streams the answer over
   `text/event-stream`. Add a distinct event type `event: progress` with a JSON `data:` line; the
   final answer keeps using the existing token/event frames. The frontend distinguishes by event
   type.
4. **Ephemeral in the UI.** Progress lines render in a lightweight status area on the pending
   assistant message and are cleared when the first answer token arrives. They are **not** persisted
   to `chat_messages` — they are transient UX, not conversation content.
5. **Planner streaming is a separate, optional follow-on.** This item surfaces tool-step progress;
   converting `_pageindex_call_responses` itself to streaming (to beat proxy idle timeouts) is noted
   but not required here.

## API shape

`run_agent_pageindex(..., on_progress=None)`:

```python
def _emit(progress_cb, **payload):
    if progress_cb:
        try:
            progress_cb(payload)
        except Exception:
            pass  # progress must never break retrieval

# at each tool dispatch in the loop:
_emit(on_progress, phase="retrieval", tool=tool_name, label=_progress_label(tool_name, args, title))
```

`_progress_label(tool_name, args, material_title)` (pure, testable):
- `get_material_structure` → `f"Reading the structure of {title}"`
- `get_page_content` → `f"Fetching pages {pages} of {title}"`
- `get_related_materials` → `"Looking for related materials"`
- unknown → `"Searching your materials"`

## chat.py wiring

In `do_POST`, define a closure that writes an SSE progress frame and pass it as `on_progress`:

```python
def _send_progress(payload):
    self.wfile.write(f"event: progress\ndata: {json.dumps(payload)}\n\n".encode())
    self.wfile.flush()
# ...
run_agent_pageindex(..., on_progress=_send_progress)
```

Match the exact SSE frame/encoding helper the file already uses for answer tokens.

## Frontend (`src/ChatTab.jsx`)

- In the SSE read loop, branch on event type: `progress` → push `payload.label` into a transient
  `retrievalStatus` state on the in-flight assistant message; first answer-token event → clear it.
- Render `retrievalStatus` as a small italic/animated line in the pending bubble.

## Verification

- pytest: `_progress_label` table-driven (each tool → expected string); `run_agent_pageindex` with a
  stub `on_progress` collects ≥1 progress payload over a mocked tool loop; with `on_progress=None`
  behavior is unchanged (no crash, same result).
- Manual: ask a broad question; watch status lines appear ("Reading the structure of…", "Fetching
  pages…") then get replaced by the streamed answer.
