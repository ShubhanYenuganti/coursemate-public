# Auto Chat Title Suggestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On qualifying message exchanges, call GPT-4o-mini to continuously refine the chat title, replacing the opening-message-as-title pattern with "New Chat" and bypassing when the user has manually renamed.

**Architecture:** `suggest_chat_title` added to `api/llm.py`; a `_maybe_suggest_title` helper in `api/chat.py` wraps the cadence check + DB update and is called from all four message handlers (send, stream_send, edit, regenerate); frontend's three `done` handlers apply `suggested_title` when present.

**Tech Stack:** Python (requests, psycopg2), React (useState/setChats), GPT-4o-mini via OpenAI REST API

> **Migration already applied.** The schema migration `ALTER TABLE chats ADD COLUMN title_auto BOOLEAN NOT NULL DEFAULT TRUE;` has been run against the database. No DDL step is required.

---

## File Map

| File | Change |
|------|--------|
| `api/llm.py` | Add `suggest_chat_title` function |
| `api/chat.py` | Add `_should_suggest_title` + `_maybe_suggest_title` helpers; modify `_send_message`, `_stream_send_message`, `_edit_message`, `_regenerate_message`, `_update_chat` |
| `src/ChatTab.jsx` | Change initial title to `'New Chat'`; apply `suggested_title` in `done` handlers |

---

## Task 1: Add `suggest_chat_title` to `api/llm.py`

**Files:**
- Modify: `api/llm.py` (insert immediately before the `_PROVIDERS` dict at line 1091)

> **Note:** The spec defined `suggest_chat_title` with a `recent_msgs` parameter. This plan inlines the DB query inside the function instead — avoids threading the list through call sites and keeps the function self-contained. The behaviour is identical.

> **Commit note:** `get_db()` in `api/db.py` auto-commits on successful exit (`conn.commit()` in the context manager). The `UPDATE chats SET title` executed inside `_maybe_suggest_title` is part of the same transaction as the message insertion; it commits when the outer `with get_db()` block completes normally.

- [ ] **Step 1: Add the function** — insert immediately before `_PROVIDERS = {` (line 1091):

```python
_TITLE_MODEL = "gpt-4o-mini"
_TITLE_URL = "https://api.openai.com/v1/chat/completions"


def suggest_chat_title(
    conn,
    user_id: int,
    chat_id: int,
    current_title: str,
) -> str | None:
    """
    Ask GPT-4o-mini to suggest a refined title for the chat based on recent messages.
    Returns a title string (max 80 chars) or None on any failure.
    """
    try:
        api_key = _get_api_key(conn, user_id, "openai")
    except Exception:
        return None

    if not api_key:
        return None

    # Fetch recent messages directly
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE chat_id = %s
              AND is_deleted = FALSE
            ORDER BY message_index DESC
            LIMIT 6
            """,
            (chat_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception:
        return None

    # Reverse to chronological order and truncate content
    turns = [
        {"role": row["role"], "content": (row["content"] or "")[:300]}
        for row in reversed(rows)
    ]

    system_prompt = (
        "You suggest short chat titles. Given the current title and recent conversation turns, "
        "return a refined title that better reflects the conversation topic. "
        "Rules: max 80 characters, no quotes, no markdown, minimal alteration from the current "
        "title unless the topic has clearly shifted. Return strict JSON: {\"title\": \"...\"}."
    )
    payload = {
        "current_title": current_title or "New Chat",
        "turns": turns,
    }

    try:
        resp = requests.post(
            _TITLE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _TITLE_MODEL,
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=8,
        )
        resp.raise_for_status()
        parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
        title = str(parsed.get("title", "")).strip()
        if title:
            return title[:80]
    except Exception:
        pass

    return None
```

- [ ] **Step 2: Verify imports** — `json` and `requests` are already imported at the top of `api/llm.py`. Confirm `_get_api_key` is defined in the same file (it is, around line 232).

---

## Task 2: Add helpers to `api/chat.py`

**Files:**
- Modify: `api/chat.py` (add two helpers after `_next_message_index`)

- [ ] **Step 1: Add the helpers** after `_next_message_index` (around line 69):

```python
def _should_suggest_title(user_msg_index: int) -> bool:
    """Fire on exchange 1, then every 4th exchange: 1, 5, 9, 13, …"""
    exchange = (user_msg_index // 2) + 1
    return exchange == 1 or (exchange - 1) % 4 == 0


def _maybe_suggest_title(conn, chat, user_id: int, user_msg_index: int) -> str | None:
    """
    If auto-titling is active and cadence fires, call GPT-4o-mini for a title suggestion,
    persist it to the DB, and return the new title. Returns None otherwise.
    """
    if not chat.get("title_auto", True):
        return None
    if not _should_suggest_title(user_msg_index):
        return None

    try:
        from .llm import suggest_chat_title
    except ImportError:
        from llm import suggest_chat_title

    suggested = suggest_chat_title(
        conn=conn,
        user_id=user_id,
        chat_id=chat["id"],
        current_title=chat.get("title") or "New Chat",
    )
    if not suggested:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chats SET title = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (suggested, chat["id"]),
        )
        cursor.close()
    except Exception:
        logger.exception("auto_title_update_failed", extra={"chat_id": chat["id"]})
        return None

    return suggested
```

---

## Task 3: Wire into `_send_message` (non-streaming)

**Files:**
- Modify: `api/chat.py` — `_send_message` method

- [ ] **Step 1: After the assistant message embedding block (around line 727, after `cursor.close()`)**, add:

```python
            suggested_title = _maybe_suggest_title(conn, chat, user['id'], next_idx)
```

- [ ] **Step 2: Update the response** at the `send_json` call (around line 741):

```python
        send_json(self, 201, {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "chunks": serialized_chunks,
            "suggested_title": suggested_title,
        })
```

---

## Task 4: Wire into `_stream_send_message`

**Files:**
- Modify: `api/chat.py` — `_stream_send_message` method

- [ ] **Step 1: After the assistant message embedding block (around line 890, after `cursor.close()`)**, add:

```python
            suggested_title = _maybe_suggest_title(conn, chat, user['id'], next_idx)
```

- [ ] **Step 2: Update the `done` SSE event** (around line 892):

```python
            send_sse_event(self, {
                "type": "done",
                "user_message": dict(user_message),
                "assistant_message": dict(assistant_message),
                "suggested_title": suggested_title,
            })
```

---

## Task 5: Wire into `_edit_message`

**Files:**
- Modify: `api/chat.py` — `_edit_message` method

The edit handler uses `msg['message_index']` as the user message's position. After the inner `try` block (after assistant embedding, before `finally: cursor.close()`), `next_idx` is computed at line 1109 but that's the *new* assistant index — for cadence purposes we want the *user message's* original index.

- [ ] **Step 1: After the assistant message is inserted and its embedding written (around line 1156), add inside the inner `try` block**:

```python
                suggested_title = _maybe_suggest_title(conn, chat, user['id'], msg['message_index'])
```

- [ ] **Step 2: Update both response paths at the bottom of `_edit_message`** (around line 1176):

```python
        if is_streaming:
            send_sse_event(self, {
                "type": "done",
                "user_message": dict(edited_user_message),
                "assistant_message": dict(assistant_message),
                "suggested_title": suggested_title,
            })
        else:
            send_json(self, 200, {
                "user_message": edited_user_message,
                "assistant_message": assistant_message,
                "chunks": serialized_chunks,
                "suggested_title": suggested_title,
            })
```

- [ ] **Step 3: Initialize `suggested_title = None`** immediately before the inner `try` block at line 1062 (the one that starts with `# Build v2 reply_history`), not at the top of the outer `with` block. This ensures it's in scope for the response send calls at the bottom of the method even if `_maybe_suggest_title` is never reached on an error path through the inner `try/finally`.

---

## Task 6: Wire into `_regenerate_message`

**Files:**
- Modify: `api/chat.py` — `_regenerate_message` method

The user message index is `user_msg['message_index']`.

- [ ] **Step 1: After `new_assistant` is fetched (around line 1776, after the assistant INSERT), add inside the inner `try` block**:

```python
                suggested_title = _maybe_suggest_title(conn, chat, user['id'], user_msg['message_index'])
```

- [ ] **Step 2: Update both response paths at the bottom of `_regenerate_message`** (around line 1785):

```python
        if is_streaming:
            send_sse_event(self, {
                "type": "done",
                "user_message": dict(updated_user_msg),
                "assistant_message": dict(new_assistant),
                "suggested_title": suggested_title,
            })
        else:
            send_json(self, 200, {
                "user_message": updated_user_msg,
                "assistant_message": new_assistant,
                "suggested_title": suggested_title,
            })
```

- [ ] **Step 3: Initialize `suggested_title = None`** before the inner `try` block.

---

## Task 7: Update `_update_chat` to lock out auto-titling

**Files:**
- Modify: `api/chat.py` — `_update_chat` method

- [ ] **Step 1: Find the UPDATE query** (around line 477) and add `title_auto = FALSE`:

```python
            cursor.execute("""
                UPDATE chats SET title = %s, title_auto = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, course_id, user_id, title, title_auto, visibility, message_count,
                          last_message_at, created_at, updated_at, is_archived
            """, (title, chat_id))
```

---

## Task 8: Frontend — initial title + apply suggested_title

**Files:**
- Modify: `src/ChatTab.jsx`

- [ ] **Step 1: Change the initial chat title in `handleSend`** (around line 1407):

```js
// Before:
const title = text.slice(0, 80);

// After:
const title = 'New Chat';
```

- [ ] **Step 2: Apply `suggested_title` in `handleStreamEvent` `done` case** (around line 1370, after the `setChats` call for `last_message_at`):

```js
      case 'done':
        setStreamingHistory([]);
        setMessages((prev) => {
          const withoutTemp = prev.filter((m) => m.id !== tempId && m.id !== evt.user_message?.id);
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
```

- [ ] **Step 3: Apply `suggested_title` in `handleEditMessage` `done` handler** (around line 1557, inside the `if (evt.type === 'done')` block, after the `setChats` call):

```js
                setChats((prev) => prev.map((c) =>
                  c.id === target.chat_id
                    ? {
                        ...c,
                        last_message_at: evt.assistant_message?.created_at,
                        message_count: nextMessages.length,
                        ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
                      }
                    : c
                ));
```

- [ ] **Step 4: Apply `suggested_title` in `handleRegenerateMessage` `done` handler** (around line 1736, inside the `if (evt.type === 'done')` block, after `setMessages`):

```js
                setChats((prev) => prev.map((c) =>
                  c.id === (userMsg.chat_id || assistantMsg.chat_id)
                    ? {
                        ...c,
                        ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
                      }
                    : c
                ));
```

---

## Task 9: Commit

- [ ] **Step 1: Stage and commit all changes**

```bash
git add api/llm.py api/chat.py src/ChatTab.jsx
git commit -m "feat: auto-suggest chat titles via GPT-4o-mini on every 4th exchange

- Replaces opening-message-as-title with 'New Chat' placeholder
- suggest_chat_title in llm.py calls gpt-4o-mini with recent turns
- _maybe_suggest_title in chat.py handles cadence (1, 5, 9, …) and title_auto guard
- _update_chat sets title_auto=FALSE to lock out auto-titling after manual rename
- suggested_title included in done SSE event and applied in frontend setChats"
```
