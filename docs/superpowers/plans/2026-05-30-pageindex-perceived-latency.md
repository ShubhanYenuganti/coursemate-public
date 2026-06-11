# PageIndex Perceived-Latency Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pageindex chat responses feel fast to the end-user by (1) showing retrieval progress immediately and (2) pre-fetching the most likely pages before the agentic loop starts.

**Architecture:** Phase 1 is pure frontend: drive a status line from existing `tool_call` SSE events so the user sees activity within ~1.5s of sending. Phase 2 adds a PostgreSQL FTS pre-fetch step in `run_agent_pageindex` that injects the top-3 likely pages into the system prompt before the agentic loop, letting the model answer on the first iteration without tool calls for typical questions.

**Tech Stack:** React (frontend state/JSX), Python (backend), PostgreSQL FTS (`to_tsvector` / `plainto_tsquery`), pytest

---

## File map

| File | Change |
|------|--------|
| `src/ChatTab.jsx` | Add `retrievalStatus` state; drive it from `tool_call` / `text` / `error` / `done` events; render inline status line |
| `api/services/query/pageindex_retrieval.py` | Add `prefetch_pages_for_query(conn, material_ids, query, top_k)` |
| `api/llm.py` | Add `_format_prefetch_block(pages)`; call pre-fetch and inject block in `run_agent_pageindex` |
| `tests/test_pageindex_retrieval.py` | Tests for `prefetch_pages_for_query` |
| `tests/test_pageindex_agent.py` | Test that pre-loaded block appears in system prompt when pre-fetch returns pages |

---

## Task 1 — Retrieval status state + event wiring

**Files:**
- Modify: `src/ChatTab.jsx`

- [ ] **Step 1: Add `retrievalStatus` state near other UI state declarations (~line 1263)**

  Find the block of `useState` calls near `const [sending, setSending] = useState(false)` and add:

  ```jsx
  const [retrievalStatus, setRetrievalStatus] = useState(null);
  ```

- [ ] **Step 2: Set initial status when the user sends a message**

  In the `handleSendMessage` function (or equivalent), right after `setSending(true)` (~line 1873), add:

  ```jsx
  setRetrievalStatus('Searching course materials…');
  ```

- [ ] **Step 3: Clear status in the send handler's catch/finally blocks**

  Every early-exit path in the send handler calls `setSending(false)`. Add `setRetrievalStatus(null)` alongside each:

  ```jsx
  // image upload failure block (~line 1925):
  setSending(false);
  sendingRef.current = false;
  setRetrievalStatus(null);   // add this

  // post-loop finally (~line 1997):
  setSending(false);
  sendingRef.current = false;
  setRetrievalStatus(null);   // add this
  ```

- [ ] **Step 4: Update `handleStreamEvent` to drive the status from SSE events**

  In `handleStreamEvent` at `src/ChatTab.jsx`, update the switch to handle `tool_call` events and clear the status when text starts or the stream ends:

  ```jsx
  function handleStreamEvent(evt, { tempId, tempAssistantId, chatId, setActiveConvFn }) {
    switch (evt.type) {
      case 'user_message':
        setMessages((prev) => [...prev.filter((m) => m.id !== tempId), evt.message]);
        break;
      case 'tool_call':
        if (evt.tool === 'get_page_content') {
          const mat = materials.find((m) => m.id === evt.material_id);
          const name = mat
            ? mat.name.replace(/\.pdf$/i, '').slice(0, 30)
            : `Material ${evt.material_id}`;
          setRetrievalStatus(`Reading ${name}, pages ${evt.pages}…`);
        }
        break;
      case 'text':
        setRetrievalStatus(null);
        if (!evt.chunk) break;
        setMessages((prev) => {
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId ? { ...m, content: m.content + evt.chunk } : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: evt.chunk }];
        });
        break;
      case 'done':
        setRetrievalStatus(null);
        setMessages((prev) => {
          const withoutTemp = prev.filter(
            (m) => m.id !== tempId && m.id !== tempAssistantId && m.id !== evt.user_message?.id
          );
          return [...withoutTemp, evt.user_message, evt.assistant_message];
        });
        setChats((prev) => prev.map((c) =>
          c.id === chatId
            ? {
                ...c,
                last_message_at: evt.assistant_message?.created_at,
                message_count: (c.message_count || 0) + 2,
                ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
              }
            : c
        ));
        setSending(false);
        sendingRef.current = false;
        break;
      case 'error':
        setRetrievalStatus(null);
        setSending(false);
        sendingRef.current = false;
        setMessages((prev) => prev.filter((m) => m.id !== tempId && m.id !== tempAssistantId));
        break;
      default:
        break;
    }
  }
  ```

- [ ] **Step 5: Verify frontend builds without errors**

  ```bash
  cd /Users/shubhan/OneShotCourseMate
  npm run build --prefix . 2>&1 | tail -5
  ```

  Expected: no TypeScript/JSX errors. (Vite build output, last line should be `✓ built in ...` or similar.)

---

## Task 2 — Render the inline status line

**Files:**
- Modify: `src/ChatTab.jsx` (~line 2835)

- [ ] **Step 1: Insert status line between message list and scroll anchor**

  Find the line `<div ref={messagesEndRef} />` (~line 2836) and add the status line immediately before it:

  ```jsx
          {sending && retrievalStatus && (
            <p className="px-4 pb-1 text-sm italic text-gray-400">{retrievalStatus}</p>
          )}
          <div ref={messagesEndRef} />
  ```

- [ ] **Step 2: Manual smoke test**

  With both dev servers running (`lsof -i :3001 -i :5173 | grep LISTEN`), open `http://localhost:5173`, navigate to a CS 118 chat, select the three routing lecture PDFs, and send a question like "What is link-state routing?".

  Observe:
  - "Searching course materials…" appears ~1.5s after send
  - Transitions to "Reading Lecture-14-RoutingAlgorithm, pages X–Y…" when a page is fetched
  - Disappears as the streaming answer starts building
  - No layout shift when it disappears

- [ ] **Step 3: Commit Phase 1**

  ```bash
  git add src/ChatTab.jsx
  git commit -m "feat(chat): show retrieval status line during pageindex responses"
  ```

---

## Task 3 — `prefetch_pages_for_query` in pageindex_retrieval.py

**Files:**
- Modify: `api/services/query/pageindex_retrieval.py`
- Test: `tests/test_pageindex_retrieval.py`

- [ ] **Step 1: Write the failing tests first**

  Add to `tests/test_pageindex_retrieval.py`:

  ```python
  from unittest.mock import MagicMock
  import json

  def _make_conn(rows):
      """Return a mock conn whose cursor().fetchall() returns rows."""
      conn = MagicMock()
      cursor = MagicMock()
      cursor.fetchall.return_value = rows
      conn.cursor.return_value = cursor
      return conn


  def test_prefetch_pages_returns_matching_rows():
      from pageindex_retrieval import prefetch_pages_for_query
      rows = [
          {"material_id": 10, "page_number": 5, "text_content": "link-state uses Dijkstra"},
          {"material_id": 10, "page_number": 7, "text_content": "distance-vector uses Bellman-Ford"},
      ]
      conn = _make_conn(rows)
      result = prefetch_pages_for_query(conn, [10], "link-state routing", top_k=3)
      assert len(result) == 2
      assert result[0]["material_id"] == 10
      assert result[0]["page_number"] == 5
      assert "link-state" in result[0]["text_content"]


  def test_prefetch_pages_empty_material_ids():
      from pageindex_retrieval import prefetch_pages_for_query
      conn = MagicMock()
      result = prefetch_pages_for_query(conn, [], "anything", top_k=3)
      assert result == []
      conn.cursor.assert_not_called()


  def test_prefetch_pages_empty_query():
      from pageindex_retrieval import prefetch_pages_for_query
      conn = MagicMock()
      result = prefetch_pages_for_query(conn, [10], "   ", top_k=3)
      assert result == []
      conn.cursor.assert_not_called()


  def test_prefetch_pages_db_error_returns_empty():
      from pageindex_retrieval import prefetch_pages_for_query
      conn = MagicMock()
      cursor = MagicMock()
      cursor.execute.side_effect = Exception("DB error")
      conn.cursor.return_value = cursor
      result = prefetch_pages_for_query(conn, [10], "routing", top_k=3)
      assert result == []
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```bash
  cd /Users/shubhan/OneShotCourseMate/tests
  python3 -m pytest test_pageindex_retrieval.py::test_prefetch_pages_returns_matching_rows \
      test_pageindex_retrieval.py::test_prefetch_pages_empty_material_ids \
      test_pageindex_retrieval.py::test_prefetch_pages_empty_query \
      test_pageindex_retrieval.py::test_prefetch_pages_db_error_returns_empty -v
  ```

  Expected: `ImportError: cannot import name 'prefetch_pages_for_query'`

- [ ] **Step 3: Implement `prefetch_pages_for_query`**

  Add to the end of `api/services/query/pageindex_retrieval.py`:

  ```python
  def prefetch_pages_for_query(
      conn, material_ids: list[int], query: str, top_k: int = 3
  ) -> list[dict]:
      """Return up to top_k pages most relevant to query via PostgreSQL FTS.

      Uses ts_rank over text_content and section_name. Returns empty list on
      empty inputs or any DB error so callers degrade gracefully.
      """
      if not material_ids or not query.strip():
          return []
      cursor = conn.cursor()
      try:
          cursor.execute(
              """SELECT material_id, page_number, text_content
                 FROM material_page_text
                 WHERE material_id = ANY(%s)
                   AND to_tsvector('english',
                         coalesce(text_content, '') || ' ' || coalesce(section_name, ''))
                       @@ plainto_tsquery('english', %s)
                 ORDER BY ts_rank(
                     to_tsvector('english',
                         coalesce(text_content, '') || ' ' || coalesce(section_name, '')),
                     plainto_tsquery('english', %s)
                 ) DESC
                 LIMIT %s""",
              (material_ids, query, query, top_k),
          )
          rows = cursor.fetchall()
      except Exception:
          rows = []
      finally:
          cursor.close()
      return [dict(r) for r in rows]
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```bash
  cd /Users/shubhan/OneShotCourseMate/tests
  python3 -m pytest test_pageindex_retrieval.py -v
  ```

  Expected: all retrieval tests pass (including existing ones).

---

## Task 4 — Wire pre-fetch into `run_agent_pageindex`

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_pageindex_agent.py`

- [ ] **Step 1: Write the failing integration tests**

  Add to `tests/test_pageindex_agent.py`:

  ```python
  def test_run_agent_pageindex_injects_prefetch_block_when_pages_found():
      """Pre-fetched pages appear as <pre_loaded_pages> in the system prompt."""
      from llm import run_agent_pageindex

      conn = MagicMock()
      captured = {}

      def fake_post(url, headers=None, json=None, timeout=None, stream=None):
          captured["payload"] = json
          return _stub_openai_response_no_tools("answer")

      routing_rows = [{"material_id": 10, "title": "L1", "doc_type": "lecture",
                       "page_count": 5, "summary": "s", "tags": [], "sections": []}]
      prefetch_rows = [{"material_id": 10, "page_number": 3, "text_content": "pre-loaded text"}]

      with patch("llm.requests.post", side_effect=fake_post), \
           patch("pageindex_retrieval.get_course_routing_index", return_value=routing_rows), \
           patch("pageindex_retrieval.prefetch_pages_for_query", return_value=prefetch_rows):
          run_agent_pageindex(conn=conn, user_message="Q?", model="gpt-4o-mini",
                              api_key="sk-test", chat_id=None, course_id=7,
                              context_material_ids=[10])

      system_content = captured["payload"]["messages"][0]["content"]
      assert "<pre_loaded_pages>" in system_content
      assert "pre-loaded text" in system_content
      assert "Material 10, page 3" in system_content


  def test_run_agent_pageindex_no_prefetch_block_when_empty():
      """No <pre_loaded_pages> block when pre-fetch returns nothing."""
      from llm import run_agent_pageindex

      conn = MagicMock()
      captured = {}

      def fake_post(url, headers=None, json=None, timeout=None, stream=None):
          captured["payload"] = json
          return _stub_openai_response_no_tools("answer")

      routing_rows = [{"material_id": 10, "title": "L1", "doc_type": "lecture",
                       "page_count": 5, "summary": "s", "tags": [], "sections": []}]

      with patch("llm.requests.post", side_effect=fake_post), \
           patch("pageindex_retrieval.get_course_routing_index", return_value=routing_rows), \
           patch("pageindex_retrieval.prefetch_pages_for_query", return_value=[]):
          run_agent_pageindex(conn=conn, user_message="Q?", model="gpt-4o-mini",
                              api_key="sk-test", chat_id=None, course_id=7,
                              context_material_ids=[10])

      system_content = captured["payload"]["messages"][0]["content"]
      assert "<pre_loaded_pages>" not in system_content
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```bash
  cd /Users/shubhan/OneShotCourseMate/tests
  python3 -m pytest test_pageindex_agent.py::test_run_agent_pageindex_injects_prefetch_block_when_pages_found \
      test_pageindex_agent.py::test_run_agent_pageindex_no_prefetch_block_when_empty -v
  ```

  Expected: `AssertionError` — `<pre_loaded_pages>` not yet in system prompt.

- [ ] **Step 3: Add `_format_prefetch_block` helper to `api/llm.py`**

  Place this immediately after `_format_routing_index_block` (search for that function name to find the right location):

  ```python
  def _format_prefetch_block(pages: list[dict]) -> str:
      lines = [
          "<pre_loaded_pages>",
          "These pages were pre-loaded based on your question. "
          "Answer directly from them if they contain what you need; "
          "use get_page_content only for additional pages.",
      ]
      for p in pages:
          lines.append(f"\n[Material {p['material_id']}, page {p['page_number']}]")
          lines.append(p.get("text_content") or "")
      lines.append("</pre_loaded_pages>")
      return "\n".join(lines)
  ```

- [ ] **Step 4: Call pre-fetch and inject block in `run_agent_pageindex`**

  In `run_agent_pageindex`, the import block and system prompt construction are at ~line 1494. Add `prefetch_pages_for_query` to the existing local import and inject the block:

  ```python
      from pageindex_retrieval import (
          get_course_routing_index,
          get_material_structure,
          get_page_content,
          prefetch_pages_for_query,   # add this
      )
  ```

  Then replace the `system_content` construction (~line 1565–1574):

  ```python
      routing_materials = get_course_routing_index(
          conn, course_id, context_material_ids or None
      )
      routing_block = _format_routing_index_block(routing_materials)

      prefetched = prefetch_pages_for_query(
          conn,
          material_ids=context_material_ids or [m["material_id"] for m in routing_materials],
          query=user_message,
          top_k=3,
      )
      pre_block = _format_prefetch_block(prefetched) + "\n\n" if prefetched else ""

      system_content = (
          PAGEINDEX_SYSTEM_PROMPT
          + "\n\n"
          + pre_block
          + routing_block
          + "\n\nUse the material IDs above when calling get_material_structure or get_page_content."
      )
  ```

- [ ] **Step 5: Run all tests**

  ```bash
  cd /Users/shubhan/OneShotCourseMate/tests
  python3 -m pytest test_pageindex_agent.py test_pageindex_retrieval.py test_chat_citations.py -q
  ```

  Expected: all tests pass (31+ passing).

- [ ] **Step 6: Commit Phase 2**

  ```bash
  git add api/services/query/pageindex_retrieval.py api/llm.py \
      tests/test_pageindex_retrieval.py tests/test_pageindex_agent.py
  git commit -m "feat(pageindex): pre-fetch top pages via FTS before agentic loop"
  ```

---

## Task 5 — Live eval verification

- [ ] **Step 1: Restart API server with auth bypass**

  ```bash
  kill $(lsof -ti :3001) 2>/dev/null; sleep 1
  DEV_BYPASS_AUTH=true python3 dev_server.py &>/tmp/dev_server.log &
  sleep 3
  python3 -c "import urllib.request, json; r = urllib.request.urlopen('http://localhost:3001/api/auth'); print(json.loads(r.read())['user']['email'])"
  ```

  Expected: `yrshubhan@gmail.com`

- [ ] **Step 2: Run the Playwright eval**

  ```bash
  cd /Users/shubhan/OneShotCourseMate
  python3 tests/playwright/pageindex_chat_eval.py
  ```

  Expected: 10 questions answered. Compare `latency_js_s` per question against the streaming baseline in `tests/pageindex_eval/playwright_chat_eval_20260530_154211.json`.

  Key signals that pre-fetch is working:
  - Questions where `n_tc == 0` in the SSE timeline (no tool calls — model answered from pre-loaded pages)
  - First text event arriving noticeably earlier (< 3s from `user_message` event)
  - No regressions in answer quality (responses still cite specific content)

- [ ] **Step 3: Check status line in browser**

  While the eval is running (headless=False), visually confirm:
  - "Searching course materials…" appears immediately after send
  - Updates to "Reading [material name], pages X–Y…" when pages are fetched
  - Disappears cleanly when streaming starts

