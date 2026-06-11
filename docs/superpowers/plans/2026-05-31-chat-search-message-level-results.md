# Chat Search — Message-Level Results — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "In Conversation" chat-search results show a highlighted snippet of the best-matching message and, on click, open the chat scrolled to and highlighting that message.

**Architecture:** Extend the existing `_search_chats` FTS handler to return one best-matching message per chat (via `DISTINCT ON` + `ts_headline`). The `SearchChat` modal renders the snippet and passes the target message to `ChatTab`, which scrolls to and highlights it after the chat loads.

**Tech Stack:** Python stdlib HTTP handler (`api/chat.py`), PostgreSQL FTS (`to_tsvector`/`ts_rank`/`ts_headline`), React (`src/SearchChat.jsx`, `src/ChatTab.jsx`), pytest.

**Spec:** `docs/superpowers/specs/2026-05-31-chat-search-message-level-results-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `api/chat.py` | `_search_chats`: content matches return best message + snippet | Modify |
| `src/SearchChat.jsx` | Render snippet line; pass target on content-row click | Modify |
| `src/ChatTab.jsx` | Scroll-to + transient highlight of target message on open | Modify |
| `tests/test_chat_search_snippets.py` | Backend snippet/shape test | Create |

---

## Task 1: Backend — best-matching message + snippet per content hit

**Files:**
- Modify: `api/chat.py` (`_search_chats`, the `content_matches` CTE near line 538 and the result assembly near line 562)
- Test: `tests/test_chat_search_snippets.py` (Create)

- [ ] **Step 1: Write the failing test**

The snippet building is pure SQL, so test the Python-side result mapping by extracting it into a small helper. First add the helper (Step 3 implements it), then this test:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_content_match_row_includes_message_fields():
    from chat import _content_match_from_row
    row = {
        "match_type": "content",
        "id": 12,
        "title": "Midterm review",
        "last_message_at": "2026-05-30T10:00:00Z",
        "hit_count": 3,
        "message_id": 88,
        "message_index": 4,
        "snippet": "the TCP <mark>handshake</mark> uses SYN",
    }
    out = _content_match_from_row(row)
    assert out["id"] == 12
    assert out["message_id"] == 88
    assert out["message_index"] == 4
    assert "<mark>handshake</mark>" in out["snippet"]
    assert out["hit_count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_search_snippets.py -v`
Expected: FAIL — `ImportError: cannot import name '_content_match_from_row'`.

- [ ] **Step 3: Add the row-mapping helper**

In `api/chat.py`, add near the other module helpers:

```python
def _content_match_from_row(r: dict) -> dict:
    """Shape a content-match SQL row into the search API response item."""
    return {
        "id": r["id"],
        "title": r["title"],
        "last_message_at": r["last_message_at"],
        "message_id": r["message_id"],
        "message_index": r["message_index"],
        "snippet": r["snippet"],
        "hit_count": r["hit_count"],
    }
```

- [ ] **Step 4: Rewrite the `content_matches` CTE to select the best message + snippet**

In `_search_chats`, replace the `content_matches` CTE (currently grouping to chat level) with a per-chat best-message selection. The new CTE chain:

```sql
                ranked_messages AS (
                    SELECT cm.chat_id,
                           cm.id   AS message_id,
                           cm.message_index,
                           ts_rank(to_tsvector('english', cm.content),
                                   plainto_tsquery('english', %s)) AS rank,
                           ts_headline('english', cm.content,
                                   plainto_tsquery('english', %s),
                                   'StartSel=<mark>,StopSel=</mark>,MaxFragments=1,MaxWords=18,MinWords=6') AS snippet,
                           COUNT(*) OVER (PARTITION BY cm.chat_id) AS hit_count
                    FROM chat_messages cm
                    JOIN chats c ON c.id = cm.chat_id
                    WHERE c.course_id = %s
                      AND c.user_id = %s
                      AND c.is_archived = FALSE
                      AND cm.is_deleted = FALSE
                      AND to_tsvector('english', cm.content) @@ plainto_tsquery('english', %s)
                      AND cm.chat_id != ALL(ARRAY(SELECT id FROM title_matches))
                ),
                best_per_chat AS (
                    SELECT DISTINCT ON (chat_id)
                           chat_id, message_id, message_index, rank, snippet, hit_count
                    FROM ranked_messages
                    ORDER BY chat_id, rank DESC
                ),
                content_matches AS (
                    SELECT c.id, c.title, c.last_message_at,
                           b.message_id, b.message_index, b.snippet, b.hit_count,
                           b.rank
                    FROM best_per_chat b
                    JOIN chats c ON c.id = b.chat_id
                    ORDER BY (1 + ln(b.hit_count)) * b.rank DESC
                    LIMIT 20
                )
```

Update the final `UNION ALL SELECT` to carry the new columns (use `NULL` for the columns that don't apply to title rows):

```sql
                SELECT 'title' AS match_type, id, title, last_message_at,
                       NULL::int AS hit_count, NULL::int AS message_id,
                       NULL::int AS message_index, NULL::text AS snippet
                FROM title_matches
                UNION ALL
                SELECT 'content' AS match_type, id, title, last_message_at,
                       hit_count, message_id, message_index, snippet
                FROM content_matches
```

Update the parameter tuple to match the new placeholder order. The `ranked_messages` CTE adds three `%s` for `q` (rank, headline, and the `@@` filter) before `course_id`/`user['id']`; keep the existing `title_tsq_params` for `title_matches`. Final params:
`(*title_tsq_params, course_id, user['id'], q, q, course_id, user['id'], q)`
Verify the order against the final SQL string before running.

- [ ] **Step 5: Use the helper in result assembly**

Replace the content-match list comprehension (near line 562):

```python
        content_matches = [
            _content_match_from_row(r) for r in rows if r["match_type"] == "content"
        ]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_chat_search_snippets.py -v`
Expected: PASS

- [ ] **Step 7: Smoke-test the SQL against a real DB (manual)**

With the dev DB, call:
`GET /api/chat?resource=chat_search&course_id=<id>&q=<a word in a message>`
Expected JSON: `content_matches[*]` each include `message_id`, `message_index`, and a `snippet` containing `<mark>`.

- [ ] **Step 8: Commit**

```bash
git add api/chat.py tests/test_chat_search_snippets.py
git commit -m "feat(chat-search): return best-matching message + snippet per content hit"
```

---

## Task 2: Frontend — render snippet, pass target message on click

**Files:**
- Modify: `src/SearchChat.jsx` (`ResultRow`, content-match section)

- [ ] **Step 1: Add a snippet renderer that safely interprets `<mark>` markers**

In `src/SearchChat.jsx`, add above `ResultRow`:

```jsx
function Snippet({ text }) {
  if (!text) return null;
  // Split on the known <mark>…</mark> markers; render matches highlighted.
  const parts = text.split(/(<mark>|<\/mark>)/g);
  let on = false;
  return (
    <span className="block text-[12px] text-gray-500 truncate mt-0.5">
      {parts.map((p, i) => {
        if (p === '<mark>') { on = true; return null; }
        if (p === '</mark>') { on = false; return null; }
        return on
          ? <mark key={i} className="bg-yellow-100 text-gray-800 rounded px-0.5">{p}</mark>
          : <span key={i}>{p}</span>;
      })}
    </span>
  );
}
```

- [ ] **Step 2: Extend `ResultRow` to show the snippet and pass a target**

Update `ResultRow` to accept optional `snippet` and `target`:

```jsx
function ResultRow({ chat, snippet, target, onSelectChat, onClose }) {
  return (
    <button
      type="button"
      className="w-full px-4 py-2.5 flex flex-col gap-0 hover:bg-indigo-50 cursor-pointer text-left"
      onClick={() => { onSelectChat(chat.id, target); onClose(); }}
    >
      <span className="flex items-center gap-3 w-full">
        <span className="text-gray-400 flex-shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </span>
        <span className="text-sm text-gray-800 truncate flex-1">{chat.title || 'Untitled'}</span>
        <span className="text-[11px] text-gray-400 flex-shrink-0">{formatRelative(chat.last_message_at)}</span>
      </span>
      {snippet && <Snippet text={snippet} />}
    </button>
  );
}
```

- [ ] **Step 3: Pass snippet + target for content rows**

In the "In Conversation" section, update the map:

```jsx
{results.content_matches.map(chat => (
  <ResultRow
    key={chat.id}
    chat={chat}
    snippet={chat.snippet}
    target={{ messageId: chat.message_id, messageIndex: chat.message_index }}
    onSelectChat={onSelectChat}
    onClose={onClose}
  />
))}
```

Title-match and recency `ResultRow`s stay as-is (no `snippet`/`target` → behave as before).

- [ ] **Step 4: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add src/SearchChat.jsx
git commit -m "feat(chat-search): render highlighted snippet in content results"
```

---

## Task 3: Frontend — scroll to and highlight the target message

**Files:**
- Modify: `src/ChatTab.jsx` (`handleConvSelect` near line 1718; message render map; add a scroll effect)

- [ ] **Step 1: Identify the select handler and message render**

Run:
`cd /Users/shubhan/OneShotCourseMate && rg -n "function handleConvSelect|handleConvSelect|messages.map\(|\.map\(\(m\b|\.map\(\(msg\b" src/ChatTab.jsx`
Confirm `handleConvSelect`'s current signature (it is passed as `onSelectChat`) and where the messages array is mapped to JSX rows. These are the two edit sites.

- [ ] **Step 2: Add pending-scroll state and accept a target in the handler**

Near the other ChatTab state (e.g. by `const [activeConv, setActiveConv] = useState(null);`, line 1280):

```jsx
const [pendingScrollMessageId, setPendingScrollMessageId] = useState(null);
const [highlightMessageId, setHighlightMessageId] = useState(null);
```

Update `handleConvSelect` to accept an optional `target`. If `handleConvSelect` currently takes a chat id (matching `onSelectChat(chat.id)`), add a second arg:

```jsx
function handleConvSelect(chatId, target) {
  setActiveConv(chatId);
  setPendingScrollMessageId(target?.messageId ?? null);
  // ... keep existing body (message loading is triggered by activeConv change)
}
```

(If `handleConvSelect` currently expects a conversation object, adapt: callers in this file pass an object, but `SearchChat` passes an id. Normalize at the top: `const id = typeof chatId === 'object' ? chatId.id : chatId;` and use `id`.)

- [ ] **Step 3: Give each message row a stable DOM id and a highlight class**

In the messages `.map(...)` render, add `id` and a conditional class to the row's outer element:

```jsx
<div
  id={`msg-${m.id}`}
  className={`... existing classes ... ${highlightMessageId === m.id ? 'ring-2 ring-yellow-300 rounded-lg transition' : ''}`}
>
```

- [ ] **Step 4: Add the scroll-and-highlight effect**

After the existing `messagesEndRef` scroll effect (near line 1396), add:

```jsx
useEffect(() => {
  if (!pendingScrollMessageId || !messages.length) return;
  const el = document.getElementById(`msg-${pendingScrollMessageId}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHighlightMessageId(pendingScrollMessageId);
    const t = setTimeout(() => setHighlightMessageId(null), 2000);
    setPendingScrollMessageId(null);
    return () => clearTimeout(t);
  }
  // Target not present (deleted / out of loaded range): clear, no scroll.
  setPendingScrollMessageId(null);
}, [pendingScrollMessageId, messages]);
```

- [ ] **Step 5: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 6: Manual verification**

1. Open the search modal, type a phrase that appears inside a message.
2. Confirm the "In Conversation" result shows a highlighted snippet.
3. Click it → the chat opens, scrolls the matching message into view, and it briefly highlights.
4. Click a title-only match → opens at default position (no scroll) — unchanged.

- [ ] **Step 7: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(chat-search): scroll to and highlight matched message on open"
```

---

## Self-Review Notes

- **Spec coverage:** snippet in results (Task 1 SQL + Task 2 render) ✓; deep-link scroll+highlight (Task 3) ✓; title/recency unchanged (Tasks 2–3 leave those rows untouched) ✓; archived still excluded (Task 1 keeps `is_archived = FALSE`) ✓; missing-target safe (Task 3 Step 4 clears with no scroll) ✓; no synthesis change ✓.
- **No raw HTML injection:** the `Snippet` component splits on the literal `<mark>` markers and renders React nodes; message content is never set via `dangerouslySetInnerHTML`.
- **Type consistency:** backend returns `message_id`/`message_index`/`snippet`; frontend reads `chat.message_id`/`chat.message_index`/`chat.snippet` and passes `{ messageId, messageIndex }`; `pendingScrollMessageId`/`highlightMessageId` used consistently in Task 3.
- **Soft spot (flagged with a grep step):** `handleConvSelect`'s exact current signature — Task 3 Step 1 resolves it before editing.
```
