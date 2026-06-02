# Build Correctness Audit — review-current-state branch — 2026-06-02

> Audit of the `review-current-state` branch, which implemented the 8 BUILD tasks
> in `docs/2026-05-31-feature-review-and-build-roadmap.md`. Scope: **build correctness
> and functional bugs only.** Each issue below is self-contained — file, line, root
> cause, repro, and a concrete fix — so it can be picked up and resolved independently.

## Verification performed

- `npm run build` — ✅ passes (only the pre-existing >500 kB chunk-size warning).
- `python -m pytest tests/` — ⚠️ **collection error** (see L-1) + 3 pre-existing failures
  unrelated to this branch (see "Out of scope" below).
- Individual backend test modules pass when run in isolation.
- Manual code inspection of every changed `api/`, `lambda/`, and `src/` file for the 8 tasks.

## Severity legend

- **CRITICAL** — feature is dead on arrival (crash / 100% failure).
- **HIGH** — feature silently fails or produces clearly wrong output in the normal path.
- **MEDIUM** — degraded behaviour in a secondary path.
- **LOW** — test/infra/deploy hygiene; no user-facing impact on its own.

> **Why the test suite did not catch these:** `tests/conftest.py` stubs `psycopg`,
> `boto3`, etc. with `MagicMock`. `MagicMock()[0]` and friends never raise, so the
> dict-row indexing bugs (C-2, C-3) and other DB-shape issues pass under tests but
> fail against a real Postgres. Frontend has no JS test runner (L-3), so the React
> crash (C-1) and the Build wiring bug (H-1) were never exercised.

---

## CRITICAL

### C-1 — FlashcardViewer crashes on every render (temporal dead zone)
**File:** `src/FlashcardViewer.jsx`
**Lines:** `226` (effect dependency array) and `214` (effect body) reference `displayCards`;
it is not declared until `228` (`const displayCards = useMemo(...)`).

**Root cause:** The play-loop `useEffect` (lines 207–226) lists `displayCards` in its
dependency array. The dependency array is evaluated **during render**, top-to-bottom,
*before* the `const displayCards` declaration at line 228 executes. `const` bindings are
in the temporal dead zone until their declaration runs, so every render throws
`ReferenceError: Cannot access 'displayCards' before initialization`.

**Impact:** The entire Flashcard viewer (the P0 "Flashcard Play mode + rating" feature)
crashes on mount. The build does not catch this; it only manifests at runtime.

**Repro:** Open any flashcard generation → blank screen / React error boundary.

**Fix:** Move the `const displayCards = useMemo(...)` block (currently lines 228–236)
*above* the play-loop `useEffect` (line 207). No logic change needed — purely reorder
so the declaration precedes both uses.

---

### C-2 — Course stats endpoint 500s (dict_row indexed by integer)
**File:** `api/course.py`
**Lines:** `86, 92, 98, 104, 110, 120` — `mat_count = cursor.fetchone()[0]` (×6).

**Root cause:** The connection pool is created with `row_factory=psycopg.rows.dict_row`
(`api/db.py:23`), so `cursor.fetchone()` returns a `dict`. For `SELECT COUNT(*) ...`
the row is `{"count": N}`, and `row[0]` raises `KeyError: 0` (verified empirically).
This `fetchone()[0]` pattern is **new on this branch and appears nowhere else** in `api/`.

**Impact:** `GET /api/course?action=stats` returns 500. `CourseStatsWidget` never loads
(Dashboard Analytics task is non-functional).

**Fix:** Alias the aggregate and read by name, e.g.
`SELECT COUNT(*) AS n FROM materials WHERE course_id = %s` then `cursor.fetchone()["n"]`,
for all six queries. (Or `next(iter(cursor.fetchone().values()))`.)

---

### C-3 — Saved prompts list & create 500 (dict_row indexed by integer)
**File:** `api/prompts.py`
**Lines:** `50` (`{"id": r[0], "title": r[1], "body": r[2], "created_at": r[3]...}` in
`do_GET`) and `90` (same shape from `row[0..3]` in `do_POST`).

**Root cause:** Same as C-2 — rows are `dict`s (`dict_row`), so integer indexing raises
`KeyError`. `do_DELETE` is unaffected (it uses `cursor.rowcount`).

**Impact:** `GET /api/prompts` (list) and `POST /api/prompts` (create) both 500. The
Saved Prompt Library picker can never load or save a prompt.

**Fix:** Index by column name:
`{"id": r["id"], "title": r["title"], "body": r["body"], "created_at": r["created_at"].isoformat()}`
in both `do_GET` and `do_POST`.

---

## HIGH

### H-1 — Generate-from-chat "Build" fails for flashcards and reports
**Files:** `src/ChatTab.jsx:1971` (`handleBuildGeneration`), `api/flashcards.py:454`
(`_generate`), `api/reports.py:783` (`_generate`).

**Root cause:** `handleBuildGeneration` POSTs `{action:'generate', course_id, title,
topic, material_ids, conversation_context, ...params}` with **no `generation_id`**.
- `api/quiz.py::_generate` supports a *direct* path (course_id + counts) → quiz Build works.
- `api/flashcards.py::_generate` requires `generation_id` (line 456: `'generation_id required'`).
- `api/reports.py::_generate` requires `generation_id` (line 784: `'generation_id required'`).

Flashcards and reports only build from a **draft** created by a prior `action:'estimate'`
call. The Build handler never performs that step, so the request 400s. The error is
swallowed by the `catch` (ChatTab.jsx:1997) — the button just reverts from "Queuing…",
giving the user no feedback and queuing nothing.

**Impact:** Build button works only for quiz proposals; silently no-ops for flashcards
and reports.

**Fix (either):**
- In `handleBuildGeneration`, for `flashcards`/`reports` first POST `action:'estimate'`
  to obtain a draft `generation_id`, then POST `action:'generate'` with that id
  (and `conversation_context`); or
- Add a direct (draft-less) create+enqueue path to `flashcards._generate` and
  `reports._generate` mirroring `quiz._generate`.

---

### H-2 — Claude/Gemini PageIndex leak `<REPLY>`/`<META>` wrapper into the streamed UI
**File:** `api/llm.py`
**Lines:** Claude `1910–1912` and Gemini `1990–1992` call
`_pageindex_stream_call_claude` / `_pageindex_stream_call_gemini` with `on_event`
**directly**. The OpenAI path instead wraps it via `_stream_with_filter`
(defined `1894–1905`, used at `2060`).

**Root cause:** The PageIndex system prompt instructs the model to wrap its final answer
as `<REPLY>…</REPLY><META>…</META>` (parsed afterward by `_parse_synthesis_json`, lines
286–294). The OpenAI branch streams through `_ReplyStreamFilter` (lines 1394+), which
strips the wrapper live so the user sees only the reply body. The Claude and Gemini
branches emit raw text deltas straight to `on_event`, so the literal `<REPLY>` tags and
the `<META>` JSON (summary / follow-ups) stream verbatim into the chat bubble. The
*stored* message is still clean (it is re-parsed), so streamed text ≠ saved text.

**Impact:** When PageIndex is active and the user selects Claude or Gemini, the live
response shows raw tags / meta JSON. Visible, confusing UX regression vs. OpenAI.

**Fix:** Route the Claude/Gemini text deltas through a `_ReplyStreamFilter` exactly like
`_stream_with_filter`: feed `{"type":"text"}` events into a filter and pass other events
through, then `flush()` after each streaming call. Either thread a filtered `on_event`
into `_pageindex_stream_call_claude/_gemini`, or wrap their text emission the same way.

---

## MEDIUM

### M-1 — Claude/Gemini PageIndex loops have no forced-synthesis fallback
**File:** `api/llm.py`
**Lines:** OpenAI fallback at `2136–2155`; Claude returns at `1974–1985`, Gemini at
`2045–2056` with no equivalent.

**Root cause:** When `MAX_TOOL_ITERATIONS` is exhausted while the model is still calling
tools, the OpenAI loop makes one final tool-less call to synthesize an answer from the
pages already fetched (`if not final_text and grounding_refs:`). The Claude and Gemini
branches instead fall straight to
`final_text = "I could not find relevant content in the course materials."`,
discarding all retrieved context.

**Impact:** On harder questions that exhaust the tool budget, Claude/Gemini return a
"not found" message even though relevant pages were retrieved — strictly worse answers
than OpenAI for the same query.

**Fix:** After each provider loop, if `not final_text and grounding_refs`, issue one
final streaming call **without tools** (Claude: omit `tools`; Gemini: omit `tools`),
parse with `_parse_synthesis_json`, and use that as `final_text` — mirroring lines
2136–2155.

---

## LOW (test / deploy hygiene)

### L-1 — Full `pytest tests/` run aborts at collection
**File:** `tests/test_chat_search_snippets.py:9–14` (and the read at `:36`).

**Root cause:** The module installs an **empty** `types.ModuleType("llm")` into
`sys.modules` (via `_make_stub(... "llm" ...)`) and never restores it. Because pytest
collects `test_chat_search_snippets.py` before `test_pageindex_agent.py` (alphabetical),
the latter's `from llm import _format_routing_index_block` (`test_pageindex_agent.py:4`)
resolves to the empty stub → `ImportError: cannot import name ... (unknown location)`,
which interrupts the **entire** collection. Both modules pass when run individually.

**Impact:** CI/`pytest tests/` cannot run the suite in one invocation. No product impact.

**Fix:** Make the stub non-destructive — save and restore `sys.modules` entries in a
fixture/teardown, or only stub names not needed by other modules, or have
`test_chat_search_snippets.py` import the real `api/llm.py` like `test_pageindex_agent.py`
does. (A repo-level `conftest.py` that snapshots/restores `sys.modules` around each
module would also fix it.)

### L-2 — Required schema migrations are not in version control
**Files:** `migrations/` (highest existing is `007_chat_search_gin_indexes.sql`).

**Root cause:** This branch's features depend on schema that has **no migration file**
(per project convention simple migrations are run by hand, but they must still be applied
and ideally tracked):
- `saved_prompts` table — used by `api/prompts.py`.
- `conversation_context` column on `quiz_generations`, `flashcard_generations`,
  `report_generations` — written by the GFC persistence paths and read by the Lambda
  `_merge_conversation_context`.
- `default_ai_provider`, `default_ai_model` columns on `courses` — read/written by
  `api/course.py` PUT and `api/courses.py::update`.

**Impact:** If any of these are not applied in an environment, the corresponding endpoint
500s (undefined column / relation). C-3 will also surface here if `saved_prompts` is missing.

**Fix:** Confirm all four schema objects exist in every target DB; add the DDL as
`migrations/008_*.sql` (or document it) so deploys are reproducible.

### L-3 — JS unit test cannot run (no test runner configured)
**Files:** `src/utils/flashcardRatings.test.js`, `package.json` (scripts: only
`dev`/`build`/`preview`; no `vitest`/`jest` dependency).

**Root cause:** A `*.test.js` was added but there is no JavaScript test runner, so it is
never executed and gives a false sense of coverage (it would have caught C-1's sibling
logic, not C-1 itself).

**Fix:** Either add `vitest` + a `test` script, or remove the orphan test file.

---

## Out of scope (pre-existing on `main`, NOT introduced by this branch)

Recorded so they are not mistaken for regressions — confirmed failing on `main` too:

- `tests/test_flashcards_phase2_validation.py::test_worker_normalization_aliases_and_count_trim`
- `tests/test_flashcards_phase2_validation.py::test_worker_normalization_rejects_missing_front_or_back`
- `tests/test_reports_validation.py::test_prompt_shapes_for_builtins_match_task_2`
  (expects `"page_count":2` in the study-guide system prompt).

---

## Suggested resolution order

1. **C-1** (one-line reorder; unblocks the whole Flashcard feature).
2. **C-2, C-3** (column-name reads; unblock Dashboard + Saved Prompts).
3. **L-2** (apply/verify migrations — prerequisite for C-3 and the GFC/course-default features).
4. **H-1** (Build wiring for flashcards/reports).
5. **H-2, M-1** (Claude/Gemini PageIndex parity — streaming filter + forced-synthesis).
6. **L-1, L-3** (test infra).
