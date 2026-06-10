# Retrieval Budget Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a budgeted PageIndex frontier path so broad questions can gather many model-selected candidate sections while admitting raw text by stored token cost before falling overflow back to summaries.

**Architecture:** Add index-time token accounting in `lambda/index_materials`, expose those token counts through PageIndex retrieval helpers, add pure budget/candidate helpers in `api/llm.py`, expose a `select_page_candidates` PageIndex tool across OpenAI, Claude, and Gemini schemas, and materialize submitted candidates into raw and summary evidence before final synthesis. Retrieval budget is derived from the selected synthesis model's context window and does not borrow from output capacity.

**Tech Stack:** Python 3 stdlib, existing PageIndex helpers, `pytest`. No new runtime dependencies or database tables.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `api/llm.py` | Modify | Add retrieval budget helpers, candidate parsing/materialization, tool schema, prompt text, evidence formatting, and loop wiring. |
| `lambda/index_materials/token_counter.py` | Create | Shared `TokenCounter` class used by every builder/indexing path. |
| `lambda/index_materials/builders/base.py` | Modify | Add `token_count` to `IndexNode` serialization and helpers to annotate node spans. |
| `lambda/index_materials/worker.py` | Modify | Add `token_count` to extracted page rows and annotate generated material indexes before storage. |
| `lambda/index_materials/db.py` | Modify | Store `material_page_text.token_count` with fallback for databases not migrated yet. |
| `api/pageindex_retrieval.py` | Modify | Return page and section token counts through retrieval helpers. |
| `api/services/query/pageindex_retrieval.py` | Modify | Mirror helper changes for the duplicate query service module. |
| `tests/test_chat_memory.py` | Modify | Add focused unit tests for budget math, candidate normalization, materialization, and prompt/tool schema. |
| `lambda/index_materials/tests/test_base.py` | Modify | Test node token-count serialization/annotation. |
| `lambda/index_materials/tests/test_db.py` | Modify | Test page token-count storage SQL. |

## Task 0: Add DB Migration For Page Token Counts

**Files:**
- Migration: database SQL

- [ ] **Step 1: Apply migration**

Run in the production migration mechanism used for PageIndex schema changes:

```sql
ALTER TABLE material_page_text
ADD COLUMN IF NOT EXISTS token_count INTEGER;
```

- [ ] **Step 2: Backfill existing rows**

Run:

```sql
UPDATE material_page_text
SET token_count = GREATEST(1, LENGTH(COALESCE(text_content, '')) / 4)
WHERE token_count IS NULL;
```

- [ ] **Step 3: Verify the column exists**

Run:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'material_page_text'
  AND column_name = 'token_count';
```

Expected: one row with `token_count`.

- [ ] **Step 4: Commit migration artifact if this repo has a migration location**

If this repo has no migration directory for PageIndex schema changes, record the SQL in the implementation commit message and deployment notes instead of creating an ad-hoc migration file.

```bash
git status --short
git commit -m "Add material page token count migration"
```

## Task 1: Add Shared Indexer Token Counter

**Files:**
- Create: `lambda/index_materials/token_counter.py`
- Modify: `lambda/index_materials/builders/base.py`
- Test: `lambda/index_materials/tests/test_base.py`

- [ ] **Step 1: Write the failing tests**

Append to `lambda/index_materials/tests/test_base.py`:

```python
from token_counter import TokenCounter


def test_token_counter_matches_backend_heuristic():
    counter = TokenCounter()

    assert counter.estimate_text("") == 1
    assert counter.estimate_text("abcd") == 1
    assert counter.estimate_text("a" * 400) == 100


def test_index_node_serializes_token_count():
    node = IndexNode(
        node_id="node_methods",
        title="Methods",
        start_page=2,
        end_page=5,
        token_count=123,
    )

    assert node.to_dict()["token_count"] == 123
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest lambda/index_materials/tests/test_base.py -q`

Expected: fails because `token_counter.py` and `IndexNode.token_count` do not exist.

- [ ] **Step 3: Create the shared token counter**

Create `lambda/index_materials/token_counter.py`:

```python
class TokenCounter:
    def estimate_text(self, text: str | None) -> int:
        if not text:
            return 1
        return max(1, len(text) // 4)

    def annotate_material_index(self, material_index, page_rows: dict[int, dict]) -> None:
        def _node_tokens(node) -> int:
            total = 0
            for page_num in range(node.start_page, node.end_page + 1):
                row = page_rows.get(page_num) or {}
                total += int(row.get("token_count") or self.estimate_text(row.get("text_content")))
            node.token_count = max(1, total)
            for child in getattr(node, "nodes", []) or []:
                _node_tokens(child)
            return node.token_count

        for node in material_index.nodes:
            _node_tokens(node)
```

- [ ] **Step 4: Add token_count to IndexNode**

Modify `IndexNode` in `lambda/index_materials/builders/base.py`:

Add the field:

```python
    token_count: int = 0
```

Add it to `to_dict()`:

```python
            "token_count": self.token_count,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest lambda/index_materials/tests/test_base.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lambda/index_materials/token_counter.py lambda/index_materials/builders/base.py lambda/index_materials/tests/test_base.py
git commit -m "Add indexer token counting primitive"
```

## Task 2: Populate Page And Section Token Counts During Indexing

**Files:**
- Modify: `lambda/index_materials/worker.py`
- Modify: `lambda/index_materials/builders/base.py`
- Test: `lambda/index_materials/tests/test_worker.py`

- [ ] **Step 1: Write the failing tests**

Append to `lambda/index_materials/tests/test_worker.py`:

```python
def test_extract_pages_sets_token_count(monkeypatch):
    class FakePage:
        def get_images(self, full=True):
            return []

    class FakeDoc:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            return FakePage()

        def close(self):
            pass

    monkeypatch.setattr("worker.fitz.open", lambda path: FakeDoc())
    monkeypatch.setattr("worker.pymupdf4llm.to_markdown", lambda doc, pages: "a" * 400)

    rows = worker._extract_pages("/tmp/fake.pdf")

    assert rows[0]["token_count"] == 100


def test_annotate_index_token_counts_sets_node_span_tokens():
    node = IndexNode(node_id="node_intro", title="Intro", start_page=1, end_page=2)
    material_index = MaterialIndex(title="Lecture", doc_type="lecture_slide", page_count=2, nodes=[node])
    page_rows = {
        1: {"page_number": 1, "text_content": "a" * 400, "token_count": 100},
        2: {"page_number": 2, "text_content": "b" * 200, "token_count": 50},
    }

    worker._annotate_index_token_counts(material_index, page_rows)

    assert material_index.nodes[0].token_count == 150
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest lambda/index_materials/tests/test_worker.py -q`

Expected: fails because page extraction and node annotation do not set token counts.

- [ ] **Step 3: Add page token counts in `_extract_pages`**

Modify `lambda/index_materials/worker.py`:

```python
from token_counter import TokenCounter
```

Inside `_extract_pages`, include:

```python
                    "token_count": TokenCounter().estimate_text(md),
```

- [ ] **Step 4: Add recursive node token annotation**

Add to `lambda/index_materials/worker.py`:

```python
def _annotate_index_token_counts(material_index, page_rows: dict[int, dict]) -> None:
    TokenCounter().annotate_material_index(material_index, page_rows)
```

Call it before `store_page_index`:

```python
_annotate_index_token_counts(material_index, {row["page_number"]: row for row in page_rows_list})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest lambda/index_materials/tests/test_worker.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lambda/index_materials/worker.py lambda/index_materials/tests/test_worker.py
git commit -m "Populate PageIndex token counts during indexing"
```

## Task 3: Store And Retrieve Page Token Counts

**Files:**
- Modify: `lambda/index_materials/db.py`
- Modify: `api/pageindex_retrieval.py`
- Modify: `api/services/query/pageindex_retrieval.py`
- Test: `lambda/index_materials/tests/test_db.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write failing DB and retrieval tests**

Append to `lambda/index_materials/tests/test_db.py`:

```python
def test_store_page_texts_includes_token_count():
    calls = []

    class Conn:
        def execute(self, sql, params):
            calls.append((sql, params))

    store_page_texts(
        Conn(),
        742,
        [{"page_number": 1, "text_content": "Intro", "has_images": False, "token_count": 7}],
    )

    assert "token_count" in calls[0][0]
    assert calls[0][1][5] == 7
```

Append to `tests/test_chat_memory.py`:

```python
def test_get_page_content_returns_token_count():
    from pageindex_retrieval import get_page_content

    conn = _FakeConn([{"page_number": 1, "text_content": "Intro", "has_images": False, "token_count": 7}])

    rows = get_page_content(conn, 742, "1")

    assert rows[0]["token_count"] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest lambda/index_materials/tests/test_db.py::test_store_page_texts_includes_token_count tests/test_chat_memory.py::test_get_page_content_returns_token_count -q
```

Expected: tests fail because token counts are not stored or selected yet.

- [ ] **Step 3: Store token_count with backward-compatible fallback**

Modify `store_page_texts` in `lambda/index_materials/db.py` so the first insert includes `token_count`:

```python
        params = (
            material_id,
            row["page_number"],
            row.get("text_content"),
            row.get("has_images", False),
            row.get("section_name"),
            row.get("token_count"),
            json.dumps(row.get("section_path", [])),
        )
```

Use:

```sql
INSERT INTO material_page_text
       (material_id, page_number, text_content, has_images, section_name,
        token_count, section_path)
VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
...
    token_count = EXCLUDED.token_count,
```

Keep the existing `UndefinedColumn` fallback path without `token_count` and `section_path` for databases that have not been migrated.

- [ ] **Step 4: Return token_count from retrieval helpers**

Modify `get_page_content` in both retrieval modules:

```sql
SELECT page_number, text_content, has_images, token_count
FROM material_page_text
...
```

If the column is missing in older environments, catch `UndefinedColumn` and retry the old query, then fill `token_count` using `max(1, len(text_content or '') // 4)`.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest lambda/index_materials/tests/test_db.py tests/test_chat_memory.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lambda/index_materials/db.py api/pageindex_retrieval.py api/services/query/pageindex_retrieval.py lambda/index_materials/tests/test_db.py tests/test_chat_memory.py
git commit -m "Store and expose PageIndex token counts"
```

## Task 4: Add Retrieval Budget Math

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_memory.py`:

```python
def test_retrieval_budget_for_128k_model_window():
    budget = llm._retrieval_budget_for("gpt-4o-mini")

    assert budget["window"] == 128000
    assert budget["base_tokens"] == 15360
    assert budget["max_tokens"] == 32000
    assert budget["raw_tokens"] == 9984
    assert budget["summary_tokens"] == 5376


def test_retrieval_budget_clamps_large_model_window():
    budget = llm._retrieval_budget_for("gpt-4.1")

    assert budget["window"] == 1000000
    assert budget["base_tokens"] == 48000
    assert budget["max_tokens"] == 48000


def test_retrieval_budget_can_expand_for_broad_questions():
    budget = llm._retrieval_budget_for("gpt-4o-mini", expanded=True)

    assert budget["base_tokens"] == 15360
    assert budget["active_tokens"] == 32000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat_memory.py -q`

Expected: fails with `AttributeError: module 'llm' has no attribute '_retrieval_budget_for'`.

- [ ] **Step 3: Implement budget helpers**

Add near the existing history/output budget constants in `api/llm.py`:

```python
RETRIEVAL_BASE_CONTEXT_RATIO = 0.12
RETRIEVAL_MAX_CONTEXT_RATIO = 0.25
RETRIEVAL_RAW_RATIO = 0.65
MIN_RETRIEVAL_TOKENS = 4096
MAX_RETRIEVAL_TOKENS = 48000
SUMMARY_TOKENS_PER_CANDIDATE = 180


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _retrieval_budget_for(model: str, expanded: bool = False) -> dict:
    window = _context_window_for(model)
    base_tokens = _clamp_int(
        int(window * RETRIEVAL_BASE_CONTEXT_RATIO),
        MIN_RETRIEVAL_TOKENS,
        MAX_RETRIEVAL_TOKENS,
    )
    max_tokens = _clamp_int(
        int(window * RETRIEVAL_MAX_CONTEXT_RATIO),
        MIN_RETRIEVAL_TOKENS,
        MAX_RETRIEVAL_TOKENS,
    )
    active_tokens = max_tokens if expanded else base_tokens
    raw_tokens = int(active_tokens * RETRIEVAL_RAW_RATIO)
    summary_tokens = max(0, active_tokens - raw_tokens)
    return {
        "window": window,
        "base_tokens": base_tokens,
        "max_tokens": max_tokens,
        "active_tokens": active_tokens,
        "raw_tokens": raw_tokens,
        "summary_tokens": summary_tokens,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all existing tests plus the new budget tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Add PageIndex retrieval budget helpers"
```

## Task 5: Add Agent Scope Classification And Reserve Retrieval Budget

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_memory.py`:

```python
def test_parse_retrieval_scope_accepts_agent_outputs():
    assert llm._parse_retrieval_scope("broad") == "broad"
    assert llm._parse_retrieval_scope('{"scope":"broad"}') == "broad"
    assert llm._parse_retrieval_scope("This is specific.") == "specific"


def test_retrieval_budget_uses_scope_to_choose_base_or_max_slice():
    specific = llm._retrieval_budget_for_scope("gpt-4o-mini", "specific")
    broad = llm._retrieval_budget_for_scope("gpt-4o-mini", "broad")

    assert specific["active_tokens"] == specific["base_tokens"]
    assert broad["active_tokens"] == broad["max_tokens"]


def test_history_budget_subtracts_reserved_retrieval_tokens():
    budget = llm._history_budget(
        window=10000,
        system_text="s" * 400,
        current_user_text="u" * 400,
        reserved_retrieval_tokens=1000,
    )

    expected_without_history_cap = (
        10000
        - 100
        - llm.RESPONSE_RESERVE_TOKENS
        - 100
        - int(10000 * llm.SAFETY_MARGIN_RATIO)
        - 1000
    )
    assert budget == min(int(10000 * llm.HISTORY_CONTEXT_RATIO), expected_without_history_cap)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat_memory.py::test_retrieval_budget_uses_scope_to_choose_base_or_max_slice -q`

Expected: fails because `_retrieval_budget_for_scope` does not exist.

- [ ] **Step 3: Implement scope parsing, scope budget selection, and retrieval reservation**

Modify `_history_budget` in `api/llm.py`:

```python
def _history_budget(
    window: int,
    system_text: str,
    current_user_text: str,
    reserved_retrieval_tokens: int = 0,
) -> int:
    """Tokens left for replayed history after system prompt, response reserve,
    current user message, retrieval reserve, and a safety margin, capped to a fixed
    share of the model context window. Never negative."""
    used = (
        _estimate_tokens(system_text)
        + RESPONSE_RESERVE_TOKENS
        + _estimate_tokens(current_user_text)
        + int(window * SAFETY_MARGIN_RATIO)
        + max(0, int(reserved_retrieval_tokens or 0))
    )
    available = max(0, window - used)
    history_cap = max(0, int(window * HISTORY_CONTEXT_RATIO))
    return min(history_cap, available)
```

Add scope parsing and scope-based budget selection near the retrieval budget helpers:

```python
def _parse_retrieval_scope(text: str) -> str:
    normalized = (text or "").strip().lower()
    if not normalized:
        return "specific"
    parsed = _extract_json_object(normalized)
    if isinstance(parsed, dict):
        normalized = str(parsed.get("scope") or "").strip().lower()
    if "broad" in normalized:
        return "broad"
    return "specific"


def _retrieval_budget_for_scope(model: str, scope: str) -> dict:
    return _retrieval_budget_for(model, expanded=_parse_retrieval_scope(scope) == "broad")
```

Add a small agent classifier helper. It should make a no-tool call with `temperature=0` where the provider supports temperature. It must return only `broad` or `specific`; malformed output falls back to `specific`.

```python
_RETRIEVAL_SCOPE_PROMPT = (
    "Classify the user's course-material retrieval need as exactly one word: broad or specific.\n"
    "Use broad for questions that likely need coverage across many sections, comparisons, surveys, "
    "overviews, or cross-material synthesis.\n"
    "Use specific for narrow lookups, single definitions, page-specific questions, or questions likely "
    "answerable from a small number of pages.\n"
    "Return JSON only: {\"scope\":\"broad\"} or {\"scope\":\"specific\"}."
)


def _classify_retrieval_scope(provider: str, model: str, api_key: str, user_message: str) -> str:
    prompt = f"{_RETRIEVAL_SCOPE_PROMPT}\n\nUser message:\n{user_message}"
    try:
        if provider == "claude":
            raw = _synthesize_claude("", prompt, model, api_key)
        elif provider == "gemini":
            raw = _synthesize_gemini("", prompt, model, api_key)
        else:
            raw = _synthesize_openai("", prompt, model, api_key)
    except Exception:
        return "specific"
    return _parse_retrieval_scope(raw)
```

Update `_build_history_turns` signature and call into `_history_budget`:

```python
def _build_history_turns(
    conn,
    chat_id,
    before_index,
    model,
    system_text,
    current_user_text,
    reserved_retrieval_tokens: int = 0,
) -> list:
    """Load active-branch history and trim it to the model's budget.
    Returns kept turns as [{"role", "content"}] in chronological order."""
    prior = _load_chat_history(conn, chat_id, before_index)
    if not prior:
        return []
    window = _context_window_for(model)
    budget = _history_budget(
        window,
        system_text,
        current_user_text,
        reserved_retrieval_tokens=reserved_retrieval_tokens,
    )
    return _compose_history(prior, budget)
```

In `run_agent_pageindex`, classify scope and compute the retrieval budget before `_build_history_turns`:

```python
retrieval_scope = _classify_retrieval_scope(provider, model, api_key, user_message)
retrieval_budget = _retrieval_budget_for_scope(model, retrieval_scope)
```

Pass it into history composition:

```python
_history_turns = _build_history_turns(
    conn=conn,
    chat_id=chat_id,
    before_index=history_before_index,
    model=model,
    system_text=history_system_content,
    current_user_text=user_message,
    reserved_retrieval_tokens=retrieval_budget["active_tokens"],
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Classify PageIndex retrieval scope before budgeting"
```

## Task 6: Normalize Model-Selected Candidate Frontiers

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_memory.py`:

```python
def test_normalize_page_candidates_expands_and_dedupes_pages():
    candidates = [
        {"material_id": 742, "pages": "6-8", "reason": "definition", "priority": "core"},
        {"material_id": 742, "pages": "8,9", "reason": "continuation", "priority": "supporting"},
        {"material_id": 743, "pages": "2", "reason": "example", "priority": "background"},
    ]

    normalized, dropped = llm._normalize_page_candidates(candidates)

    assert dropped == 0
    assert normalized == [
        {"material_id": 742, "page": 6, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 7, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 8, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 9, "reason": "continuation", "priority": "supporting"},
        {"material_id": 743, "page": 2, "reason": "example", "priority": "background"},
    ]


def test_normalize_page_candidates_drops_malformed_candidates():
    candidates = [
        {"material_id": "bad", "pages": "1"},
        {"material_id": 742, "pages": "x-y"},
        {"material_id": 742, "pages": "3"},
    ]

    normalized, dropped = llm._normalize_page_candidates(candidates)

    assert dropped == 2
    assert normalized == [
        {"material_id": 742, "page": 3, "reason": "", "priority": "supporting"},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat_memory.py::test_normalize_page_candidates_expands_and_dedupes_pages -q`

Expected: fails with missing `_normalize_page_candidates`.

- [ ] **Step 3: Implement normalization helpers**

Add to `api/llm.py` near the retrieval budget helpers:

```python
def _parse_page_spec(pages: str) -> list[int]:
    page_numbers: list[int] = []
    for part in str(pages or "").split(","):
        part = part.strip()
        if not part:
            continue
        range_match = re.match(r"^(\d+)-(\d+)$", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                continue
            page_numbers.extend(range(start, end + 1))
        elif re.match(r"^\d+$", part):
            page_numbers.append(int(part))
    return [p for p in page_numbers if p > 0]


def _normalize_page_candidates(candidates: list) -> tuple[list[dict], int]:
    normalized: list[dict] = []
    seen: set[tuple[int, int]] = set()
    dropped = 0
    for candidate in candidates or []:
        try:
            material_id = int(candidate.get("material_id"))
        except (TypeError, ValueError):
            dropped += 1
            continue
        pages = _parse_page_spec(candidate.get("pages", ""))
        if not pages:
            dropped += 1
            continue
        reason = str(candidate.get("reason") or "").strip()
        priority = str(candidate.get("priority") or "supporting").strip().lower()
        if priority not in {"core", "supporting", "background"}:
            priority = "supporting"
        for page in pages:
            key = (material_id, page)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "material_id": material_id,
                    "page": page,
                    "reason": reason,
                    "priority": priority,
                }
            )
    return normalized, dropped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Normalize PageIndex candidate frontiers"
```

## Task 7: Add Section Summary Lookup Helpers

**Files:**
- Modify: `api/pageindex_retrieval.py`
- Modify: `api/services/query/pageindex_retrieval.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing unit test with a fake connection**

Append to `tests/test_chat_memory.py`:

```python
class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self.cursor_obj = _FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj


def test_get_page_section_summaries_returns_matching_sections():
    from pageindex_retrieval import get_page_section_summaries

    conn = _FakeConn(
        [
            {
                "material_id": 742,
                "material_title": "Lecture 4",
                "nodes": [
                    {"start_page": 1, "end_page": 3, "summary": "Intro", "token_count": 300},
                    {"start_page": 4, "end_page": 6, "summary": "MDP setup", "token_count": 600},
                ],
            }
        ]
    )

    summaries = get_page_section_summaries(conn, [742])

    assert summaries[(742, 4)]["summary"] == "MDP setup"
    assert summaries[(742, 4)]["token_count"] == 600
    assert summaries[(742, 6)]["title"] == "Lecture 4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_get_page_section_summaries_returns_matching_sections -q`

Expected: fails with `ImportError` for `get_page_section_summaries`.

- [ ] **Step 3: Implement helper in both retrieval modules**

Add to both `api/pageindex_retrieval.py` and `api/services/query/pageindex_retrieval.py`:

```python
def get_page_section_summaries(conn, material_ids: list[int]) -> dict[tuple[int, int], dict]:
    if not material_ids:
        return {}
    cursor = conn.cursor()
    cursor.execute(
        """SELECT cmi.material_id, cmi.material_title, mpi.index_json->'nodes' AS nodes
           FROM course_material_index cmi
           LEFT JOIN material_page_index mpi USING (material_id)
           WHERE cmi.material_id = ANY(%s)
           ORDER BY cmi.material_id""",
        (material_ids,),
    )
    rows = cursor.fetchall()
    cursor.close()
    summaries: dict[tuple[int, int], dict] = {}
    for row in rows:
        material_id = row["material_id"]
        title = row.get("material_title") or f"Material {material_id}"
        for section in _extract_page_summaries(row.get("nodes") or []):
            for page in range(section["start_page"], section["end_page"] + 1):
                summaries[(material_id, page)] = {
                    "material_id": material_id,
                    "title": title,
                    "page": page,
                    "start_page": section["start_page"],
                    "end_page": section["end_page"],
                    "summary": section["summary"],
                    "token_count": section.get("token_count") or max(1, len(section.get("summary") or "") // 4),
                }
    return summaries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_memory.py::test_get_page_section_summaries_returns_matching_sections -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/pageindex_retrieval.py api/services/query/pageindex_retrieval.py tests/test_chat_memory.py
git commit -m "Add PageIndex section summary lookup"
```

## Task 8: Materialize Candidates Into Raw And Summary Evidence

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_memory.py`:

```python
def test_materialize_page_candidates_splits_raw_and_summary(monkeypatch):
    candidates = [
        {"material_id": 742, "page": 1, "reason": "definition", "priority": "core"},
        {"material_id": 742, "page": 2, "reason": "setup", "priority": "supporting"},
        {"material_id": 742, "page": 3, "reason": "example", "priority": "supporting"},
    ]
    budget = {
        "raw_tokens": 160,
        "summary_tokens": 500,
    }

    def fake_get_page_content(conn, material_id, pages):
        token_counts = {1: 100, 2: 80, 3: 40}
        page = int(pages)
        return [{"page_number": page, "text_content": f"raw page {pages}", "has_images": False, "token_count": token_counts[page]}]

    def fake_get_page_section_summaries(conn, material_ids):
        return {
            (742, 2): {
                "material_id": 742,
                "title": "Lecture",
                "page": 2,
                "start_page": 2,
                "end_page": 2,
                "summary": "summary page 2",
                "token_count": 80,
            }
        }

    monkeypatch.setattr(llm, "_get_page_content_for_materialization", fake_get_page_content)
    monkeypatch.setattr(llm, "_get_page_section_summaries_for_materialization", fake_get_page_section_summaries)

    raw, summaries, meta = llm._materialize_page_candidates(object(), candidates, budget)

    assert len(raw) == 2
    assert "raw page 1" in raw[0]
    assert "raw page 3" in raw[1]
    assert summaries == [
        "Material 742 (Lecture), page 2: summary page 2\nReason selected: setup"
    ]
    assert meta["raw_pages"] == 2
    assert meta["raw_tokens"] == 140
    assert meta["summary_pages"] == 1


def test_materialize_page_candidates_tracks_summary_omissions(monkeypatch):
    candidates = [
        {"material_id": 742, "page": 1, "reason": "", "priority": "core"},
        {"material_id": 742, "page": 2, "reason": "", "priority": "supporting"},
        {"material_id": 742, "page": 3, "reason": "", "priority": "supporting"},
    ]
    budget = {"raw_tokens": 1, "summary_tokens": 1}

    monkeypatch.setattr(
        llm,
        "_get_page_content_for_materialization",
        lambda conn, material_id, pages: [{"page_number": int(pages), "text_content": "raw", "has_images": False, "token_count": 50}],
    )
    monkeypatch.setattr(
        llm,
        "_get_page_section_summaries_for_materialization",
        lambda conn, material_ids: {
            (742, 2): {"material_id": 742, "title": "Lecture", "page": 2, "start_page": 2, "end_page": 2, "summary": "summary two"},
            (742, 3): {"material_id": 742, "title": "Lecture", "page": 3, "start_page": 3, "end_page": 3, "summary": "summary three"},
        },
    )

    raw, summaries, meta = llm._materialize_page_candidates(object(), candidates, budget)

    assert len(raw) == 1
    assert summaries == []
    assert meta["omitted_summary_pages"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat_memory.py::test_materialize_page_candidates_splits_raw_and_summary -q`

Expected: fails with missing `_materialize_page_candidates`.

- [ ] **Step 3: Implement materialization helpers**

Add to `api/llm.py`:

```python
def _get_page_content_for_materialization(conn, material_id: int, pages: str) -> list[dict]:
    from pageindex_retrieval import get_page_content

    return get_page_content(conn, material_id, pages)


def _get_page_section_summaries_for_materialization(conn, material_ids: list[int]) -> dict:
    from pageindex_retrieval import get_page_section_summaries

    return get_page_section_summaries(conn, material_ids)


def _format_raw_page_result(material_id: int, rows: list[dict]) -> str:
    parts = []
    for row in rows:
        parts.append(
            f"Material {material_id}, page {row['page_number']}\n"
            f"{row.get('text_content') or '[No text extracted]'}"
        )
    return "\n\n".join(parts)


def _candidate_priority_key(candidate: dict) -> tuple[int, int]:
    priority_rank = {"core": 0, "supporting": 1, "background": 2}
    return (priority_rank.get(candidate.get("priority"), 1), candidate.get("_order", 0))


def _materialize_page_candidates(conn, candidates: list[dict], budget: dict) -> tuple[list[str], list[str], dict]:
    raw_evidence: list[str] = []
    summary_evidence: list[str] = []
    meta = {
        "raw_pages": 0,
        "raw_tokens": 0,
        "raw_material_ids": [],
        "summary_pages": 0,
        "summary_tokens": 0,
        "omitted_summary_pages": 0,
    }
    candidates_with_order = [
        {**candidate, "_order": index}
        for index, candidate in enumerate(candidates or [])
    ]
    raw_budget = max(0, int(budget.get("raw_tokens") or 0))
    raw_candidate_keys: set[tuple[int, int]] = set()
    summary_candidates: list[dict] = []

    for candidate in sorted(candidates_with_order, key=_candidate_priority_key):
        rows = _get_page_content_for_materialization(
            conn,
            candidate["material_id"],
            str(candidate["page"]),
        )
        row_tokens = sum(
            int(row.get("token_count") or _estimate_tokens(row.get("text_content") or ""))
            for row in rows
        )
        if rows and meta["raw_tokens"] + row_tokens <= raw_budget:
            raw_evidence.append(_format_raw_page_result(candidate["material_id"], rows))
            meta["raw_pages"] += len(rows)
            meta["raw_tokens"] += row_tokens
            meta["raw_material_ids"].append(candidate["material_id"])
            raw_candidate_keys.add((candidate["material_id"], candidate["page"]))
        else:
            summary_candidates.append(candidate)

    material_ids = _dedupe_preserve_order([c["material_id"] for c in summary_candidates])
    summaries_by_page = _get_page_section_summaries_for_materialization(conn, material_ids)
    summary_budget = max(0, int(budget.get("summary_tokens") or 0))
    running_tokens = 0
    for candidate in summary_candidates:
        section = summaries_by_page.get((candidate["material_id"], candidate["page"]))
        if not section:
            meta["omitted_summary_pages"] += 1
            continue
        line = (
            f"Material {candidate['material_id']} ({section['title']}), page {candidate['page']}: "
            f"{section['summary']}"
        )
        if candidate.get("reason"):
            line += f"\nReason selected: {candidate['reason']}"
        line_tokens = _estimate_tokens(line)
        if running_tokens + line_tokens > summary_budget:
            meta["omitted_summary_pages"] += 1
            continue
        summary_evidence.append(line)
        running_tokens += line_tokens
        meta["summary_pages"] += 1
        meta["summary_tokens"] += line_tokens

    return raw_evidence, summary_evidence, meta
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Materialize PageIndex candidate evidence under budget"
```

## Task 9: Add Candidate Tool Schema And Prompt Instructions

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_memory.py`:

```python
def test_pageindex_tool_list_includes_candidate_frontier_tool():
    tool_names = [tool["function"]["name"] for tool in llm._pageindex_tool_list(web_search_enabled=False)]

    assert "select_page_candidates" in tool_names


def test_retrieval_prompt_describes_budgeted_candidate_frontier():
    prompt = llm._build_pageindex_retrieval_system_context(
        "<course_materials></course_materials>",
        web_search_enabled=False,
        clarification_depth=0,
    )

    assert "select_page_candidates" in prompt
    assert "broad" in prompt.lower()
    assert "raw text" in prompt.lower()
    assert "summary" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat_memory.py::test_pageindex_tool_list_includes_candidate_frontier_tool -q`

Expected: fails because the tool does not exist.

- [ ] **Step 3: Add prompt text and tool schema**

Modify `_PAGEINDEX_TOOL_USE` in `api/llm.py` to include:

```python
    "\n\n**Broad candidate frontier**: For broad, survey, comparative, cross-topic, or "
    "multi-section questions, call `select_page_candidates(candidates)` after inspecting "
    "the routing tree. Include every plausible candidate range in ranked order. The backend "
    "will admit raw text for the top budgeted subset and compact the rest into summaries. "
    "Use direct `get_page_content` for narrow lookups where only one small range is needed."
```

Add a `select_page_candidates` function tool to `_pageindex_tool_list` before `propose_generation`:

```python
{
    "type": "function",
    "function": {
        "name": "select_page_candidates",
        "description": (
            "Submit a ranked frontier of candidate page ranges for broad questions. "
            "The backend will fetch raw text for the top budgeted subset and use summaries for the rest."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "material_id": {"type": "integer"},
                            "pages": {"type": "string", "description": "Page spec such as '5-7', '3,8', or '12'."},
                            "reason": {"type": "string"},
                            "priority": {"type": "string", "enum": ["core", "supporting", "background"]},
                        },
                        "required": ["material_id", "pages"],
                    },
                }
            },
            "required": ["candidates"],
        },
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Add PageIndex candidate frontier tool"
```

## Task 10: Wire Candidate Tool Dispatch Into All Provider Loops

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing dispatch test**

Append to `tests/test_chat_memory.py`:

```python
def test_dispatch_select_page_candidates_materializes_evidence(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_materialize_page_candidates",
        lambda conn, candidates, budget: (
            ["raw evidence"],
            ["summary evidence"],
            {
                "raw_pages": 1,
                "raw_tokens": 50,
                "raw_material_ids": [742],
                "summary_pages": 1,
                "summary_tokens": 20,
                "omitted_summary_pages": 0,
            },
        ),
    )
    grounding_refs = []

    result, meta = llm._dispatch_candidate_frontier(
        conn=object(),
        args={"candidates": [{"material_id": 742, "pages": "1"}]},
        budget={"raw_tokens": 100, "summary_tokens": 100},
        grounding_refs=grounding_refs,
    )

    assert result == "Candidate frontier accepted: 1 raw pages, 1 summary pages, 0 summary pages omitted."
    assert meta["raw_evidence"] == ["raw evidence"]
    assert meta["summary_evidence"] == ["summary evidence"]
    assert grounding_refs == ["material:742"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_dispatch_select_page_candidates_materializes_evidence -q`

Expected: fails with missing `_dispatch_candidate_frontier`.

- [ ] **Step 3: Implement candidate dispatch helper**

Add to `api/llm.py` near `_dispatch_pageindex_tool`:

```python
def _dispatch_candidate_frontier(conn, args: dict, budget: dict, grounding_refs: list) -> tuple[str, dict]:
    candidates, dropped = _normalize_page_candidates(args.get("candidates") or [])
    raw_evidence, summary_evidence, materialization_meta = _materialize_page_candidates(
        conn,
        candidates,
        budget,
    )
    for material_id in _dedupe_preserve_order(materialization_meta.get("raw_material_ids") or []):
        grounding_refs.append(f"material:{material_id}")
    meta = {
        "raw_evidence": raw_evidence,
        "summary_evidence": summary_evidence,
        "candidate_count": len(candidates),
        "dropped_candidates": dropped,
        **materialization_meta,
    }
    result = (
        "Candidate frontier accepted: "
        f"{meta['raw_pages']} raw pages, "
        f"{meta['summary_pages']} summary pages, "
        f"{meta['omitted_summary_pages']} summary pages omitted."
    )
    return result, meta
```

Use the existing `retrieval_budget` computed from the agent scope classification before history composition. Do not classify the query again inside provider-specific tool loops.

For each provider branch, when a tool call name is `select_page_candidates`, call `_dispatch_candidate_frontier`, then append `raw_evidence` to `course_evidence` and `summary_evidence` to a new `summary_evidence` list.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Wire PageIndex candidate frontier dispatch"
```

## Task 11: Include Summary Evidence In Synthesis

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_memory.py`:

```python
def test_format_pageindex_evidence_includes_candidate_summaries():
    evidence = llm._format_pageindex_evidence(
        ["raw course"],
        ["web result"],
        ["summary course"],
    )

    assert "Raw retrieved course material:" in evidence
    assert "Candidate coverage summaries:" in evidence
    assert "summary course" in evidence
    assert "Web search results" in evidence


def test_synthesis_prompt_distinguishes_raw_and_summary_evidence():
    prompt = llm._build_pageindex_synthesis_system_context(
        "Candidate coverage summaries:\nsummary",
        clarification_depth=0,
    )

    assert "Raw material is direct evidence" in prompt
    assert "Candidate coverage summaries" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat_memory.py::test_format_pageindex_evidence_includes_candidate_summaries -q`

Expected: fails because `_format_pageindex_evidence` does not accept summary evidence yet.

- [ ] **Step 3: Update evidence formatting and synthesis instruction**

Change `_PAGEINDEX_SYNTHESIS_INSTRUCTION` to include:

```python
    "Raw material is direct evidence. Candidate coverage summaries are compact course-index "
    "evidence for breadth and orientation; use them for coverage and caveats, but do not invent "
    "details that require raw text if only a summary was provided."
```

Change `_format_pageindex_evidence` signature and body:

```python
def _format_pageindex_evidence(course_contents: list, web_contents: list, summary_contents: list | None = None) -> str:
    parts = []
    if course_contents:
        parts.append(
            "Raw retrieved course material:\n"
            + "\n\n---\n\n".join(str(c) for c in course_contents)
        )
    if summary_contents:
        parts.append(
            "Candidate coverage summaries:\n"
            + "\n\n---\n\n".join(str(c) for c in summary_contents)
        )
    if web_contents:
        parts.append(
            "Web search results - use these to answer questions not covered by course materials:\n"
            + "\n\n---\n\n".join(str(c) for c in web_contents)
        )
    return "\n\n".join(parts)
```

Update all call sites to pass `summary_evidence`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Include PageIndex summary evidence in synthesis"
```

## Task 12: Add Budget Trace Metadata And Regression Coverage

**Files:**
- Modify: `api/llm.py`
- Test: `tests/test_chat_memory.py`

- [ ] **Step 1: Write the failing metadata test**

Append to `tests/test_chat_memory.py`:

```python
def test_retrieval_budget_trace_contains_candidate_counts():
    trace = llm._candidate_frontier_trace(
        iteration=2,
        args={"candidates": [{"material_id": 742, "pages": "1-3"}]},
        meta={
            "candidate_count": 3,
            "dropped_candidates": 0,
            "raw_pages": 2,
            "raw_tokens": 1500,
            "summary_pages": 1,
            "summary_tokens": 200,
            "omitted_summary_pages": 0,
        },
        budget={"active_tokens": 15360, "raw_tokens": 9984, "summary_tokens": 5376},
    )

    assert trace["tool"] == "select_page_candidates"
    assert trace["candidate_count"] == 3
    assert trace["raw_pages"] == 2
    assert trace["raw_tokens"] == 1500
    assert trace["summary_pages"] == 1
    assert trace["retrieval_budget_tokens"] == 15360
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_memory.py::test_retrieval_budget_trace_contains_candidate_counts -q`

Expected: fails with missing `_candidate_frontier_trace`.

- [ ] **Step 3: Implement trace helper and use it in provider loops**

Add to `api/llm.py`:

```python
def _candidate_frontier_trace(iteration: int, args: dict, meta: dict, budget: dict) -> dict:
    return {
        "tool": "select_page_candidates",
        "args": args,
        "iteration": iteration,
        "candidate_count": meta.get("candidate_count", 0),
        "dropped_candidates": meta.get("dropped_candidates", 0),
        "raw_pages": meta.get("raw_pages", 0),
        "raw_tokens": meta.get("raw_tokens", 0),
        "summary_pages": meta.get("summary_pages", 0),
        "summary_tokens": meta.get("summary_tokens", 0),
        "omitted_summary_pages": meta.get("omitted_summary_pages", 0),
        "retrieval_budget_tokens": budget.get("active_tokens", 0),
        "raw_budget_tokens": budget.get("raw_tokens", 0),
        "summary_budget_tokens": budget.get("summary_tokens", 0),
    }
```

Use this helper instead of the generic `{"tool": name, "args": args, "iteration": iteration}` trace for `select_page_candidates` calls.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_chat_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Run syntax verification**

Run: `python3 -m py_compile api/llm.py api/pageindex_retrieval.py api/services/query/pageindex_retrieval.py`

Expected: exits successfully. Existing warnings are acceptable only if they predate this change.

- [ ] **Step 6: Commit**

```bash
git add api/llm.py tests/test_chat_memory.py
git commit -m "Trace PageIndex candidate frontier budgets"
```

## Final Verification

- [ ] Run focused unit tests:

```bash
pytest tests/test_chat_memory.py -q
```

Expected: PASS.

- [ ] Run PageIndex agent tests to identify stale expectations:

```bash
pytest tests/test_pageindex_agent.py -q
```

Expected: may still contain existing stale failures around clean synthesis payloads and unpatched image recall. Do not hide new failures; document any failures separately.

- [ ] Run syntax verification:

```bash
python3 -m py_compile api/llm.py api/pageindex_retrieval.py api/services/query/pageindex_retrieval.py
```

Expected: exits successfully.

- [ ] Review git diff:

```bash
git diff --stat
git diff -- api/llm.py api/pageindex_retrieval.py api/services/query/pageindex_retrieval.py tests/test_chat_memory.py
```

Expected: changes are scoped to retrieval budgeting, candidate frontier materialization, and tests.
