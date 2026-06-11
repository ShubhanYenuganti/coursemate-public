# PageIndex for Claude & Gemini — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Also use:** `claude-api` skill (Anthropic streaming tool_use exactness) and `find-docs`/`context7` (Gemini `streamGenerateContent` function-calling shapes) before writing the provider stream-call parsers — verify event formats against current docs rather than guessing.

**Goal:** Run the PageIndex agentic loop on the user's **selected** provider (Claude via Anthropic `tool_use`, Gemini via `functionDeclarations`) instead of always falling back to OpenAI.

**Architecture:** Extract the provider-agnostic tool dispatch from `run_agent_pageindex`, add provider-specific streaming call + message-format adapters for Anthropic and Gemini, and route `synthesize` to the loop for the user's selected provider using that provider's API key.

**Tech Stack:** `api/llm.py`, OpenAI/Anthropic/Gemini REST streaming, `requests`, pytest + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-05-31-pageindex-claude-gemini-design.md` (to be written from this plan's premise) and roadmap P1/priority #1.

---

## Reality check (corrects the roadmap)

The roadmap says "Claude/Gemini fall back to legacy non-agentic RAG." **Actual behavior** (`api/llm.py::synthesize`, lines 1921–1968): when `_is_pageindex_enabled()` is true, *every* provider routes to `run_agent_pageindex`, which is hardcoded to `DEFAULT_AGENTIC_PROVIDER` (OpenAI), `DEFAULT_AGENTIC_MODEL`, and the user's **OpenAI** API key (`agentic_api_key = _get_api_key(conn, user_id, DEFAULT_AGENTIC_PROVIDER)`). So a Claude/Gemini user's selected model is **bypassed** and OpenAI answers using their OpenAI key. This plan makes the loop honor the selected provider. (Side benefit: removes the hidden hard dependency on every user having an OpenAI key.)

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `api/llm.py` | Tool dispatch extraction; Claude + Gemini stream adapters; provider routing | Modify |
| `tests/test_pageindex_agent.py` | Tests for dispatch + Claude/Gemini loops | Modify |

---

## Task 1: Extract provider-agnostic tool dispatch

**Files:**
- Modify: `api/llm.py` (the `for call in tool_calls:` body inside `run_agent_pageindex`, lines ~1697–1768)
- Test: `tests/test_pageindex_agent.py`

Goal: one pure function `_dispatch_pageindex_tool(conn, name, args, course_id, context_material_ids, grounding_refs, on_event) -> str` returning the tool-result text and appending to `grounding_refs` / emitting events. This is reused identically by all three provider loops.

- [ ] **Step 1: Write the failing test**

```python
def test_dispatch_pageindex_tool_get_page_content_appends_grounding():
    from unittest.mock import patch, MagicMock
    import llm
    grounding = []
    events = []
    rows = [{"page_number": 5, "text_content": "Hello page 5"}]
    with patch("pageindex_retrieval.get_page_content", return_value=rows):
        out = llm._dispatch_pageindex_tool(
            conn=MagicMock(), name="get_page_content",
            args={"material_id": 7, "pages": "5"},
            course_id=1, context_material_ids=[7],
            grounding_refs=grounding, on_event=events.append,
        )
    assert "Hello page 5" in out
    assert "material:7" in grounding
    assert any(e.get("tool") == "get_page_content" for e in events)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_dispatch_pageindex_tool_get_page_content_appends_grounding -v`
Expected: FAIL — `AttributeError: module 'llm' has no attribute '_dispatch_pageindex_tool'`.

- [ ] **Step 3: Implement `_dispatch_pageindex_tool`**

Move the existing per-tool logic out of the loop into a module function. It contains the `get_material_structure` / `get_page_content` / `get_related_materials` / `propose_generation` (if Generate-From-Chat landed) / fallback branches verbatim, but operating on parameters instead of closure variables:

```python
def _dispatch_pageindex_tool(conn, name, args, course_id, context_material_ids,
                             grounding_refs, on_event):
    from pageindex_retrieval import get_material_structure, get_page_content
    if name == "get_material_structure":
        return json.dumps(get_material_structure(conn, args.get("material_id")), indent=2)
    if name == "get_page_content":
        material_id = args.get("material_id")
        rows = get_page_content(conn, material_id, args.get("pages", ""))
        if rows:
            tool_result = "\n\n".join(
                f"--- Page {r['page_number']} ---\n{r['text_content'] or '[No text extracted]'}"
                for r in rows
            )
            grounding_refs.append(f"material:{material_id}")
        else:
            tool_result = "No content found for the requested pages."
        if on_event:
            on_event({"type": "tool_call", "tool": "get_page_content",
                      "material_id": material_id, "pages": args.get("pages", "")})
        return tool_result
    if name == "get_related_materials":
        from pageindex_retrieval import get_material_relations
        material_id = args.get("material_id")
        relations = get_material_relations(conn, course_id, material_id)
        # ... (move the existing formatting block here verbatim) ...
        if on_event:
            on_event({"type": "tool_call", "tool": "get_related_materials", "material_id": material_id})
        return tool_result
    return f"Unknown tool: {name}"
```

In `run_agent_pageindex`, replace the inlined branches with:
```python
            tool_result = _dispatch_pageindex_tool(
                conn, name, args, course_id, context_material_ids, grounding_refs, on_event
            )
            tool_trace.append({"tool": name, "args": args, "iteration": iteration})
            messages.append({"role": "tool", "tool_call_id": call["id"], "name": name, "content": str(tool_result)})
```

- [ ] **Step 4: Run to verify it passes + no regressions**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py -v`
Expected: all PASS (existing OpenAI-path tests still green — behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "refactor(pageindex): extract provider-agnostic tool dispatch"
```

---

## Task 2: Anthropic (Claude) streaming tool-loop adapter

**Files:**
- Modify: `api/llm.py` (add `_pageindex_tools_anthropic()`, `_pageindex_stream_call_claude()`)
- Test: `tests/test_pageindex_agent.py`

> Use the `claude-api` skill to confirm the streaming event sequence (`message_start`, `content_block_start` for `tool_use`, `input_json_delta`, `message_delta` with `stop_reason="tool_use"`) and the `tool_result` block shape. Include prompt caching on the system + tools per that skill.

Anthropic differences vs OpenAI: tools are `[{"name","description","input_schema"}]`; assistant tool calls arrive as `content` blocks `{"type":"tool_use","id","name","input"}`; tool outputs are sent back as a user message with `{"type":"tool_result","tool_use_id","content"}` blocks; `stop_reason == "tool_use"` signals more tools.

- [ ] **Step 1: Write the failing test (mock the Anthropic stream)**

```python
def _stub_anthropic_tool_use(tool_id, name, input_obj):
    resp = MagicMock(); resp.status_code = 200
    payload = json.dumps(input_obj)
    resp.iter_lines.return_value = iter([
        b'event: content_block_start',
        b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"' + tool_id.encode() + b'","name":"' + name.encode() + b'","input":{}}}',
        b'event: content_block_delta',
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":' + json.dumps(payload).encode() + b'}}',
        b'event: message_delta',
        b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
    ])
    return resp


def test_pageindex_claude_loop_calls_tool_then_answers():
    import copy
    from llm import run_agent_pageindex
    events = []
    first = _stub_anthropic_tool_use("toolu_1", "get_page_content", {"material_id": 7, "pages": "5"})
    # second call returns a final text answer with no tools
    final = MagicMock(); final.status_code = 200
    final.iter_lines.return_value = iter([
        b'event: content_block_delta',
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Page 5 says hello."}}',
        b'event: message_delta',
        b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
    ])
    with patch("llm.requests.post", side_effect=[copy.deepcopy(first), copy.deepcopy(final)]), \
         patch("llm.get_course_routing_index", return_value=[]), \
         patch("llm._format_routing_index_block", return_value="<course_materials></course_materials>"), \
         patch("pageindex_retrieval.get_page_content", return_value=[{"page_number":5,"text_content":"hello"}]):
        text, grounding, *_ = run_agent_pageindex(
            conn=MagicMock(), user_message="q", model="claude-sonnet-4-6", api_key="sk-ant",
            chat_id=1, course_id=7, context_material_ids=[7], on_event=events.append,
            provider="claude",
        )
    assert "material:7" in grounding
    assert "hello" not in text  # tool output not echoed raw
    assert any(e.get("tool") == "get_page_content" for e in events)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_pageindex_claude_loop_calls_tool_then_answers -v`
Expected: FAIL — `run_agent_pageindex` has no `provider` parameter / no Claude path.

- [ ] **Step 3: Add the Anthropic tools formatter and stream call**

```python
def _pageindex_tools_anthropic(openai_tools):
    """Convert the OpenAI-format tool list to Anthropic input_schema format."""
    out = []
    for t in openai_tools:
        fn = t["function"]
        out.append({"name": fn["name"], "description": fn["description"],
                    "input_schema": fn["parameters"]})
    return out


def _pageindex_stream_call_claude(api_key, model, system, messages, tools, on_event):
    """One streaming Anthropic call. Returns (assistant_content_blocks, stop_reason).
    Emits {"type":"text","chunk":...} for text_delta events."""
    body = {
        "model": model, "max_tokens": 2048, "system": system,
        "messages": messages, "tools": _pageindex_tools_anthropic(tools),
        "stream": True,
    }
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json=body, stream=True, timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    blocks = {}          # index -> {"type","id","name","input_json"/"text"}
    stop_reason = None
    for raw in resp.iter_lines():
        if not raw: continue
        line = raw.decode() if isinstance(raw, bytes) else raw
        if not line.startswith("data: "): continue
        evt = json.loads(line[6:])
        t = evt.get("type")
        if t == "content_block_start":
            cb = evt["content_block"]; idx = evt["index"]
            blocks[idx] = {"type": cb["type"], "id": cb.get("id"), "name": cb.get("name"),
                           "input_json": "", "text": ""}
        elif t == "content_block_delta":
            d = evt["delta"]; idx = evt["index"]
            if d["type"] == "input_json_delta":
                blocks[idx]["input_json"] += d.get("partial_json", "")
            elif d["type"] == "text_delta":
                blocks[idx]["text"] += d["text"]
                if on_event: on_event({"type": "text", "chunk": d["text"]})
        elif t == "message_delta":
            stop_reason = evt.get("delta", {}).get("stop_reason", stop_reason)
    ordered = [blocks[i] for i in sorted(blocks)]
    return ordered, stop_reason
```

- [ ] **Step 4: Add a Claude loop branch in `run_agent_pageindex`**

Add a `provider: str = "openai"` parameter. When `provider == "claude"`, run an Anthropic-shaped loop reusing `_dispatch_pageindex_tool`:
- System = `system_content` (the routing block) — passed as Anthropic `system`, not a message.
- `messages` starts `[{"role":"user","content": user_message}]`.
- Each iteration: call `_pageindex_stream_call_claude`; collect `tool_use` blocks; if none / `stop_reason != "tool_use"`, the concatenated `text` blocks are the final answer (parse via `_parse_synthesis_json`), break.
- For each `tool_use` block: `args = json.loads(block["input_json"] or "{}")`, `result = _dispatch_pageindex_tool(...)`. Append the assistant turn (`{"role":"assistant","content": <the tool_use blocks>}`) then a user turn with `tool_result` blocks: `{"role":"user","content":[{"type":"tool_result","tool_use_id": block["id"],"content": str(result)}]}`.
- Keep the same `tool_trace` / `grounding_refs` / forced-synthesis tail.

Structure the loop so the OpenAI path (existing `_stream_with_filter`) and the Claude path share the tail. Keep the return tuple identical.

- [ ] **Step 5: Run to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_pageindex_claude_loop_calls_tool_then_answers -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(pageindex): Anthropic tool_use streaming loop for Claude"
```

---

## Task 3: Gemini streaming function-call loop adapter

**Files:**
- Modify: `api/llm.py` (add `_pageindex_tools_gemini()`, `_pageindex_stream_call_gemini()`, Gemini branch)
- Test: `tests/test_pageindex_agent.py`

> Use `find-docs`/`context7` for the exact Gemini `streamGenerateContent` chunk shape and `functionCall`/`functionResponse` field names before finalizing the parser.

Gemini differences: tools are `[{"functionDeclarations":[{"name","description","parameters"}]}]`; the model emits `candidates[].content.parts[].functionCall = {name, args}`; tool outputs go back as a `{"role":"function","parts":[{"functionResponse":{"name","response":{...}}}]}` (or `role:"user"` with `functionResponse` parts per current API); system prompt via `system_instruction`.

- [ ] **Step 1: Write the failing test (mock the Gemini stream)**

```python
def _stub_gemini_function_call(name, args):
    resp = MagicMock(); resp.status_code = 200
    chunk = {"candidates":[{"content":{"parts":[{"functionCall":{"name":name,"args":args}}]}}]}
    resp.iter_lines.return_value = iter([b'data: ' + json.dumps(chunk).encode()])
    return resp


def test_pageindex_gemini_loop_calls_tool_then_answers():
    import copy
    from llm import run_agent_pageindex
    events = []
    first = _stub_gemini_function_call("get_page_content", {"material_id":7,"pages":"5"})
    final = MagicMock(); final.status_code = 200
    final.iter_lines.return_value = iter([
        b'data: ' + json.dumps({"candidates":[{"content":{"parts":[{"text":"Page 5 says hi."}]}}]}).encode()
    ])
    with patch("llm.requests.post", side_effect=[copy.deepcopy(first), copy.deepcopy(final)]), \
         patch("llm.get_course_routing_index", return_value=[]), \
         patch("llm._format_routing_index_block", return_value="<course_materials></course_materials>"), \
         patch("pageindex_retrieval.get_page_content", return_value=[{"page_number":5,"text_content":"hi"}]):
        text, grounding, *_ = run_agent_pageindex(
            conn=MagicMock(), user_message="q", model="gemini-2.5-flash", api_key="g-key",
            chat_id=1, course_id=7, context_material_ids=[7], on_event=events.append,
            provider="gemini",
        )
    assert "material:7" in grounding
    assert any(e.get("tool") == "get_page_content" for e in events)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_pageindex_gemini_loop_calls_tool_then_answers -v`
Expected: FAIL — no Gemini path.

- [ ] **Step 3: Implement the Gemini tools formatter + stream call + loop branch**

```python
def _pageindex_tools_gemini(openai_tools):
    decls = [{"name": t["function"]["name"], "description": t["function"]["description"],
              "parameters": t["function"]["parameters"]} for t in openai_tools]
    return [{"functionDeclarations": decls}]


def _pageindex_stream_call_gemini(api_key, model, system, contents, tools, on_event):
    """One streaming Gemini call. Returns (parts, has_function_call).
    Emits text_delta via on_event."""
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:streamGenerateContent?alt=sse&key={api_key}")
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "tools": _pageindex_tools_gemini(tools),
    }
    resp = requests.post(url, json=body, stream=True, timeout=_TIMEOUT)
    resp.raise_for_status()
    parts, has_fc = [], False
    for raw in resp.iter_lines():
        if not raw: continue
        line = raw.decode() if isinstance(raw, bytes) else raw
        if not line.startswith("data: "): continue
        chunk = json.loads(line[6:])
        for cand in chunk.get("candidates", []):
            for p in cand.get("content", {}).get("parts", []):
                if "functionCall" in p:
                    has_fc = True; parts.append(p)
                elif "text" in p:
                    parts.append(p)
                    if on_event: on_event({"type": "text", "chunk": p["text"]})
    return parts, has_fc
```

Gemini loop branch in `run_agent_pageindex` (when `provider == "gemini"`):
- `contents = [{"role":"user","parts":[{"text": user_message}]}]`.
- Each iteration: `parts, has_fc = _pageindex_stream_call_gemini(...)`. If not `has_fc`, the concatenated text parts → final answer (`_parse_synthesis_json`), break.
- For each `functionCall` part: `args = fc["args"]`, `result = _dispatch_pageindex_tool(...)`. Append model turn `{"role":"model","parts": parts}` then a function-response turn:
  `{"role":"user","parts":[{"functionResponse":{"name": fc["name"],"response":{"result": str(result)}}}]}`.
- Shared tail unchanged.

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_pageindex_gemini_loop_calls_tool_then_answers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(pageindex): Gemini functionCall streaming loop"
```

---

## Task 4: Route `synthesize` to the selected provider

**Files:**
- Modify: `api/llm.py` (`synthesize`, lines ~1921–1968)
- Test: `tests/test_pageindex_agent.py`

- [ ] **Step 1: Write the failing test**

```python
def test_synthesize_pageindex_routes_to_selected_provider():
    from llm import synthesize
    from unittest.mock import patch, MagicMock
    captured = {}
    def fake_loop(**kwargs):
        captured.update(kwargs)
        return ("ans", ["material:1"], [], {}, "sum", [], None)
    with patch("llm._is_pageindex_enabled", return_value=True), \
         patch("llm._get_api_key", return_value="key-for-provider"), \
         patch("llm.run_agent_pageindex", side_effect=fake_loop):
        synthesize(MagicMock(), 1, "claude", "claude-sonnet-4-6", "q", [], chat_id=5)
    assert captured["provider"] == "claude"
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["api_key"] == "key-for-provider"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_synthesize_pageindex_routes_to_selected_provider -v`
Expected: FAIL — current code passes `DEFAULT_AGENTIC_MODEL` + OpenAI key, no `provider`.

- [ ] **Step 3: Update the PageIndex routing in `synthesize`**

Replace the hardcoded OpenAI wiring (lines ~1923, ~1948–1958) with selected-provider wiring:

```python
        agentic_api_key = selected_provider_api_key
        pageindex_model = ai_model
        # ... course_id lookup unchanged ...
        (text, grounding_refs, tool_trace, metadata, msg_summary, follow_ups, clarifying_question) = run_agent_pageindex(
            conn=conn,
            user_message=user_message,
            model=pageindex_model,
            api_key=agentic_api_key,
            chat_id=chat_id,
            course_id=pageindex_course_id,
            context_material_ids=material_scope,
            on_event=on_event,
            provider=ai_provider,
        )
```

- [ ] **Step 4: Run to verify it passes + full file green**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(pageindex): route agentic loop to user's selected provider"
```

---

## Task 5: End-to-end eval across providers

- [ ] **Step 1: Run the existing eval harness for each provider**

Use `Skill pageindex-chat-eval` (or `tests/playwright/pageindex_chat_eval.py`) against the same course/questions with: an OpenAI model (baseline), a Claude model, and a Gemini model.
Expected: all questions answered with page-level citations; live retrieval-status events appear for all three.

- [ ] **Step 2: Compare answer quality vs the OpenAI baseline**

Record pass/fail per provider. If Claude/Gemini parsing diverges (e.g. missing citations), capture the failing transcript and convert it into a regression test before fixing.

- [ ] **Step 3: Gate rollout**

PageIndex remains behind `_is_pageindex_enabled()`. Do not enable Claude/Gemini in production until the eval passes for those providers.

---

## Self-Review Notes

- **Spec coverage:** all three providers run the loop with shared tools (Tasks 1–4) ✓; identical retrieved content via shared `_dispatch_pageindex_tool` (Task 1) ✓; live `tool_call`/`text` events for all providers (Tasks 2–3 emit via `on_event`) ✓; selected provider + key honored (Task 4) ✓; eval before rollout (Task 5) ✓.
- **Removes hidden dependency:** users no longer need an OpenAI key for PageIndex when they've selected Claude/Gemini.
- **Type consistency:** `_dispatch_pageindex_tool` signature identical across loops; `run_agent_pageindex` gains `provider` (default `"openai"`, preserving existing callers); return tuple unchanged.
- **External-API risk (flagged):** Anthropic/Gemini streaming event shapes must be verified against current docs via the `claude-api` and `find-docs` skills — the parser code here is structurally correct but the exact field names should be confirmed before merging.
```
