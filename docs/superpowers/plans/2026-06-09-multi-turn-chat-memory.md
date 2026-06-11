# Multi-Turn Conversational Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the chat send path replay prior active-branch conversation turns (verbatim, within a per-model token budget) to the model, replacing the single-turn payload.

**Architecture:** Add four pure-ish helpers to `api/llm.py` — a per-model context-window map, a token estimator, a chat-history loader, and a budget-aware composer. Wire them into `run_agent_pageindex` so each provider branch (Claude / Gemini / OpenAI+Responses) seeds its message list with composed history before the current user turn. Collapse the live clarification branch in `api/chat.py` into the plain `synthesize` path, preserving the depth cap as a system instruction. Populate the dead `context_token_count` / `response_token_count` columns for instrumentation.

**Tech Stack:** Python 3 stdlib, `pytest`, `unittest.mock`. No new dependencies. Tests follow the existing `tests/test_llm_unit.py` pattern (stub `middleware`, `models`, `db`, `boto3`, `crypto_utils`; `sys.path` insert `api/`).

**Scope guardrails:**
- Do NOT touch PageIndex course-material retrieval (`api/pageindex_retrieval.py`, `lambda/index_materials/`, the retrieval tools).
- Retrieval stays on `gpt-4o-mini`. No provider-agnostic-retrieval refactor.
- Hot tier only: verbatim text, drop-oldest-first when over budget. No summary/embedding/episode tiers.

---

### Task 1: Per-model context-window map + token estimator

**Files:**
- Modify: `api/llm.py` (add constants/helpers near the other `_safe_int_env` / `_char_cap_from_tokens` helpers, around line 270–475)
- Test: `tests/test_chat_memory.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_chat_memory.py`:

```python
"""Unit tests for multi-turn chat memory helpers in api/llm.py."""
import sys
import os
from unittest.mock import MagicMock

# Stub heavy imports so llm.py can load without a real environment.
for mod in ("middleware", "models", "db", "boto3", "crypto_utils"):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import llm  # noqa: E402


def test_estimate_tokens_uses_char_heuristic():
    # ~4 chars per token, floor of 1.
    assert llm._estimate_tokens("") == 1
    assert llm._estimate_tokens("abcd") == 1
    assert llm._estimate_tokens("a" * 400) == 100


def test_context_window_known_model():
    # gpt-4o-mini has a 128k window.
    assert llm._context_window_for("gpt-4o-mini") == 128000


def test_context_window_unknown_model_falls_back():
    assert llm._context_window_for("totally-made-up-model") == llm._DEFAULT_CONTEXT_WINDOW
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py -v`
Expected: FAIL — `AttributeError: module 'llm' has no attribute '_estimate_tokens'`

- [ ] **Step 3: Write minimal implementation**

In `api/llm.py`, add after `_char_cap_from_tokens` (around line 475):

```python
# --- Multi-turn chat memory: budgeting -------------------------------------

_DEFAULT_CONTEXT_WINDOW = 128000

# Per-model context windows (tokens). Unknown models fall back to the default.
MODEL_CONTEXT_WINDOWS = {
    # Claude
    "claude-opus-4-8": 200000,
    "claude-opus-4-7": 200000,
    "claude-opus-4-6": 200000,
    "claude-sonnet-4-6": 200000,
    "claude-haiku-4-5-20251001": 200000,
    "claude-sonnet-4-5-20250929": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    # Gemini
    "gemini-3.5-flash": 1000000,
    "gemini-3.1-pro-preview": 1000000,
    "gemini-3-flash-preview": 1000000,
    "gemini-2.5-pro": 1000000,
    "gemini-2.5-flash": 1000000,
    "gemini-2.5-flash-lite": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-2.0-flash-lite": 1000000,
    # OpenAI
    "gpt-5.5": 400000,
    "gpt-5.4-mini": 400000,
    "gpt-5.4-nano": 400000,
    "gpt-5.2": 400000,
    "gpt-5.1": 400000,
    "gpt-5-mini": 400000,
    "gpt-5-nano": 400000,
    "gpt-4.1": 1000000,
    "gpt-4.1-mini": 1000000,
    "gpt-4.1-nano": 1000000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "o3": 200000,
    "o3-mini": 200000,
    "o3-pro": 200000,
    "o4-mini": 200000,
    "o1": 200000,
    "o1-pro": 200000,
    "gpt-oss-120b": 128000,
}


def _context_window_for(model: str) -> int:
    return MODEL_CONTEXT_WINDOWS.get(model, _DEFAULT_CONTEXT_WINDOW)


def _estimate_tokens(text: str) -> int:
    """Canonical token estimate: ~4 chars/token, floor of 1."""
    if not text:
        return 1
    return max(1, len(text) // 4)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "feat(chat-memory): add per-model context window map and token estimator"
```

---

### Task 2: History budget calculation

**Files:**
- Modify: `api/llm.py` (after the Task 1 helpers)
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_chat_memory.py`:

```python
def test_history_budget_subtracts_reserves_and_margin():
    # window=1000, system=40 tokens (160 chars), current user=10 tokens (40 chars).
    # reserve=RESPONSE_RESERVE_TOKENS, margin=SAFETY_MARGIN_RATIO of window.
    budget = llm._history_budget(
        window=1000,
        system_text="s" * 160,
        current_user_text="u" * 40,
    )
    expected = 1000 - 40 - llm.RESPONSE_RESERVE_TOKENS - 10 - int(1000 * llm.SAFETY_MARGIN_RATIO)
    assert budget == expected


def test_history_budget_never_negative():
    budget = llm._history_budget(window=10, system_text="x" * 1000, current_user_text="y" * 1000)
    assert budget == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_history_budget_subtracts_reserves_and_margin -v`
Expected: FAIL — `AttributeError: module 'llm' has no attribute '_history_budget'`

- [ ] **Step 3: Write minimal implementation**

In `api/llm.py`, add after `_estimate_tokens`:

```python
RESPONSE_RESERVE_TOKENS = 4096
SAFETY_MARGIN_RATIO = 0.15


def _history_budget(window: int, system_text: str, current_user_text: str) -> int:
    """Tokens left for replayed history after system prompt, response reserve,
    current user message, and a safety margin. Never negative."""
    used = (
        _estimate_tokens(system_text)
        + RESPONSE_RESERVE_TOKENS
        + _estimate_tokens(current_user_text)
        + int(window * SAFETY_MARGIN_RATIO)
    )
    return max(0, window - used)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py -v`
Expected: PASS (5 tests total)

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "feat(chat-memory): add history token budget calculation"
```

---

### Task 3: History composer (drop-oldest-first)

**Files:**
- Modify: `api/llm.py` (after the Task 2 helpers)
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_chat_memory.py`:

```python
def test_compose_history_keeps_all_when_under_budget():
    turns = [
        {"role": "user", "content": "aaaa"},       # 1 token
        {"role": "assistant", "content": "bbbb"},  # 1 token
    ]
    out = llm._compose_history(turns, budget_tokens=100)
    assert out == turns  # unchanged, chronological order preserved


def test_compose_history_drops_oldest_first_when_over_budget():
    turns = [
        {"role": "user", "content": "a" * 400},       # 100 tokens (oldest)
        {"role": "assistant", "content": "b" * 400},  # 100 tokens
        {"role": "user", "content": "c" * 400},       # 100 tokens (newest)
    ]
    # Budget only fits the two newest (200 tokens).
    out = llm._compose_history(turns, budget_tokens=200)
    assert [t["content"][0] for t in out] == ["b", "c"]  # oldest "a" dropped


def test_compose_history_empty_budget_returns_empty():
    turns = [{"role": "user", "content": "a" * 400}]
    assert llm._compose_history(turns, budget_tokens=0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_compose_history_drops_oldest_first_when_over_budget -v`
Expected: FAIL — `AttributeError: module 'llm' has no attribute '_compose_history'`

- [ ] **Step 3: Write minimal implementation**

In `api/llm.py`, add after `_history_budget`:

```python
def _compose_history(prior_turns: list, budget_tokens: int) -> list:
    """Return the newest prior turns that fit within budget_tokens, in
    chronological (oldest->newest) order. Drops oldest turns first."""
    kept_reversed = []
    running = 0
    for turn in reversed(prior_turns):  # newest first
        cost = _estimate_tokens(turn.get("content", ""))
        if running + cost > budget_tokens:
            break
        kept_reversed.append(turn)
        running += cost
    return list(reversed(kept_reversed))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py -v`
Expected: PASS (8 tests total)

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "feat(chat-memory): add budget-aware history composer"
```

---

### Task 4: Chat-history loader (DB query)

**Files:**
- Modify: `api/llm.py` (after the Task 3 helpers)
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_chat_memory.py`:

```python
def test_load_chat_history_queries_active_branch_and_maps_rows():
    rows = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor

    out = llm._load_chat_history(conn, chat_id=7, before_index=5)

    assert out == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    # Query must filter is_deleted and message_index < before_index, ordered asc.
    sql, params = cursor.execute.call_args[0]
    assert "is_deleted = FALSE" in sql
    assert "message_index <" in sql
    assert "ORDER BY message_index ASC" in sql
    assert params == (7, 5)


def test_load_chat_history_none_chat_returns_empty():
    assert llm._load_chat_history(MagicMock(), chat_id=None, before_index=5) == []
    assert llm._load_chat_history(MagicMock(), chat_id=1, before_index=None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_load_chat_history_queries_active_branch_and_maps_rows -v`
Expected: FAIL — `AttributeError: module 'llm' has no attribute '_load_chat_history'`

- [ ] **Step 3: Write minimal implementation**

In `api/llm.py`, add after `_compose_history`:

```python
def _load_chat_history(conn, chat_id, before_index) -> list:
    """Active-branch prior turns (user + assistant), oldest->newest, excluding
    soft-deleted rows and anything at/after before_index. Returns
    [{"role", "content"}]. reply_history undo blobs are intentionally ignored."""
    if chat_id is None or before_index is None:
        return []
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT role, content
        FROM chat_messages
        WHERE chat_id = %s
          AND is_deleted = FALSE
          AND role IN ('user', 'assistant')
          AND message_index < %s
        ORDER BY message_index ASC
        """,
        (chat_id, before_index),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "feat(chat-memory): add active-branch chat history loader"
```

---

### Task 5: Combined history builder + per-provider seed shaping

This task adds one function that ties loader + budget + composer together and returns the kept turns, plus three tiny shapers that convert kept turns to each provider's message shape. Wiring into the loop is Task 6.

**Files:**
- Modify: `api/llm.py` (after the Task 4 helpers)
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_chat_memory.py`:

```python
def test_build_history_turns_end_to_end(monkeypatch):
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "a" * 400},       # 100 tokens
        {"role": "assistant", "content": "b" * 400},  # 100 tokens
    ])
    # Big window -> both kept.
    kept = llm._build_history_turns(
        conn=MagicMock(), chat_id=1, before_index=9,
        model="gpt-4o-mini", system_text="s", current_user_text="u",
    )
    assert len(kept) == 2


def test_shape_history_openai_roles_passthrough():
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert llm._shape_history_openai(turns) == turns


def test_shape_history_gemini_maps_assistant_to_model():
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    out = llm._shape_history_gemini(turns)
    assert out == [
        {"role": "user", "parts": [{"text": "hi"}]},
        {"role": "model", "parts": [{"text": "yo"}]},
    ]


def test_shape_history_claude_roles_passthrough():
    turns = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert llm._shape_history_claude(turns) == turns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_build_history_turns_end_to_end -v`
Expected: FAIL — `AttributeError: module 'llm' has no attribute '_build_history_turns'`

- [ ] **Step 3: Write minimal implementation**

In `api/llm.py`, add after `_load_chat_history`:

```python
def _build_history_turns(conn, chat_id, before_index, model, system_text, current_user_text) -> list:
    """Load active-branch history and trim it to the model's budget.
    Returns kept turns as [{"role", "content"}] in chronological order."""
    prior = _load_chat_history(conn, chat_id, before_index)
    if not prior:
        return []
    window = _context_window_for(model)
    budget = _history_budget(window, system_text, current_user_text)
    return _compose_history(prior, budget)


def _shape_history_openai(turns: list) -> list:
    """OpenAI / Responses message shape == canonical {role, content}."""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


def _shape_history_claude(turns: list) -> list:
    """Claude messages use the same role names (user/assistant)."""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


def _shape_history_gemini(turns: list) -> list:
    """Gemini contents: role 'assistant' -> 'model', content -> parts[].text."""
    out = []
    for t in turns:
        role = "model" if t["role"] == "assistant" else "user"
        out.append({"role": role, "parts": [{"text": t["content"]}]})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py -v`
Expected: PASS (14 tests total)

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "feat(chat-memory): add history builder and per-provider seed shapers"
```

---

### Task 6: Thread history params through `synthesize` / `run_agent_pageindex` and seed each provider branch

**Files:**
- Modify: `api/llm.py:1635` (`run_agent_pageindex` signature + the three seed lists), `api/llm.py:2178` (`synthesize` signature + its `run_agent_pageindex(...)` call)
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_chat_memory.py`. This patches the OpenAI retrieval/synthesis stream call to capture the seeded `messages` and asserts prior history is present before the current user turn.

```python
def test_run_agent_seeds_openai_history(monkeypatch):
    # No images, no real network.
    monkeypatch.setattr(llm, "_fetch_images_as_base64", lambda keys: [])
    monkeypatch.setattr(llm, "_recall_prior_chat_images", lambda *a, **k: [])
    monkeypatch.setattr(llm, "get_course_routing_index", lambda conn, cid, mids: [], raising=False)
    monkeypatch.setattr(llm, "_load_chat_history", lambda c, cid, bi: [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ])

    captured = {}

    def fake_stream(api_key, model, msgs, tools, on_event):
        captured["msgs"] = msgs
        # Return a final answer with no tool calls: (text, finish_reason)-style stub
        # matching _pageindex_stream_call's contract used by the OpenAI branch.
        return ("Final answer.", "stop")

    monkeypatch.setattr(llm, "_pageindex_stream_call", fake_stream)

    llm.run_agent_pageindex(
        conn=MagicMock(),
        user_message="current question",
        model="gpt-4o-mini",
        api_key="sk-test",
        chat_id=1,
        course_id=2,
        context_material_ids=[],
        provider="openai",
        history_before_index=9,
    )

    contents = [m["content"] for m in captured["msgs"] if m["role"] in ("user", "assistant")]
    assert "earlier question" in contents
    assert "earlier answer" in contents
    # Current user turn is last.
    assert captured["msgs"][-1]["content"] == "current question"
```

> NOTE: `_pageindex_stream_call`'s real return contract is whatever the existing OpenAI branch already unpacks at `api/llm.py:1706-1711` and its first call site. Read that branch before writing `fake_stream` and match its exact tuple shape (the stub above is the shape used by the OpenAI text path; adjust if the branch unpacks differently).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_run_agent_seeds_openai_history -v`
Expected: FAIL — `TypeError: run_agent_pageindex() got an unexpected keyword argument 'history_before_index'`

- [ ] **Step 3: Implementation**

3a. Add params to `run_agent_pageindex` signature (`api/llm.py:1635`):

```python
def run_agent_pageindex(
    conn,
    user_message: str,
    model: str,
    api_key: str,
    chat_id: int | None,
    course_id: int | None,
    context_material_ids: list,
    on_event=None,
    provider: str = "openai",
    web_search_enabled: bool = False,
    image_s3_keys: list | None = None,
    history_before_index: int | None = None,
    clarification_depth: int = 0,
) -> tuple:
```

3b. After `system_content` is fully built and before the seed message lists (i.e. right before line 1681 `request_images = ...`), append the depth-cap instruction and build history turns once:

```python
    if clarification_depth >= 2:
        system_content += (
            "\n\n**Do not ask any further clarifying questions.** Answer the user's question "
            "directly and completely using the available materials."
        )

    _history_turns = _build_history_turns(
        conn=conn,
        chat_id=chat_id,
        before_index=history_before_index,
        model=model,
        system_text=system_content,
        current_user_text=user_message,
    )
```

3c. OpenAI seed list at `api/llm.py:1691`. Change:

```python
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": openai_user_content},
    ]
```
to:
```python
    messages = (
        [{"role": "system", "content": system_content}]
        + _shape_history_openai(_history_turns)
        + [{"role": "user", "content": openai_user_content}]
    )
```

3d. Claude seed list at `api/llm.py:1735`. Change:

```python
        claude_messages = [{"role": "user", "content": claude_user_content}]
```
to:
```python
        claude_messages = _shape_history_claude(_history_turns) + [
            {"role": "user", "content": claude_user_content}
        ]
```

3e. Gemini seed list. Read the Gemini branch around `api/llm.py:1842` where `contents` is first constructed with the current user turn. Prepend history the same way:

```python
        contents = _shape_history_gemini(_history_turns) + [<existing current-user content entry>]
```
(Match the exact existing current-user `contents` entry — do not change its shape, only prepend.)

3f. Record the history token estimate into the returned metadata so Task 7 can persist it. Find where `run_agent_pageindex` builds its metadata/`grounding_meta` dict before returning, and add:

```python
        metadata["history_token_estimate"] = sum(_estimate_tokens(t["content"]) for t in _history_turns)
        metadata["history_turn_count"] = len(_history_turns)
```
(Use the actual local variable name for the returned metadata dict in this function.)

3g. Thread the params through `synthesize` (`api/llm.py:2178`). Add to its signature:

```python
    history_before_index: int | None = None,
    clarification_depth: int = 0,
```
and pass them into its `run_agent_pageindex(...)` call:

```python
        history_before_index=history_before_index,
        clarification_depth=clarification_depth,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py::test_run_agent_seeds_openai_history -v`
Expected: PASS

- [ ] **Step 5: Run the full memory test file + existing llm/pageindex tests**

Run: `pytest tests/test_chat_memory.py tests/test_llm_unit.py tests/test_pageindex_agent.py -v`
Expected: PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "feat(chat-memory): seed provider message lists with budgeted history"
```

---

### Task 7: Collapse the clarification branch in `chat.py` + token-count instrumentation

**Files:**
- Modify: `api/chat.py` (imports line 30/36; the two `clarification_pending` branches at ~1007 and ~1249; the assistant `INSERT` column lists)
- Modify: `tests/test_chat_search_snippets.py:40` (drop `synthesize_with_clarification` from the stub attr list)
- Modify: `api/llm.py` (remove the now-unused `synthesize_with_clarification`)

- [ ] **Step 1: Replace the first clarification branch (`api/chat.py:~1004-1030`)**

Find:
```python
            try:
                if clarification_pending:
                    original_prompt = _get_prior_user_message(conn, chat_id) or content
                    assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary, assistant_follow_ups, assistant_clarifying_question = synthesize_with_clarification(
                        conn=conn,
                        user_id=user['id'],
                        ai_provider=ai_provider,
                        ai_model=ai_model,
                        original_prompt=original_prompt,
                        prior_reply=prior_reply_content or "",
                        clarifying_question=prior_clarification_question or "",
                        user_clarification=content,
                        clarification_depth=prior_clarification_depth,
                        chunks=chunks,
                        chat_id=chat_id,
                        context_material_ids=context_material_ids,
                    )
                else:
                    assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary, assistant_follow_ups, assistant_clarifying_question = synthesize(
                        conn,
                        user['id'],
                        ai_provider,
                        ai_model,
                        content,
                        chunks,
                        chat_id=chat_id,
                        context_material_ids=context_material_ids,
                    )
```

Replace with:
```python
            try:
                assistant_content, retrieved_ids, grounding_meta, tool_trace, assistant_summary, assistant_follow_ups, assistant_clarifying_question = synthesize(
                    conn,
                    user['id'],
                    ai_provider,
                    ai_model,
                    content,
                    chunks,
                    chat_id=chat_id,
                    context_material_ids=context_material_ids,
                    history_before_index=user_message['message_index'],
                    clarification_depth=prior_clarification_depth,
                )
```

> The pending clarifying question and the user's answer are now ordinary history turns the model sees verbatim; `prior_clarification_depth` still drives the depth cap and the persisted `new_clarification_depth`. Leave the `_get_prior_clarification_state` call and `new_clarification_depth` logic intact.

- [ ] **Step 2: Replace the second clarification branch (`api/chat.py:~1246-1272`)**

This is the regenerate/edit-resend send path. Read it first — it has the same `if clarification_pending: synthesize_with_clarification(...) else: synthesize(...)` shape but its own local variable for the current user row. Apply the identical collapse: call `synthesize(...)` unconditionally with `history_before_index=<that path's user row>['message_index']` and `clarification_depth=<that path's prior depth var>`. Match the exact local variable names used in that block.

- [ ] **Step 3: Add token-count instrumentation to the assistant INSERTs**

Both assistant `INSERT INTO chat_messages` statements (around `api/chat.py:1064` and `api/chat.py:1286`) omit `context_token_count` / `response_token_count`. For each, add the two columns to the column list and two placeholders, computing values right before the insert:

```python
            context_token_count = (grounding_meta or {}).get("history_token_estimate")
            response_token_count = max(1, len(assistant_content or "") // 4)
```
Add `context_token_count, response_token_count` to the INSERT column list (e.g. after `clarification_depth`) and the two values to the `VALUES (...)` tuple in the same positions.

- [ ] **Step 4: Remove the dead import and function**

In `api/chat.py` lines 30 and 36, change `from .llm import synthesize, synthesize_with_clarification` / `from llm import synthesize, synthesize_with_clarification` to drop `synthesize_with_clarification`.

In `api/llm.py`, delete the `synthesize_with_clarification` function (starts `api/llm.py:2274`).

In `tests/test_chat_search_snippets.py:40`, remove `"synthesize_with_clarification"` from the tuple of attrs being stubbed.

- [ ] **Step 5: Verify nothing still references the removed symbol**

Run: `grep -rn 'synthesize_with_clarification' api/ tests/`
Expected: no output.

- [ ] **Step 6: Run the affected test suites**

Run: `pytest tests/test_chat_search_snippets.py tests/test_chat_citations.py tests/test_chat_memory.py tests/test_llm_unit.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add api/chat.py api/llm.py tests/test_chat_search_snippets.py
git commit -m "feat(chat-memory): replay history in send path, retire clarification bundle, record token counts"
```

---

### Task 8: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the entire backend test suite**

Run: `pytest tests/ -v`
Expected: PASS. Pay attention to `test_pageindex_agent.py`, `test_pageindex_retrieval.py`, `test_chat_citations.py`, and the `*_conversation_context.py` generation tests — none should regress, since PageIndex retrieval and the generation features were untouched.

- [ ] **Step 2: If any test fails**

Use superpowers:systematic-debugging. Do not weaken assertions to make tests pass; the history wiring must not alter retrieval behavior or citation output.

- [ ] **Step 3: Final commit (only if Step 1 required incidental fixes)**

```bash
git add -A
git commit -m "test(chat-memory): full regression pass green"
```

---

## Self-Review notes (for the implementer)

- **Spec coverage:** Task 1 = window map + estimator; Task 2 = budget formula; Task 3 = drop-oldest composer; Task 4 = linear active-branch loader; Task 5–6 = composition + per-provider seeding (hot tier, verbatim); Task 7 = clarification consolidation + depth cap + token instrumentation; Task 8 = PageIndex/no-regression guardrail. Deferred tiers (warm/retrieved/episode) and intent tags are intentionally absent.
- **Type consistency:** canonical turn shape is `{"role": str, "content": str}` everywhere; `_shape_history_gemini` is the only shaper that changes it (to `{role, parts:[{text}]}`); `_build_history_turns` returns canonical turns; new kwargs are `history_before_index: int | None` and `clarification_depth: int` on both `synthesize` and `run_agent_pageindex`.
- **Known soft spots to verify against live code while implementing:** (1) the exact return-tuple contract of `_pageindex_stream_call` for the `fake_stream` stub in Task 6 Step 1; (2) the actual local name of the returned metadata dict in Task 6 Step 3f; (3) the second clarification branch's local variable names in Task 7 Step 2; (4) the exact current-user `contents` entry shape in the Gemini branch for Task 6 Step 3e.
