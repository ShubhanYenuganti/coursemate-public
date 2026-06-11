# Web Search User Toggle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give users a per-chat web-search toggle in the compose bar that controls whether the assistant may use the web_search tool.

**Architecture:** A compose-bar toggle (persisted in `localStorage`) sends `web_search_enabled` in the `stream_send`/`stream_edit` payload. The backend threads it into `synthesize` and the PageIndex loop, which only offers the `web_search` tool when the server env flag AND the per-chat flag are both on.

**Tech Stack:** React (`src/ChatTab.jsx`), Python (`api/chat.py`, `api/llm.py`, `api/tools.py`), pytest.

**Spec:** `docs/superpowers/specs/2026-05-31-web-search-toggle-design.md` (roadmap P1).

**Dependency:** Roadmap priority #1 (PageIndex for Claude/Gemini). `web_search` currently exists only in the legacy `run_agent_openai` loop (`api/llm.py` line 1064), **not** in `run_agent_pageindex` (the production path). This plan adds it to the PageIndex loop, so it benefits from — and is most coherent after — the all-providers loop work.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/ChatTab.jsx` | Compose-bar toggle, localStorage, payload field | Modify |
| `api/chat.py` | Read `web_search_enabled`, pass to `synthesize` | Modify |
| `api/llm.py` | Thread flag into `run_agent_pageindex`; offer `web_search` tool conditionally | Modify |
| `tests/test_pageindex_agent.py` | Tool-gating test | Modify |

---

## Task 1: Backend — gate `web_search` in the PageIndex loop

**Files:**
- Modify: `api/llm.py` (`run_agent_pageindex` tools list ~line 1540; dispatch ~line 1697; `synthesize` ~line 1948)
- Modify: `api/tools.py` (reuse existing `execute_web_search`)
- Test: `tests/test_pageindex_agent.py`

- [ ] **Step 1: Write the failing test**

```python
def test_pageindex_offers_web_search_only_when_flag_on(monkeypatch):
    import llm
    monkeypatch.setattr(llm, "_is_enabled", lambda k, default=False: k == "AGENTIC_WEB_SEARCH_ENABLED")
    tools_on = llm._pageindex_tool_list(web_search_enabled=True)
    tools_off = llm._pageindex_tool_list(web_search_enabled=False)
    names_on = {t["function"]["name"] for t in tools_on}
    names_off = {t["function"]["name"] for t in tools_off}
    assert "web_search" in names_on
    assert "web_search" not in names_off
    assert "get_page_content" in names_off  # base tools always present
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_pageindex_offers_web_search_only_when_flag_on -v`
Expected: FAIL — no `_pageindex_tool_list`.

- [ ] **Step 3: Extract the tool list into a helper with the gate**

In `api/llm.py`, factor the `run_agent_pageindex` tools list into:

```python
def _pageindex_tool_list(web_search_enabled: bool = False) -> list:
    tools = [
        # ... existing get_material_structure, get_page_content, get_related_materials ...
        # (and propose_generation if that change landed)
    ]
    if web_search_enabled and _is_enabled("AGENTIC_WEB_SEARCH_ENABLED"):
        tools.append({
            "type": "function",
            "function": {
                "name": "web_search",
                "description": ("Search the web for information not covered by course "
                                "materials. Use when page content is insufficient."),
                "parameters": {"type": "object",
                               "properties": {"query": {"type": "string"}},
                               "required": ["query"]},
            },
        })
    return tools
```

Have `run_agent_pageindex` accept `web_search_enabled: bool = False` and build `tools = _pageindex_tool_list(web_search_enabled)`.

- [ ] **Step 4: Add the `web_search` dispatch branch**

In `_dispatch_pageindex_tool` (from the PageIndex Claude/Gemini plan; if that hasn't landed, add inside the existing dispatch loop), add:

```python
    if name == "web_search":
        from tools import execute_web_search
        if on_event:
            on_event({"type": "web_search_start", "query": args.get("query", "")})
        result = execute_web_search(conn, args.get("query", ""))
        return result.get("text", "")
```

- [ ] **Step 5: Thread the flag through `synthesize`**

Add `web_search_enabled: bool = False` to `synthesize`'s signature and pass it into the `run_agent_pageindex(...)` call.

- [ ] **Step 6: Run to verify it passes + no regressions**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(web-search): gate web_search tool in pageindex loop by per-request flag"
```

---

## Task 2: Backend — read `web_search_enabled` in chat handlers

**Files:**
- Modify: `api/chat.py` (`_send_message` near line 860; `_edit_message` near line 1311)

- [ ] **Step 1: Extract and thread the flag**

In both the send and edit handlers, after parsing the body:

```python
        web_search_enabled = bool(data.get('web_search_enabled', False))
```

Pass `web_search_enabled=web_search_enabled` into the `synthesize(...)` call in each handler.

- [ ] **Step 2: Build/lint check**

Run: `cd /Users/shubhan/OneShotCourseMate && python -c "import ast; ast.parse(open('api/chat.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add api/chat.py
git commit -m "feat(web-search): accept web_search_enabled in chat send/edit"
```

---

## Task 3: Frontend — compose-bar toggle

**Files:**
- Modify: `src/ChatTab.jsx` (compose bar; send payloads at lines ~2008 and ~2145)

- [ ] **Step 1: Locate the compose bar and send payloads**

Run:
`cd /Users/shubhan/OneShotCourseMate && rg -n "context_material_ids: contextIds|ai_provider: selectedModel|compose|textarea|placeholder=\"|Send\b" src/ChatTab.jsx | head`
Confirm the two `fetch('/api/chat', ...)` send/edit bodies (≈ lines 2008 and 2145) and the compose-bar JSX where the send button lives.

- [ ] **Step 2: Add toggle state with persistence**

Near the other ChatTab state (line ~1283):

```jsx
const [webSearchEnabled, setWebSearchEnabled] = useState(
  () => localStorage.getItem('chat_web_search_enabled') === '1'
);
function toggleWebSearch() {
  setWebSearchEnabled((v) => {
    const next = !v;
    localStorage.setItem('chat_web_search_enabled', next ? '1' : '0');
    return next;
  });
}
```

- [ ] **Step 3: Add the toggle button to the compose bar**

Next to the existing compose actions (image attach, send), add a globe button:

```jsx
<button
  type="button"
  onClick={toggleWebSearch}
  title={webSearchEnabled ? 'Web search on' : 'Web search off'}
  aria-pressed={webSearchEnabled}
  className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors ${
    webSearchEnabled
      ? 'border-indigo-400 text-indigo-600 bg-indigo-50'
      : 'border-gray-200 text-gray-400 hover:border-indigo-400 hover:text-indigo-600'
  }`}
>
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20" />
  </svg>
</button>
```

- [ ] **Step 4: Include the flag in both send payloads**

In each send/edit `fetch('/api/chat', ...)` body (lines ~2008 and ~2145), add:

```jsx
          web_search_enabled: webSearchEnabled,
```

- [ ] **Step 5: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(web-search): compose-bar toggle persisted per browser"
```

---

## Task 4: End-to-end verification

- [ ] **Step 1: Env prerequisites**

Ensure `AGENTIC_WEB_SEARCH_ENABLED=true` and `TAVILY_API_KEY` are set in the environment being tested.

- [ ] **Step 2: Manual flow**

1. Toggle web search ON → ask a question requiring external info → confirm `web_search_start` status appears and web result sources show in the panel.
2. Toggle OFF → same question → confirm Tavily is not called (no `web_search_start`).
3. Refresh the page → toggle state persists.

- [ ] **Step 3: Provider note**

Per the PageIndex Claude/Gemini plan, the toggle now works for whichever provider runs the loop. Before that lands, it is effective on the OpenAI-run loop only.

---

## Self-Review Notes

- **Spec coverage:** compose-bar toggle + persistence (Task 3) ✓; payload field (Task 3) ✓; backend threads flag (Task 2) ✓; honored only when env AND flag on (Task 1) ✓; sources shown (existing `web_search_start`/web-result events) ✓.
- **Key correction over the roadmap:** the toggle must wire `web_search` into the **PageIndex** loop (the production path), not just the legacy OpenAI loop where it already exists — Task 1 does this.
- **Type consistency:** `web_search_enabled` boolean threaded uniformly (frontend payload → `data.get` → `synthesize` kwarg → `run_agent_pageindex` → `_pageindex_tool_list`).
- **YAGNI:** per-browser localStorage, not a server-side per-user preference (out of scope).
```
