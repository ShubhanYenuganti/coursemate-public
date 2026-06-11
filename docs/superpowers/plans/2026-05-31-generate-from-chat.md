# Generate-From-Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user trigger a conversation-grounded quiz/flashcard/report generation directly from chat — the model proposes it inline as a card the user can Build (queue immediately) or Refine (open the prefilled modal).

**Architecture:** A new no-side-effect `propose_generation` tool in the PageIndex agentic loop emits a `generation_proposal` SSE event instead of generating. The frontend renders a Proposal Card; Build reuses the existing draft-create + `action=generate` (SQS) endpoints, adding an optional `conversation_context` field that the generator Lambdas merge with material chunks (hybrid source). Refine opens the existing generation modal prefilled.

**Tech Stack:** Python stdlib HTTP handlers (`api/`), AWS Lambda workers (`lambda/`), OpenAI/Anthropic/Gemini function-calling, PostgreSQL, React (`src/`), pytest, `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-05-31-generate-from-chat-design.md`

**Dependency:** Roadmap priority #1 (all-providers agentic loop). Until that ships, `propose_generation` is reachable on the OpenAI/PageIndex path only. This plan is buildable now against that path.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `api/llm.py` | `propose_generation` tool def + dispatch → emit `generation_proposal` event | Modify (`run_agent_pageindex`) |
| `tests/test_pageindex_agent.py` | Unit tests for the new tool + event | Modify |
| DB: `quiz_generations`, `flashcard_generations`, `report_generations` | Persist conversation context | Migration (nullable `conversation_context TEXT`) |
| `api/quiz.py` | Accept + persist `conversation_context` on create/draft | Modify |
| `api/flashcards.py` | Same | Modify |
| `api/reports.py` | Same | Modify |
| `lambda/quiz_generate/handler.py` | Merge conversation context into prompt source | Modify |
| `lambda/flashcards_generate/handler.py` | Same | Modify |
| `lambda/reports_generate/handler.py` | Same | Modify |
| `src/ChatTab.jsx` | Handle `generation_proposal` event; render card; Build/Refine handlers | Modify |
| `src/components/GenerationProposalCard.jsx` | Presentational card | Create |

---

## Phase 1 — Backend: `propose_generation` tool + SSE event

### Task 1: Add `propose_generation` to the PageIndex agent

**Files:**
- Modify: `api/llm.py` (`run_agent_pageindex` — tools list near line 1540, dispatch loop near line 1680)
- Test: `tests/test_pageindex_agent.py`

The tool produces no generation. When the model calls it, the agent emits an `on_event` of type `generation_proposal` and returns a short tool-result string so the model then writes its conversational reply in the same turn.

Proposal object shape (forwarded verbatim in the event):
```python
{
    "type": "generation_proposal",
    "generation_type": "quiz" | "flashcards" | "report",
    "title": str,
    "discussion_summary": str,
    "material_ids": list[int],   # defaults to context_material_ids if model omits
    "params": dict,              # type-specific, e.g. {"tf_count":3,"sa_count":2,"la_count":1}
}
```

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pageindex_agent.py` (reuse the existing `patch`/`MagicMock` style; place after the existing tool-call tests):

```python
def _stub_openai_named_tool_call(name: str, args: dict) -> MagicMock:
    """Mock one streaming OpenAI response that emits a single named tool call."""
    resp = MagicMock()
    resp.status_code = 200
    tool_args = json.dumps(args)
    lines = [
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1",'
        b'"type":"function","function":{"name":"' + name.encode() + b'",'
        b'"arguments":' + json.dumps(tool_args).encode() + b'}}]}}]}',
        b'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        b'data: [DONE]',
    ]
    resp.iter_lines.return_value = iter(lines)
    return resp


def test_run_agent_pageindex_propose_generation_emits_event():
    import copy
    from llm import run_agent_pageindex

    events = []
    first = _stub_openai_named_tool_call(
        "propose_generation",
        {
            "generation_type": "quiz",
            "title": "TCP Handshake Quiz",
            "discussion_summary": "We covered SYN/SYN-ACK/ACK and sequence numbers.",
            "params": {"tf_count": 3, "sa_count": 2, "la_count": 1},
        },
    )
    second = _stub_openai_response_no_tools("Here's a quiz on the handshake.")

    with patch("llm.requests.post", side_effect=[copy.deepcopy(first), copy.deepcopy(second)]), \
         patch("llm.get_course_routing_index", return_value=[]), \
         patch("llm._format_routing_index_block", return_value="<course_materials></course_materials>"):
        run_agent_pageindex(
            conn=MagicMock(),
            user_message="make me a quiz about the TCP handshake",
            model="gpt-4o",
            api_key="sk-test",
            chat_id=1,
            course_id=7,
            context_material_ids=[101, 102],
            on_event=events.append,
        )

    proposals = [e for e in events if e.get("type") == "generation_proposal"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["generation_type"] == "quiz"
    assert p["title"] == "TCP Handshake Quiz"
    assert p["material_ids"] == [101, 102]          # defaulted from context_material_ids
    assert p["params"]["tf_count"] == 3
    assert "SYN" in p["discussion_summary"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_run_agent_pageindex_propose_generation_emits_event -v`
Expected: FAIL — no `generation_proposal` event emitted (the tool is unknown, dispatch falls through).

- [ ] **Step 3: Add the tool definition**

In `api/llm.py`, inside `run_agent_pageindex`, append to the `tools` list (after the `get_related_materials` entry, before the list closes near line 1620):

```python
        {
            "type": "function",
            "function": {
                "name": "propose_generation",
                "description": (
                    "Propose a study artifact (quiz, flashcards, or report) for the user to "
                    "build from this conversation. Call this ONLY when the user explicitly asks "
                    "to create one (e.g. 'make me a quiz about X', 'turn this into flashcards'). "
                    "Do not generate the artifact yourself — this tool shows the user a card they "
                    "confirm. After calling it, write a short reply telling them the proposal is ready."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "generation_type": {
                            "type": "string",
                            "enum": ["quiz", "flashcards", "report"],
                        },
                        "title": {"type": "string", "description": "Short human title."},
                        "discussion_summary": {
                            "type": "string",
                            "description": (
                                "Concise distillation of the relevant conversation that should "
                                "ground the generation. A few sentences; this is the source content."
                            ),
                        },
                        "material_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Optional; defaults to the chat's selected materials.",
                        },
                        "params": {
                            "type": "object",
                            "description": (
                                "Optional type-specific parameters, e.g. {\"tf_count\":3,"
                                "\"sa_count\":2,\"la_count\":1} for quiz, {\"num_cards\":10} for "
                                "flashcards, {\"template\":\"study_guide\"} for report."
                            ),
                        },
                    },
                    "required": ["generation_type", "title", "discussion_summary"],
                },
            },
        },
```

- [ ] **Step 4: Add the dispatch branch**

In `api/llm.py`, in the `for call in tool_calls:` dispatch loop of `run_agent_pageindex`, add a branch alongside `get_material_structure` / `get_page_content` / `get_related_materials`:

```python
            elif name == "propose_generation":
                proposal = {
                    "type": "generation_proposal",
                    "generation_type": args.get("generation_type"),
                    "title": args.get("title") or "",
                    "discussion_summary": args.get("discussion_summary") or "",
                    "material_ids": args.get("material_ids") or list(context_material_ids or []),
                    "params": args.get("params") or {},
                }
                if on_event:
                    on_event(proposal)
                tool_result = (
                    "Proposal shown to the user as a card with Build and Refine actions. "
                    "Now write a one-sentence reply confirming the proposal is ready."
                )
```

Ensure the existing `messages.append({"role": "tool", ...})` after the branch chain uses `tool_result` (it already does for the other tools — this branch sets the same variable).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py::test_run_agent_pageindex_propose_generation_emits_event -v`
Expected: PASS

- [ ] **Step 6: Run the full agent test file (no regressions)**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add api/llm.py tests/test_pageindex_agent.py
git commit -m "feat(chat): add propose_generation tool emitting generation_proposal event"
```

---

## Phase 2 — Backend: persist `conversation_context` + merge into generation source

### Task 2: Add `conversation_context` columns (migration)

**Files:** Database only (no migration script — per project policy, run these one-liners directly).

- [ ] **Step 1: Run the migration SQL against the database**

```sql
ALTER TABLE quiz_generations    ADD COLUMN IF NOT EXISTS conversation_context TEXT;
ALTER TABLE flashcard_generations ADD COLUMN IF NOT EXISTS conversation_context TEXT;
ALTER TABLE report_generations  ADD COLUMN IF NOT EXISTS conversation_context TEXT;
```

> Confirm the exact flashcard/report table names first with:
> `cd /Users/shubhan/OneShotCourseMate && rg -n "INSERT INTO .*_generations|CREATE TABLE .*_generations" api lambda`
> Adjust the table names above if they differ (e.g. `flashcards_generations`).

- [ ] **Step 2: Verify columns exist**

```sql
SELECT table_name, column_name FROM information_schema.columns
WHERE column_name = 'conversation_context';
```
Expected: three rows, one per generation table.

### Task 3: Quiz API — accept & persist `conversation_context`

**Files:**
- Modify: `api/quiz.py` (POST create/draft body parsing near line 655; the `UPDATE quiz_generations SET status='queued' ...` near line 737; the new-row INSERT path)
- Test: `tests/test_quiz_conversation_context.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


def test_extract_conversation_context_from_body():
    from quiz import _extract_conversation_context  # to be added
    assert _extract_conversation_context({"conversation_context": "We discussed TCP."}) == "We discussed TCP."
    assert _extract_conversation_context({}) is None
    assert _extract_conversation_context({"conversation_context": "  "}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_quiz_conversation_context.py -v`
Expected: FAIL — `ImportError: cannot import name '_extract_conversation_context'`.

- [ ] **Step 3: Add the helper and persist it**

In `api/quiz.py`, add near the other module-level helpers:

```python
def _extract_conversation_context(body: dict) -> str | None:
    """Optional conversation summary that grounds a chat-originated generation."""
    val = (body.get('conversation_context') or '').strip()
    return val or None
```

In the POST handler, read it once after parsing the body:

```python
        conversation_context = _extract_conversation_context(body)
```

In the draft `UPDATE quiz_generations SET status='queued' ...` statement, add the column when present (keep existing params; append a conditional set is fine, but simplest is to always set it):

```python
                    cursor.execute(
                        """
                        UPDATE quiz_generations
                        SET status='queued',
                            provider=%s,
                            model_id=%s,
                            parent_generation_id=%s,
                            conversation_context=COALESCE(%s, conversation_context),
                            error=NULL
                        WHERE id=%s
                        """,
                        (provider, model_id, parent_generation_id_int,
                         conversation_context, draft_generation_id),
                    )
```

In the new-row INSERT path (the `else: # Legacy flow: create a new generation row directly`), include `conversation_context` in the column list and values. Locate the `INSERT INTO quiz_generations (...)` there and add the column + `%s` + `conversation_context` to the parameter tuple.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_quiz_conversation_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/quiz.py tests/test_quiz_conversation_context.py
git commit -m "feat(quiz): persist conversation_context on generation create/draft"
```

### Task 4: Quiz Lambda — merge conversation context into the prompt source

**Files:**
- Modify: `lambda/quiz_generate/handler.py` (`_build_quiz_prompt` near line 139; handler material-context assembly near line 369)
- Test: `tests/test_quiz_generate_context_merge.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'quiz_generate'))


def test_merge_conversation_context_prepends_discussion():
    from handler import _merge_conversation_context  # to be added
    merged = _merge_conversation_context("We discussed TCP handshake.", "PDF chunk text.")
    assert "We discussed TCP handshake." in merged
    assert "PDF chunk text." in merged
    # discussion appears before material chunks
    assert merged.index("We discussed") < merged.index("PDF chunk text.")


def test_merge_conversation_context_no_summary_returns_material_only():
    from handler import _merge_conversation_context
    assert _merge_conversation_context(None, "PDF chunk text.") == "PDF chunk text."
    assert _merge_conversation_context("", "PDF chunk text.") == "PDF chunk text."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_quiz_generate_context_merge.py -v`
Expected: FAIL — `ImportError: cannot import name '_merge_conversation_context'`.

- [ ] **Step 3: Add the merge helper and call it in the handler**

In `lambda/quiz_generate/handler.py`, add near `_fetch_material_context`:

```python
def _merge_conversation_context(conversation_context: str | None, material_context: str) -> str:
    """Prepend a conversation summary (chat-originated generations) ahead of material chunks."""
    summary = (conversation_context or "").strip()
    if not summary:
        return material_context
    return (
        "Conversation summary (what the student discussed; use as primary source):\n"
        f"{summary}\n\n"
        "Supporting course materials:\n"
        f"{material_context}"
    )
```

In the handler, after `material_context = _fetch_material_context(conn, material_ids)` (near line 369), insert:

```python
        material_context = _merge_conversation_context(
            gen.get('conversation_context'), material_context
        )
```

(`gen` is the generation row already fetched in the handler; `conversation_context` is now a column on it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_quiz_generate_context_merge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lambda/quiz_generate/handler.py tests/test_quiz_generate_context_merge.py
git commit -m "feat(quiz-lambda): merge conversation_context into generation source"
```

### Task 5: Flashcards + Reports — same persist + merge

**Files:**
- Modify: `api/flashcards.py`, `api/reports.py` (mirror Task 3)
- Modify: `lambda/flashcards_generate/handler.py`, `lambda/reports_generate/handler.py` (mirror Task 4)
- Test: `tests/test_flashcards_conversation_context.py`, `tests/test_reports_conversation_context.py` (Create)

- [ ] **Step 1: Write failing tests (mirror Task 3/4 helpers)**

For each of flashcards and reports, add a test mirroring Task 3 (`_extract_conversation_context`) and Task 4 (`_merge_conversation_context`). Example for flashcards (repeat structure for reports, adjusting the `sys.path` lambda dir to `reports_generate` and module imports):

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'flashcards_generate'))


def test_flashcards_extract_conversation_context():
    from flashcards import _extract_conversation_context
    assert _extract_conversation_context({"conversation_context": "We discussed mitosis."}) == "We discussed mitosis."
    assert _extract_conversation_context({}) is None


def test_flashcards_merge_conversation_context():
    from handler import _merge_conversation_context
    merged = _merge_conversation_context("We discussed mitosis.", "Material chunk.")
    assert "We discussed mitosis." in merged and "Material chunk." in merged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_flashcards_conversation_context.py tests/test_reports_conversation_context.py -v`
Expected: FAIL — missing helpers.

- [ ] **Step 3: Implement in both API modules**

In `api/flashcards.py` and `api/reports.py`, add the identical `_extract_conversation_context` helper from Task 3 Step 3, read `conversation_context = _extract_conversation_context(body)` in the POST handler, and add `conversation_context=COALESCE(%s, conversation_context)` to the draft `UPDATE ... SET status='queued'` plus the column to the new-row INSERT (same as quiz). Use each module's actual generation table name.

- [ ] **Step 4: Implement in both Lambda handlers**

In `lambda/flashcards_generate/handler.py` and `lambda/reports_generate/handler.py`, add the identical `_merge_conversation_context` helper from Task 4 Step 3, and call it on the assembled material context immediately after that context is fetched and before it is passed into the prompt builder, using the generation row's `conversation_context` column.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_flashcards_conversation_context.py tests/test_reports_conversation_context.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add api/flashcards.py api/reports.py lambda/flashcards_generate/handler.py lambda/reports_generate/handler.py tests/test_flashcards_conversation_context.py tests/test_reports_conversation_context.py
git commit -m "feat(flashcards,reports): persist + merge conversation_context"
```

---

## Phase 3 — Frontend: Proposal Card + Build/Refine

### Task 6: Render the Proposal Card from the `generation_proposal` event

**Files:**
- Create: `src/components/GenerationProposalCard.jsx`
- Modify: `src/ChatTab.jsx` (`handleStreamEvent` switch near line 1789; assistant-message render)

- [ ] **Step 1: Create the presentational card**

`src/components/GenerationProposalCard.jsx`:

```jsx
import React from 'react';

const TYPE_LABEL = { quiz: 'Quiz', flashcards: 'Flashcards', report: 'Report' };

export default function GenerationProposalCard({ proposal, onBuild, onRefine, status }) {
  if (!proposal) return null;
  const { generation_type, title, material_ids = [], params = {} } = proposal;
  const paramSummary = Object.entries(params)
    .map(([k, v]) => `${v} ${k.replace(/_count$/, '').replace(/_/g, ' ')}`)
    .join(' · ');

  return (
    <div className="mt-2 rounded-xl border border-indigo-200 bg-indigo-50/60 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-indigo-700">
        <span>💡 {TYPE_LABEL[generation_type] || 'Generation'}</span>
        <span className="text-indigo-400">·</span>
        <span className="truncate">{title}</span>
      </div>
      <div className="mt-1 text-[11px] text-indigo-600/80">
        {paramSummary && <span>{paramSummary} · </span>}
        <span>{material_ids.length} material{material_ids.length === 1 ? '' : 's'} + this conversation</span>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={onBuild}
          disabled={status === 'building'}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {status === 'building' ? 'Queuing…' : status === 'queued' ? 'Queued ✓' : 'Build'}
        </button>
        <button
          type="button"
          onClick={onRefine}
          disabled={status === 'building'}
          className="px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 text-xs font-medium hover:bg-indigo-100"
        >
          Refine
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Attach the proposal to the streaming assistant message**

In `src/ChatTab.jsx` `handleStreamEvent` switch, add a case before `default`:

```jsx
      case 'generation_proposal':
        setMessages((prev) => {
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId ? { ...m, _generationProposal: evt } : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: '', _streaming: true, _generationProposal: evt }];
        });
        break;
```

- [ ] **Step 3: Render the card under the assistant message**

In `src/ChatTab.jsx`, find where an assistant message's content is rendered (the message-bubble JSX). Locate it with:
`cd /Users/shubhan/OneShotCourseMate && rg -n "_liveToolTrace|msg.content|message.content|role === 'assistant'" src/ChatTab.jsx`
Immediately after the assistant content block, render:

```jsx
{msg._generationProposal && (
  <GenerationProposalCard
    proposal={msg._generationProposal}
    status={msg._proposalStatus}
    onBuild={() => handleBuildGeneration(msg)}
    onRefine={() => handleRefineGeneration(msg)}
  />
)}
```

Add the import at the top of `ChatTab.jsx`:
```jsx
import GenerationProposalCard from './components/GenerationProposalCard';
```
(Adjust the relative path if `ChatTab.jsx` is not in `src/`.)

- [ ] **Step 4: Build the frontend to verify it compiles**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: build succeeds (no import/JSX errors).

- [ ] **Step 5: Commit**

```bash
git add src/components/GenerationProposalCard.jsx src/ChatTab.jsx
git commit -m "feat(chat-ui): render generation proposal card from stream event"
```

### Task 7: Build handler — create + enqueue directly

**Files:**
- Modify: `src/ChatTab.jsx` (add `handleBuildGeneration`)

`handleBuildGeneration` POSTs to the right endpoint with the proposal values, the chat's provider/model, and `conversation_context = discussion_summary`, then triggers `action=generate`. Reuse the existing `fetch('/api/quiz', ...)` style already in the file (see the create/generate calls).

- [ ] **Step 1: Add the handler**

```jsx
const ENDPOINT_BY_TYPE = { quiz: '/api/quiz', flashcards: '/api/flashcards', report: '/api/reports' };

async function handleBuildGeneration(msg) {
  const p = msg._generationProposal;
  if (!p) return;
  const endpoint = ENDPOINT_BY_TYPE[p.generation_type];
  if (!endpoint) return;

  setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, _proposalStatus: 'building' } : m));
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        action: 'generate',
        course_id: course.id,
        title: p.title,
        topic: p.title,
        material_ids: p.material_ids,
        conversation_context: p.discussion_summary,
        provider: selectedModel,
        model_id: selectedModelId || selectedModel,
        ...p.params,
      }),
    });
    if (!res.ok) throw new Error('queue failed');
    setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, _proposalStatus: 'queued' } : m));
  } catch (e) {
    setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, _proposalStatus: null } : m));
  }
}
```

> Confirm the create+enqueue contract: the quiz POST handler accepts `action=generate` with these fields and enqueues (see `api/quiz.py` POST routing). If create and enqueue are two separate calls in this codebase, issue the create call first, then the `action=generate` call with the returned `generation_id`. Verify with:
> `cd /Users/shubhan/OneShotCourseMate && rg -n "action'|action\"|draft_generation_id|action == 'generate'" api/quiz.py`

- [ ] **Step 2: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat(chat-ui): Build action queues generation from proposal"
```

### Task 8: Refine handler — open the prefilled modal

**Files:**
- Modify: `src/ChatTab.jsx` (add `handleRefineGeneration`)
- Possibly modify: `src/CoursePage.jsx`, `src/Generations.jsx` (thread a prefill payload), depending on the existing tab-navigation mechanism.

- [ ] **Step 1: Identify the existing navigation + prefill mechanism**

Run:
`cd /Users/shubhan/OneShotCourseMate && rg -n "onGoToTab|onNavigate|handleTabChange|setActiveTab|preSelected|prefill" src/ChatTab.jsx src/CoursePage.jsx src/Generations.jsx`
This determines whether ChatTab already receives a tab-navigation prop (as `FlashcardViewer` does via `onGoToTab`) and how state is threaded.

- [ ] **Step 2: Add the handler using that mechanism**

If ChatTab receives `onGoToTab(tab, payload)` (or similar), implement:

```jsx
function handleRefineGeneration(msg) {
  const p = msg._generationProposal;
  if (!p || !onGoToTab) return;
  onGoToTab('generate', {
    generationType: p.generation_type,
    prefill: {
      title: p.title,
      topic: p.title,
      material_ids: p.material_ids,
      conversation_context: p.discussion_summary,
      provider: selectedModel,
      model_id: selectedModelId || selectedModel,
      ...p.params,
    },
  });
}
```

If the navigation prop does not yet accept a payload, extend it minimally: thread an optional second argument through `CoursePage`'s tab-change handler into `Generations.jsx`, and have the relevant modal (`Quiz.jsx` / `Flashcards.jsx` / `Reports.jsx`) read the prefill on mount to set its initial form state. Keep changes additive — prefill is optional and absent for normal navigation.

- [ ] **Step 3: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 4: Commit**

```bash
git add src/ChatTab.jsx src/CoursePage.jsx src/Generations.jsx
git commit -m "feat(chat-ui): Refine action opens prefilled generation modal"
```

---

## Phase 4 — End-to-end verification

### Task 9: Manual + eval verification

- [ ] **Step 1: Run the backend test suite**

Run: `cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_agent.py tests/test_quiz_conversation_context.py tests/test_quiz_generate_context_merge.py tests/test_flashcards_conversation_context.py tests/test_reports_conversation_context.py -v`
Expected: all PASS.

- [ ] **Step 2: Manual flow (OpenAI model selected in chat)**

1. Open a course chat, select 2 materials, choose an OpenAI model.
2. Send: "make me a quiz about <topic in the materials>".
3. Verify: a conversational reply streams AND a Proposal Card appears showing type, title, params, and "2 materials + this conversation".
4. Click **Build** → card shows "Queued ✓"; a quiz generation appears in the Generate tab and completes.
5. Open the quiz → questions reflect the discussed topic (hybrid source working).

- [ ] **Step 3: Refine + no-materials paths**

1. Repeat step 2, click **Refine** → the quiz modal opens prefilled with the title/params/materials.
2. New chat with NO materials selected → "make me flashcards about <topic>" → Build → flashcards generated from the conversation summary alone (no error).

- [ ] **Step 4: Commit any fixes, then report status**

```bash
git add -A && git commit -m "test: verify generate-from-chat end-to-end"
```

---

## Self-Review Notes

- **Spec coverage:** propose_generation tool (Task 1) ✓; hybrid source = summary+materials (Tasks 3–5) ✓; Build reuses existing endpoints (Task 7) ✓; Refine opens prefilled modal (Task 8) ✓; all three generation types (Task 5, 7) ✓; provider defaults to chat's (Tasks 7–8) ✓; no-materials → conversation-only (Task 4 merge returns summary-grounded context, Task 9 Step 3) ✓.
- **Dependency:** Phase 1 works on the OpenAI/PageIndex path today; Claude/Gemini coverage arrives with roadmap priority #1 (no extra work here beyond the shared tool definition).
- **Deferred decision resolved:** `conversation_context` stored as a dedicated nullable `TEXT` column per generation table (Task 2), not a JSON settings field — explicit and trivially merge-able in the Lambda.
- **Attribution risk (from spec):** conversation-derived content has no page citations. Not changed in this plan; the viewer renders only the citations the generator emits, so no false citations are introduced. Flagged for design follow-up if richer attribution is wanted.
