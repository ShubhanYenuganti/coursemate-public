# Manual Test Plan — Roadmap Features + Bug Fixes — 2026-06-02

Step-by-step manual QA for the 8 features built on `review-current-state`
(`docs/2026-05-31-feature-review-and-build-roadmap.md`) and the bug fixes from
`docs/2026-06-02-build-correctness-audit.md`.

Each test lists **Preconditions → Steps → Expected**, and notes which fix/feature it
validates. Run the features roughly in the order below — earlier ones set up data the
later ones reuse.

---

## 0. Environment setup (do this first) VERIFIED

1. **Apply the schema migration** (required, or several features 500):
   ```bash
   psql "$DATABASE_URL" -f migrations/008_feature_roadmap_schema.sql
   ```
   Verifies the `saved_prompts` table, `courses.default_ai_provider/default_ai_model`,
   and `conversation_context` columns exist.
2. **Environment variables** (server / `vercel dev` env):
   - `PAGEINDEX_RAG_ENABLED=true` — PageIndex agentic loop (default on; needed for #1, #4, #7).
   - `AGENTIC_WEB_SEARCH_ENABLED=true` — server gate for web search (#7).
   - `TAVILY_API_KEY=…` — required for web search to actually return results (#7).
3. **API keys** — in the app, store a key for **OpenAI, Anthropic (Claude), and Gemini**
   under the user's settings (each provider path is tested separately).
4. **Run the app** (per `README.md`):
   ```bash
   npm run dev          # frontend (vite)
   vercel dev           # Python API (separate terminal)
   ```
5. **Seed data**: create a course **as the owner**, upload **≥2 materials** (PDFs with a
   few pages), wait for indexing to finish (status “ready”), and open one chat with a few
   messages.

### Quick automated sanity (optional, ~5s)
```bash
python -m pytest tests/ -q --ignore=tests/integration   # 80 passed (+3 pre-existing fails)
npm test                                                 # 4 passed
npm run build                                            # ✓ built
```

---

## 1. Per-Course Model Default  (feature #6) VERIFIED

**Validates:** course default storage + chat seeding precedence (localStorage > course > global).

**Preconditions:** You are the course **owner**. Migration 008 applied.

**Steps & Expected:**
1. On the course home, open the **course settings / AI model** editor (owner-only).
   - *Expected:* a provider + model picker is visible. Non-owners do **not** see it.
2. Set provider = **Claude**, model = a Claude model → **Save**.
   - *Expected:* `PUT /api/course` returns 200; no error toast. Reload — selection persists.
3. In a **fresh browser profile / incognito** (so `localStorage` has no
   `chat_selected_model`), open the course → **Chat** tab.
   - *Expected:* the chat model picker is pre-seeded to **Claude** (the course default).
4. Manually change the chat model to OpenAI and send a message, then reload.
   - *Expected:* chat now shows **OpenAI** — `localStorage` overrides the course default.

---

## 2. Dashboard Analytics Widget  (feature #7 / DA) VERIFIED

**Validates:** `GET /api/course?action=stats` and `CourseStatsWidget`. **Regression for C-2**
(stats endpoint previously 500’d on `cursor.fetchone()[0]`).

**Steps & Expected:**
1. Open the course home view.
   - *Expected:* the **stats widget** renders counts for materials, quizzes, flashcards,
     reports, chats, and messages. **No 500 / blank widget.**
2. Open devtools → Network → find the `action=stats` request.
   - *Expected:* HTTP **200** with a JSON body of integer counts (not a 500 with `KeyError`).
3. Generate a quiz (or upload a material), return to the home view.
   - *Expected:* the corresponding count increments.

---

## 3. Saved Prompt Library  (feature #8 / SPL) VERIFIED

**Validates:** `GET/POST/DELETE /api/prompts` + compose-bar picker. **Regression for C-3**
(list/create previously 500’d on dict-row indexing).

**Steps & Expected:**
1. In the chat compose bar, type a reusable prompt, then click the **saved-prompts /
   bookmark** button → **Save current text** (give it a title).
   - *Expected:* `POST /api/prompts` → **201**; the prompt appears in the picker. **No 500.**
2. Clear the compose bar, open the picker, select the saved prompt.
   - *Expected:* the prompt text is inserted into the compose bar (editable before send).
3. Reload the page, reopen the picker.
   - *Expected:* `GET /api/prompts` → **200**; saved prompt still listed.
4. Delete the prompt from the picker.
   - *Expected:* `DELETE /api/prompts?id=…` → 200; it disappears. Deleting a non-existent id → 404.
5. Log in as a **different user**.
   - *Expected:* that user does **not** see the first user's prompts (per-user scoping).

---

## 4. Single-Course Chat Search (snippet + jump-to)  (feature #5 / CS) VERIFIED

**Validates:** message-level search results with snippet + deep-link to the matched message.

**Preconditions:** A chat with several messages, at least one containing a distinctive word
(e.g. “handshake”).

**Steps & Expected:**
1. Open the course **chat search** (search button in the chat header).
2. Search a word that appears in a **chat title** → *Expected:* title matches listed.
3. Search a word that appears only in **message content** (e.g. “handshake”).
   - *Expected:* a content result shows a **snippet** with the term highlighted
     (`<mark>…</mark>`), plus a hit count for that chat.
4. Click a content result.
   - *Expected:* the app opens that chat **and scrolls to / highlights the matched message**
     (not just the top of the chat).
5. Search a partial last word (e.g. “robo” for “Robotics”).
   - *Expected:* prefix matching still finds title matches.

---

## 5. Flashcard Play Mode + Rating  (feature #2) VERIFIED

**Validates:** Play study mode + per-card thumb rating. **Regression for C-1** (viewer
previously crashed on render due to a temporal-dead-zone `ReferenceError`).

**Preconditions:** A flashcard generation with ≥3 cards exists (generate one if needed).

**Steps & Expected:**
1. Open the flashcard generation in the viewer.
   - *Expected (C-1):* the viewer **renders** — no blank screen / React error boundary.
2. Click a card.
   - *Expected:* it flips front→back.
3. Click **Play**.
   - *Expected:* auto-advance study mode starts — each card shows, flips to the answer,
     then advances (~4s cadence); a progress indicator advances; it **stops on the last card**.
4. Click **Play** again to toggle it off mid-session.
   - *Expected:* auto-advance pauses.
5. Click **thumb up** on a card, then **thumb down** on another.
   - *Expected:* the selected thumb shows an active (colored) state; clicking the same thumb
     again clears it.
6. Reload the page and reopen the same generation.
   - *Expected:* the thumb ratings persist (localStorage, keyed per `generationId`).
7. Open a **different** generation.
   - *Expected:* ratings are independent (not shared across generations).

---

## 6. PageIndex for Claude & Gemini  (feature #1)

**Validates:** the agentic PageIndex loop honors the selected provider (not hardcoded to
OpenAI). **Regression for H-2** (no `<REPLY>`/`<META>` tag leakage) and **M-1** (forced
synthesis on long retrievals).

**Preconditions:** `PAGEINDEX_RAG_ENABLED=true`; Claude + Gemini keys stored; a course with
indexed multi-page materials.

**Steps & Expected (run once per provider — Claude, then Gemini):**
1. In chat, select the **Claude** model, select 1–2 materials as context, and ask a
   factual question answerable from a specific page (e.g. “What does page 3 of <material>
   define as X?”).
   - *Expected:* a **live retrieval status / tool-trace** appears (“Retrieving pages…”), the
     answer cites **page-level sources**, and the source panel lists the fetched pages.
2. **(H-2)** Watch the streamed answer as it types.
   - *Expected:* the visible text is **clean prose** — **no** literal `<REPLY>`, `</REPLY>`,
     `<META>` tags or trailing JSON (summary/follow-ups) in the bubble. The final saved
     message matches what streamed.
3. Repeat steps 1–2 with the **Gemini** model.
   - *Expected:* same behavior — page citations, clean stream, no tag leakage.
4. **(M-1, harder)** Ask a broad question that forces several tool calls across multiple
   materials (e.g. “Summarize how chapters 2 and 4 relate, with page references”).
   - *Expected:* even when retrieval takes many steps, you get a **synthesized answer from
     the fetched pages**, *not* the fallback “I could not find relevant content in the course
     materials.” (Before M-1, Claude/Gemini returned that error after exhausting iterations.)
5. Compare an OpenAI answer to the same question as a baseline.
   - *Expected:* comparable citation quality across all three providers.

> Note: these paths hit live provider APIs and have no automated coverage — verify here
> before enabling for Claude/Gemini in production.

---

## 7. Web Search User Toggle  (feature #3) VERIFIED

**Validates:** per-chat web-search toggle threaded into the PageIndex loop, gated by both the
server env flag and the per-chat flag.

**Preconditions:** `AGENTIC_WEB_SEARCH_ENABLED=true` **and** `TAVILY_API_KEY` set; PageIndex enabled.

**Steps & Expected:**
1. In the compose bar, locate the **globe / web-search toggle**. Turn it **on**.
   - *Expected:* it shows an active state.
2. Ask a question requiring **current/outside** info (e.g. “What's the latest stable version
   of <tool>?”).
   - *Expected:* a web-search step appears in the tool trace; the answer references live web
     results and **web URLs appear in the source panel**.
3. Reload the page.
   - *Expected:* the toggle state **persists** (localStorage `chat_web_search_enabled`).
4. Turn the toggle **off**, ask another outside-info question.
   - *Expected:* **no** web search is performed (course-materials-only answer), even though
     the server env flag is on.
5. **Server-gate check:** set `AGENTIC_WEB_SEARCH_ENABLED` unset/false, restart, toggle on,
   ask again.
   - *Expected:* no web search runs (env gate overrides the per-chat flag).

---

## 8. Generate-From-Chat (rich)  (feature #4 / GFC) VERIFIED

**Validates:** the `propose_generation` tool → proposal card → **Build** (queues a generation)
and **Refine** (opens prefilled modal). **Regression for H-1** (Build now works for
**flashcards and reports**, not just quiz).

**Preconditions:** PageIndex enabled; a chat with a substantive discussion and 1–2 materials selected.

**Steps & Expected — run the Build path once per type (quiz, flashcards, report):**
1. In a chat, explicitly ask to create an artifact, e.g.:
   - quiz: “Make me a 5-question quiz about what we just discussed.”
   - flashcards: “Turn this conversation into 10 flashcards.”
   - report: “Generate a study-guide report from this discussion.”
   - *Expected:* a **proposal card** renders inline with a title, the param summary, and a
     “N materials + this conversation” line, plus **Build** and **Refine** buttons.
2. Click **Build**.
   - *Expected (H-1):* button shows “Queuing…” then **“Queued ✓”** for **all three types**
     (previously flashcards/reports silently reverted to Build and queued nothing). For
     flashcards/reports the client runs estimate→generate under the hood.
3. Go to the **Generate** tab → the relevant sub-tab (Quiz / Flashcards / Reports).
   - *Expected:* a new generation is present and progresses to **ready**; its content reflects
     the conversation (conversation summary used as a primary source).
4. Back in chat, on a fresh proposal click **Refine** instead.
   - *Expected:* navigates to the Generate tab with the matching sub-tab and a **prefilled
     modal** — topic, the chat's materials, and the conversation context pre-populated.
5. **No-materials case:** start a chat with **no materials selected**, discuss a topic, ask
   to “make a quiz about this.”
   - *Expected:* proposal builds using only the conversation summary; the generation succeeds
     with no selected materials.

---

## 9. Bug-fix regression matrix (quick reference)

| Fix | Where to confirm | Pass signal |
|---|---|---|
| **C-1** Flashcard crash | Test 5, step 1 | Viewer renders, no error boundary |
| **C-2** Stats 500 | Test 2 | `action=stats` → 200, widget shows counts |
| **C-3** Prompts 500 | Test 3 | list/create → 200/201, no `KeyError` |
| **H-1** Build flashcards/reports | Test 8, step 2 | “Queued ✓” for all 3 types |
| **H-2** Tag leakage | Test 6, step 2 | No `<REPLY>`/`<META>` in stream |
| **M-1** Forced synthesis | Test 6, step 4 | Real answer, not the “could not find” fallback |
| **L-1** Test collection | `pytest tests/` | Suite runs (80 passed), no collection abort |
| **L-2** Migrations | Setup step 1 | Migration applies; features don't 500 on missing columns |
| **L-3** JS tests | `npm test` | 4 passed |

---

## 10. Notes & known limitations

- The 3 pre-existing backend test failures (`test_flashcards_phase2_validation`,
  `test_reports_validation`) also fail on `main` and are **unrelated** to this branch.
- PageIndex Claude/Gemini and web search hit live third-party APIs; budget/keys required and
  results are non-deterministic — focus on *behavioral* expectations (citations, clean
  stream, no error fallback), not exact answer text.
