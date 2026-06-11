# Streaming Retrieval Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface live retrieval progress ("Reading the structure of Lecture 4…", "Fetching pages 10–14…") as ephemeral SSE events while the PageIndex agent runs, replaced by the streamed answer.

**Architecture:** A pure `_progress_label` formatter + an optional `on_progress` callback threaded through `run_agent_pageindex`; `api/chat.py` wires it to a new `event: progress` SSE frame; `ChatTab` renders transient status on the pending assistant message.

**Tech Stack:** Python serverless, SSE, React.

**Spec:** `docs/superpowers/specs/2026-06-10-streaming-retrieval-progress-design.md`

---

### Task 1: Pure progress-label formatter

**Files:**
- Modify: `api/llm.py` (add `_progress_label`)
- Test: `tests/test_progress_label.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_progress_label.py
from api.llm import _progress_label

def test_structure_label():
    assert _progress_label('get_material_structure', {'material_id': 1}, 'Lecture 4') == 'Reading the structure of Lecture 4'

def test_page_content_label():
    assert _progress_label('get_page_content', {'pages': '10-14'}, 'Homework 3') == 'Fetching pages 10-14 of Homework 3'

def test_related_label():
    assert _progress_label('get_related_materials', {}, None) == 'Looking for related materials'

def test_unknown_label():
    assert _progress_label('mystery', {}, None) == 'Searching your materials'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_progress_label.py -v` — FAIL (name not defined).

- [ ] **Step 3: Implement**

Add near the other PageIndex helpers in `api/llm.py`:

```python
def _progress_label(tool_name: str, args: dict, material_title: str | None) -> str:
    title = material_title or "your materials"
    if tool_name == "get_material_structure":
        return f"Reading the structure of {title}"
    if tool_name == "get_page_content":
        pages = (args or {}).get("pages", "")
        return f"Fetching pages {pages} of {title}"
    if tool_name == "get_related_materials":
        return "Looking for related materials"
    return "Searching your materials"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_progress_label.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_progress_label.py
git commit -m "feat: add _progress_label formatter for retrieval progress"
```

---

### Task 2: Thread `on_progress` through `run_agent_pageindex`

**Files:**
- Modify: `api/llm.py` (`run_agent_pageindex` signature ~2409 and its tool-dispatch loop)
- Test: `tests/test_pageindex_progress.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pageindex_progress.py
import api.llm as llm

def test_emit_calls_callback_and_swallows_errors():
    seen = []
    llm._emit(lambda p: seen.append(p), phase='retrieval', tool='get_page_content', label='x')
    assert seen == [{'phase': 'retrieval', 'tool': 'get_page_content', 'label': 'x'}]
    # must not raise when the callback throws:
    llm._emit(lambda p: (_ for _ in ()).throw(RuntimeError('boom')), label='y')

def test_emit_noop_when_callback_none():
    llm._emit(None, label='z')   # no exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pageindex_progress.py -v` — FAIL (`_emit` not defined).

- [ ] **Step 3: Implement `_emit` and call it at each tool dispatch**

Add helper:

```python
def _emit(progress_cb, **payload):
    if progress_cb:
        try:
            progress_cb(payload)
        except Exception:
            pass  # progress must never break retrieval
```

Add `on_progress=None` to the `run_agent_pageindex` signature (keyword-only, after existing params).
In the loop, immediately before each tool is executed (search for where tools are dispatched — the
loop reads `tool_calls` and routes `get_material_structure`/`get_page_content`/`get_related_materials`),
add:

```python
_emit(on_progress, phase="retrieval", tool=tool_name,
      label=_progress_label(tool_name, tool_args, material_title))
```

Use the loop's existing variable names for the tool name, parsed args, and the material title (the
title is available from the routing index the loop already builds). If a per-call title isn't handy,
pass `None` — the formatter falls back to "your materials".

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pageindex_progress.py -v` — PASS. Then run the existing agent tests to prove
no regression: `pytest tests/test_pageindex_agent.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_pageindex_progress.py
git commit -m "feat: emit retrieval tool progress via optional on_progress callback"
```

---

### Task 3: Emit progress as SSE frames from chat.py

**Files:**
- Modify: `api/chat.py` (`do_POST`, where `run_agent_pageindex` is invoked)

- [ ] **Step 1: Define the progress sender and pass it in**

Near the streaming response setup in `do_POST`, after headers are sent, add a closure that writes an
SSE `progress` frame using the same write/flush the file already uses for answer tokens:

```python
def _send_progress(payload):
    try:
        self.wfile.write(("event: progress\n" + "data: " + json.dumps(payload) + "\n\n").encode())
        self.wfile.flush()
    except Exception:
        pass

# pass to the agent:
run_agent_pageindex(..., on_progress=_send_progress)
```

Match the exact frame format the file already emits for tokens (some SSE setups omit the `event:`
line and use only `data:` — if so, encode the type inside the JSON, e.g.
`{"type": "progress", ...}`, and keep answer frames as they are). Pick whichever matches the existing
convention so the frontend parser stays uniform.

- [ ] **Step 2: Manually verify frames are sent**

Run: `npm run dev` (or `vercel dev`), open the network tab on a chat request, send a broad question,
and confirm `progress` frames arrive before the answer tokens.

- [ ] **Step 3: Commit**

```bash
git add api/chat.py
git commit -m "feat: stream retrieval progress frames over chat SSE"
```

---

### Task 4: Render transient progress in ChatTab

**Files:**
- Modify: `src/ChatTab.jsx` (SSE read loop + pending assistant bubble)

- [ ] **Step 1: Capture progress in the SSE loop**

In the chat send/stream handler (search for where SSE chunks are parsed — `data:` lines), branch on
the progress event/type and store the latest label on the in-flight assistant message:

```jsx
// when a progress frame is parsed:
setRetrievalStatus(payload.label);
// when the first answer-token frame arrives:
setRetrievalStatus(null);
```

Add `const [retrievalStatus, setRetrievalStatus] = useState(null);` near the other send-related
state, and clear it in the `finally`/completion path too.

- [ ] **Step 2: Render it on the pending bubble**

Where the in-flight assistant message renders (before any answer text), show:

```jsx
{retrievalStatus && (
  <div className="text-xs italic text-gray-400 animate-pulse">{retrievalStatus}</div>
)}
```

- [ ] **Step 3: Manually verify the full loop**

Run: `npm run dev`. Ask a broad question → status lines appear and animate, then vanish as the answer
streams in.

- [ ] **Step 4: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat: show ephemeral retrieval progress in chat"
```

---

## Self-Review

- **Spec coverage:** label formatter (T1), `on_progress` plumbing with None-default safety (T2),
  SSE frame (T3), transient UI (T4). ✓
- **Backward compatibility:** `on_progress=None` default keeps every existing caller and the eval
  path unchanged; `_emit` swallows callback errors so retrieval can never break. ✓
- **Convention caveat:** T3 explicitly tells the engineer to match the file's existing SSE frame
  format rather than assume `event:`-style frames. ✓
