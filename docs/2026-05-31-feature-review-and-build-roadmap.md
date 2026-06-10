# Feature Review & Build Roadmap — 2026-05-31

> Automated review by the feature-review agent. Inspect of routes, components, API handlers, Lambda functions, data models, integration providers, and tests.

---

## ⚠️ Reconciliation Update — 2026-06-01

This roadmap was reconciled against the actual codebase during a planning session. **The original review contained material inaccuracies** (it was written without deep code inspection). Corrections:

- **Already fully built (no work needed):**
  - **Chat image edit** — `_edit_message` does the full add/remove-key diff, re-embeds added images, and passes final keys to `synthesize()`; frontend has `kind: 'existing'` edit staging. (Original said "not implemented.")
  - **Quiz attempt history** — tables + grader + `list_attempts`/`get_attempt` endpoints AND the `QuizViewer` attempts UI all exist. (Original said "no UI.")
  - **Chat search surface** — a `SearchChat` command-palette modal with FTS across the course already exists. (Only a message-level snippet/jump-to improvement was scoped.)
- **Mis-described:**
  - **PageIndex** does **not** "fall back to legacy RAG" for Claude/Gemini — when enabled, `synthesize` routes *every* provider through `run_agent_pageindex`, which is hardcoded to OpenAI and the user's OpenAI key. The selected Claude/Gemini model is bypassed. The real work is making the loop honor the selected provider.
  - **Flashcard rating UI does not exist** (original said it did). The Play button is genuinely unwired.
  - **Web search** is not in the PageIndex loop at all — only in the legacy OpenAI loop. The toggle work must add it to the PageIndex loop.
- **De-duplicated:** the two PageIndex rows (P1 + P2) were the same item; collapsed into one.
- **Dropped by owner:** Chat export to Drive/Notion; Flashcard spaced repetition.
- **Redefined by owner:** "Cross-course search/chat" → **single-course** chat search improvement (snippet + jump-to-message).
- **New priority order:** PageIndex Claude/Gemini is **#1** (web search toggle + generate-from-chat build on the all-providers loop).

Specs and implementation plans for the actionable items live in `docs/superpowers/specs/` and `docs/superpowers/plans/`.

---

## Concise Summary

- **Current product shape**: A course-scoped AI study assistant. Users create courses, upload materials (PDF, DOCX, images, spreadsheets), connect Google Drive and Notion as both source and export targets, chat with their materials across three AI providers, and generate quizzes, flashcards, and reports. The product is post-MVP with working end-to-end flows for all major verticals.

- **Strongest existing features**: Multi-provider streaming chat (OpenAI / Claude / Gemini) with source citations; full material ingestion pipeline with type-aware chunking and vector embedding; async generation (quiz, flashcard, report) with PDF and Drive/Notion export; bidirectional Drive and Notion integration (source + export).

- **Most important partial builds** _(corrected 2026-06-01)_: (1) Flashcard interactivity — Play button is wired to nothing; **no rating UI exists yet**. (2) PageIndex agentic loop — when enabled it routes **all** providers through OpenAI (selected Claude/Gemini model bypassed), not a "legacy fallback". (3) Web search tool — fully implemented but only in the legacy OpenAI loop, behind `AGENTIC_WEB_SEARCH_ENABLED=false`, with no user toggle and not present in the PageIndex loop. _(Chat image edit was listed here but is in fact fully implemented.)_

- **Fastest easy wins**: Flashcard Play mode + rating (build both), web search user toggle, single-course chat-search snippet/jump-to-message, per-course model default. _(Quiz attempt history and chat image edit are already built; chat export to Drive/Notion dropped by owner.)_

- **Highest-value new suggestions**: Saved prompt library; generate-from-chat shortcut (rich/conversational — spec'd and planned); dashboard analytics (materials processed, generation counts, chat activity). _(Spaced-repetition scheduling dropped by owner; cross-course search redefined as single-course.)_

- **Main technical/product risks**: PageIndex is the future retrieval path but is OpenAI-gated — Claude/Gemini users' selected model is silently bypassed in favor of OpenAI, an invisible two-tier (and a hidden requirement that every user hold an OpenAI key). Web search is disabled by default, absent from the production retrieval loop, and has no UI surface. The Flashcard Play button is dead UI.

---

## Prioritized Opportunities

_Reconciled 2026-06-01. "Order" reflects the agreed build sequence. Status: **BUILD** = plan written; **DONE** = already implemented (verify note written); **DROPPED** = removed by owner._

| Order | Status | Priority | Feature / Component | Corrected Current State | Effort | Plan / Note |
|---|---|---|---|---|---|---|
| 1 | BUILD | P1 | PageIndex for Claude & Gemini | Enabled loop routes ALL providers through OpenAI; selected Claude/Gemini model bypassed | L | `plans/2026-05-31-pageindex-claude-gemini.md` |
| 2 | BUILD | P0 | Flashcard Play mode + rating | Play button unwired; rating UI does NOT exist | S | `plans/2026-05-31-flashcard-play-mode-and-rating.md` |
| 3 | BUILD | P1 | Web search user toggle | Web search only in legacy loop, not PageIndex; no toggle | S–M | `plans/2026-05-31-web-search-user-toggle.md` |
| 4 | BUILD | P3 | Generate-from-chat (rich) | Not present; rich/conversational design approved | M | `plans/2026-05-31-generate-from-chat.md` |
| 5 | BUILD | P3→S | Single-course chat search (snippet + jump-to) | Search modal exists; content matches lack snippet/deep-link | S | `plans/2026-05-31-chat-search-message-level-results.md` |
| 6 | BUILD | P2 | Per-course model default | Chat default is global localStorage only | S | `plans/2026-06-01-per-course-model-default.md` |
| 7 | BUILD | P2 | Dashboard analytics widget | No widgets; data all in DB | M | `plans/2026-06-01-dashboard-analytics-widget.md` |
| 8 | BUILD | P3 | Saved prompt library | Not present | M | `plans/2026-06-01-saved-prompt-library.md` |
| — | DONE | P0 | Chat image edit preserves images | Fully implemented (backend diff + frontend staging) | — | `plans/2026-05-31-chat-image-edit-VERIFY-already-implemented.md` |
| — | DONE | P1 | Quiz attempt history & grading view | Fully implemented (tables + grader + QuizViewer UI) | — | `plans/2026-05-31-quiz-attempt-history-VERIFY-already-implemented.md` |
| — | DROPPED | P1 | Chat export to Drive / Notion | Not implemented | — | Dropped by owner |
| — | DROPPED | P2 | Flashcard spaced repetition scheduling | Not implemented | — | Dropped by owner |
| — | MERGED | P2 | PageIndex for Claude/Gemini agentic loop | Duplicate of Order 1 | — | Merged into Order 1 |

---

## Superpowers Spec + Implementation Plan: Flashcard Play Mode + Rating

Category: Partially Built  
Priority: P0  
Estimated Effort: S

### Current State
`src/FlashcardViewer.jsx` renders a Play button and thumb-up/thumb-down rating buttons. Neither has an `onClick` handler — Play only stops propagation, thumbs only stop propagation (confirmed by session eval obs 5070). The flashcard data model (`front`/`back`) is stored in the `flashcard_generations` table and exposed through the API.

### Spec Scope
- **In scope**: Play/flip study mode (card-by-card flip through); thumb rating recorded per card; visual progress bar during play.
- **Out of scope**: SM-2 spaced-repetition scheduling (P2 separate item); shared deck state.

### Target Outcome
- Clicking Play enters a full-screen card-flip study session.
- Users swipe/click to flip each card front→back.
- Thumb up/down records a rating for each card and advances to the next.
- Progress bar shows cards remaining.

### Architecture / Data Flow
- Frontend: `FlashcardViewer.jsx` gains a `playMode` state; separate `FlashcardPlaySession` component renders one card at a time.
- API: `POST /api/flashcards action=rate_card` writes `{generation_id, card_index, rating}` to a new `flashcard_card_ratings` table.
- DB: one migration — `CREATE TABLE flashcard_card_ratings (id serial primary key, generation_id int references flashcard_generations, card_index int, user_id int references users, rating smallint, rated_at timestamptz default now())`.

### Acceptance Criteria
- Play button opens study session; cards flip on click.
- Thumb up/down calls rating API; response 200.
- Progress bar advances after each card rating.
- Exiting Play returns to the normal viewer.

### Implementation Plan
1. Add `flashcard_card_ratings` table — provide migration SQL in chat for user to run.
2. Add `action=rate_card` branch in `api/flashcards.py`.
3. Build `FlashcardPlaySession` component in `src/FlashcardViewer.jsx` with flip animation, progress bar.
4. Wire Play button to enter play mode; wire thumb buttons to call rating API.

### Verification Plan
- Click Play: session opens, cards flip, progress advances.
- Rate a card: `flashcard_card_ratings` row inserted.
- Exit session: viewer state restored.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-flashcard-play-rating-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-flashcard-play-rating-implementation-plan.md`

### Files Likely Touched
- `src/FlashcardViewer.jsx`
- `src/FlashcardViewerRoute.jsx`
- `api/flashcards.py`

### Risks / Dependencies
- Migration must run before API change ships.
- Card index must be stable — current API returns ordered array; assume positional index is stable per generation.

---

## Superpowers Spec + Implementation Plan: Chat Image Edit

Category: Partially Built  
Priority: P0  
Estimated Effort: M

### Current State
Chat messages support image attachments on send (`upload_image` action, `image_s3_keys` column on `chat_messages`, `chat_image_embeddings` table). However, editing a message that had images drops them silently: the edit textarea shows only text, and the `stream_edit` payload sends no images. An openspec change (`openspec/changes/edit-message-image-attachments/`) fully specifies the fix; schema already supports it.

### Spec Scope
- **In scope**: Pre-populate image strip in edit mode from `image_s3_keys`; mutable strip (add/remove during edit); `stream_edit` backend accepts updated `image_attachments`; embed new images, delete embeddings for removed images.
- **Out of scope**: Image cropping; rich image annotations.

### Target Outcome
- Opening edit mode on a message with images shows existing thumbnails in the staging strip.
- User can remove existing images (×) or add new ones (+).
- Submitting edit sends final image set to the LLM identically to a fresh send.

### Architecture / Data Flow
- `api/chat.py`: `_edit_message` must accept `image_attachments`; message serialization must include `image_s3_keys` in GET response.
- `api/llm.py`: `synthesize()` already accepts `image_s3_keys`; call site in `_edit_message` just needs to pass the final list.
- `src/ChatTab.jsx`: edit state reads `msg.image_s3_keys`; staging strip component pre-populated.

### Acceptance Criteria
- Editing a message with 2 images shows 2 thumbnails in edit mode.
- Removing one thumbnail and submitting: LLM receives 1 image; removed embedding deleted.
- Adding a new image in edit mode: new embedding written; LLM receives it.

### Implementation Plan
1. Extend message GET serializer in `api/chat.py` to include `image_s3_keys`.
2. Update `src/ChatTab.jsx` edit state to pre-populate staging strip from `msg.image_s3_keys`.
3. Update `handleEditMessage` in `src/ChatTab.jsx` to upload new images and pass final `image_s3_keys` in `stream_edit` payload.
4. Update `_edit_message` in `api/chat.py` to accept `image_attachments`, embed new, delete removed embeddings, pass to `synthesize()`.

### Verification Plan
- Send message with 2 images → edit → verify strip pre-populated.
- Remove 1 image → submit → verify `chat_image_embeddings` row deleted.
- Add new image in edit → submit → verify new embedding row written.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-chat-image-edit-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-chat-image-edit-implementation-plan.md`

### Files Likely Touched
- `src/ChatTab.jsx`
- `api/chat.py`

### Risks / Dependencies
- Openspec design already complete; implementation straightforward.
- S3 presigned download URL must be generated for existing images in the edit response.

---

## Superpowers Spec + Implementation Plan: Web Search User Toggle

Category: Partially Built  
Priority: P1  
Estimated Effort: S

### Current State
`api/tools.py::execute_web_search` is fully implemented using Tavily. It is gated by `AGENTIC_WEB_SEARCH_ENABLED=false` — a server-side environment variable. There is no per-user or per-chat toggle. The tool appears in the OpenAI agentic loop but is silently disabled. Claude and Gemini paths don't invoke it at all.

### Spec Scope
- **In scope**: Per-chat web-search toggle button in the chat compose bar; stored in localStorage; passed in the `stream_send` payload; honored by the OpenAI agentic loop.
- **Out of scope**: Per-user server-side preference; enabling web search for Claude/Gemini agentic loops (P2).

### Target Outcome
- A globe icon button in the compose bar toggles web search on/off.
- When on, the AI supplements course materials with live web results.
- Toggle state persists across sessions (localStorage).
- Clear visual indicator (active state) when web search is enabled.

### Architecture / Data Flow
- `src/ChatTab.jsx`: Add toggle button; pass `web_search_enabled: bool` in `stream_send` payload.
- `api/chat.py`: Read `web_search_enabled` from request body; pass to `synthesize()`.
- `api/llm.py` / `api/tools.py`: Honor the flag — allow web search if flag is true AND `AGENTIC_WEB_SEARCH_ENABLED` server env is true.

### Acceptance Criteria
- Toggle button visible in compose bar; state persists via localStorage.
- `web_search_enabled=true` in payload causes Tavily to be called (if env var set).
- `web_search_enabled=false` skips Tavily regardless of env var.
- Web search result URLs shown in source panel.

### Implementation Plan
1. Add globe toggle button to compose bar in `src/ChatTab.jsx`; store state in localStorage.
2. Pass `web_search_enabled` in `stream_send` and `stream_edit` payloads.
3. Update `api/chat.py` send/edit handlers to extract and thread `web_search_enabled` through to `synthesize()`.
4. Update `synthesize()` / agentic loop in `api/llm.py` to check both env var AND request flag before enabling web search tool.

### Verification Plan
- Toggle on → submit question → Tavily called → web result sources appear.
- Toggle off → submit → Tavily not called even if env var set.
- Refresh page → toggle state preserved.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-web-search-toggle-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-web-search-toggle-implementation-plan.md`

### Files Likely Touched
- `src/ChatTab.jsx`
- `api/chat.py`
- `api/llm.py`
- `api/tools.py`

### Risks / Dependencies
- Requires `AGENTIC_WEB_SEARCH_ENABLED=true` and `TAVILY_API_KEY` in production env.
- Web search only works in the OpenAI agentic loop — should show toggle as disabled for Claude/Gemini models until P2 work.

---

## Superpowers Spec + Implementation Plan: Quiz Attempt History View

Category: Easy Improvement  
Priority: P1  
Estimated Effort: M

### Current State
`api/services/quiz_attempt_grader.py` exists and grades quiz answers. The quiz API (`api/quiz.py`) has an `export_pdf` action. `src/QuizViewer.jsx` renders questions and answers interactively. However, there is no attempt recording, attempt history table, or attempt history view in the UI — users complete a quiz and lose their score.

### Spec Scope
- **In scope**: Record quiz attempts with question-level scores; view attempt history per quiz generation; see score and per-question breakdown.
- **Out of scope**: Leaderboards; shared attempts; cross-quiz analytics.

### Target Outcome
- After completing a quiz, score is recorded and visible in the generation list.
- Users can review past attempts with score, timestamp, and per-question results.
- Attempt history accessible from the Quiz viewer.

### Architecture / Data Flow
- DB: `quiz_attempts` table: `(id, generation_id, user_id, score_pct, answers_json, attempted_at)`.
- API: `POST /api/quiz action=submit_attempt` → grade via grader → write attempt → return score.
- API: `GET /api/quiz?action=list_attempts&generation_id=X` → return attempt history.
- Frontend: `src/QuizViewer.jsx` — Submit button calls API; show score summary; link to attempt history.
- Frontend: `src/Quiz.jsx` — Generation list shows best/last score badge.

### Acceptance Criteria
- Submitting answers records an attempt; score visible immediately.
- Returning to a quiz shows attempt history list (date, score).
- Per-question breakdown visible in attempt detail.

### Implementation Plan
1. Write migration SQL for `quiz_attempts` table (provide in chat).
2. Add `action=submit_attempt` and `action=list_attempts` branches to `api/quiz.py`; use `quiz_attempt_grader.py` for scoring.
3. Add Submit flow to `src/QuizViewer.jsx`; display score summary after submission.
4. Add attempt history panel to `src/QuizViewer.jsx`.
5. Add score badge to generation cards in `src/Quiz.jsx`.

### Verification Plan
- Submit quiz → attempt row created → score displayed.
- Navigate away and back → attempt history shows previous attempt.
- Short-answer grading returns partial credit.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-quiz-attempt-history-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-quiz-attempt-history-implementation-plan.md`

### Files Likely Touched
- `api/quiz.py`
- `api/services/quiz_attempt_grader.py`
- `src/QuizViewer.jsx`
- `src/Quiz.jsx`

### Risks / Dependencies
- LLM-graded short/long answer requires OpenAI call; add timeout guard.
- Migration must precede API changes.

---

## Superpowers Spec + Implementation Plan: Chat Export to Drive / Notion

Category: Easy Improvement  
Priority: P1  
Estimated Effort: M

### Current State
Google Drive and Notion export are fully implemented for Quizzes, Flashcards, and Reports (`api/services/providers/gdrive.py`, `api/services/export_blocks.py`). The chat API supports message listing and full-text search. There is no mechanism to export a chat conversation to Drive or Notion.

### Spec Scope
- **In scope**: Export current chat thread to Notion (as a page) or Google Drive (as a Doc); include message history with user/AI roles; citations/sources footnoted.
- **Out of scope**: Real-time chat sync; export partial message selections.

### Target Outcome
- Three-dot menu on a chat has "Export to Notion" and "Export to Google Drive" options.
- Exported document contains the full conversation with user/AI labels and source citations.
- Export uses the existing sticky target selection for Drive/Notion.

### Architecture / Data Flow
- `api/services/export_blocks.py`: Add `chat_to_notion_blocks(messages)` function.
- `api/services/providers/gdrive.py`: Add `chat_to_doc_requests(messages)` function.
- `api/chat.py`: Add `action=export_to_notion` and `action=export_to_drive` handlers; fetch messages, call respective export function, call provider API.
- `src/ChatTab.jsx`: Add export options to the chat header/context menu.

### Acceptance Criteria
- Exporting a 10-message chat to Notion creates a correctly structured Notion page.
- Exporting to Drive creates a Google Doc with styled headings for user/AI turns.
- Source citations from AI messages appear as footnotes or inline links.

### Implementation Plan
1. Add `chat_to_notion_blocks()` to `api/services/export_blocks.py`.
2. Add `chat_to_doc_requests()` to `api/services/providers/gdrive.py`.
3. Add `action=export_to_notion` and `action=export_to_drive` to `api/chat.py`.
4. Add export dropdown to chat header/context menu in `src/ChatTab.jsx`.

### Verification Plan
- Export chat to Notion → Notion page created with correct content.
- Export chat to Drive → Google Doc created with styled conversation.
- Long chat (50+ messages) exports without timeout.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-chat-export-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-chat-export-implementation-plan.md`

### Files Likely Touched
- `api/chat.py`
- `api/services/export_blocks.py`
- `api/services/providers/gdrive.py`
- `src/ChatTab.jsx`

### Risks / Dependencies
- Requires Drive/Notion to be connected; show disabled state with "Connect first" tooltip if not.
- Notion block limit (100 per request) may require pagination for long chats.

---

## Superpowers Spec + Implementation Plan: PageIndex for Claude & Gemini

Category: Partially Built  
Priority: P1 → P2 (schedule after P1 items)  
Estimated Effort: L

### Current State
`api/llm.py` has a `_pageindex_stream_call()` function that implements the agentic tool-use loop using the OpenAI REST API with function-calling (`tools`, `tool_calls`). Claude and Gemini chat paths in `synthesize()` use the non-agentic legacy path (single-call with embedded chunks). `_is_pageindex_active()` in `api/chat.py` controls the gate.

### Spec Scope
- **In scope**: PageIndex agentic loop for Claude (Anthropic tool_use blocks) and Gemini (functionDeclarations / FunctionResponse).
- **Out of scope**: Multi-modal page retrieval for Claude (image content blocks) — treat as a follow-on.

### Target Outcome
- All three providers execute the full PageIndex agentic loop with the same tools (`get_page_content`, `get_material_structure`, `get_related_materials`).
- Retrieved page content is identical regardless of provider.
- Live retrieval status SSE events stream correctly for all providers.

### Architecture / Data Flow
- `api/llm.py`: Add `_pageindex_claude_loop()` and `_pageindex_gemini_loop()` mirroring `_pageindex_stream_call()` but using Anthropic and Gemini REST formats respectively.
- Tool dispatch (page fetch, structure fetch) is provider-agnostic; can be shared.
- `synthesize()` routing: detect `use_pageindex=True` and dispatch to the right loop based on provider.

### Acceptance Criteria
- Asking a factual question over Claude Sonnet 4.6 uses `get_page_content` tool and cites page-level sources.
- Asking over Gemini 2.5 Flash similarly executes the agentic loop.
- Live retrieval status ("Retrieving pages X from Y") appears during tool execution for all providers.

### Implementation Plan
1. Extract provider-agnostic tool dispatch functions from `_pageindex_stream_call`.
2. Implement `_pageindex_claude_loop()` using Anthropic messages API with `tools` / `tool_use` / `tool_result` block format.
3. Implement `_pageindex_gemini_loop()` using Gemini REST with `tools.functionDeclarations` + `FunctionResponse`.
4. Update `synthesize()` to route to the appropriate loop.
5. Ensure SSE `retrieval_status` events are emitted from all three loops.

### Verification Plan
- Run `tests/test_pageindex_agent.py` against Claude and Gemini paths.
- Verify source panel shows page-level citations for both providers.
- Compare answer quality against OpenAI baseline using eval harness.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-pageindex-claude-gemini-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-pageindex-claude-gemini-implementation-plan.md`

### Files Likely Touched
- `api/llm.py`
- `api/chat.py`
- `tests/test_pageindex_agent.py`

### Risks / Dependencies
- Anthropic tool_use format differs meaningfully from OpenAI function calling — requires careful message history construction.
- Gemini streaming with function responses has different SSE shapes.
- OpenAI is the only battle-tested path; run eval before enabling for Claude/Gemini in production.

---

## Superpowers Spec + Implementation Plan: Saved Prompt Library

Category: New Suggestion  
Priority: P3  
Estimated Effort: M

### Current State
No saved prompt functionality exists. Users retype common questions (e.g., "summarize this lecture", "give me practice problems for chapter 3") every session.

### Spec Scope
- **In scope**: Per-user saved prompts; insert prompt into compose bar; manage (rename, delete) saved prompts; optional per-course scope.
- **Out of scope**: Shared prompt marketplace; prompt versioning.

### Target Outcome
- Compose bar has a "Saved prompts" button that opens a picker.
- Users can save the current compose text as a named prompt.
- Selecting a saved prompt inserts it into the compose bar (editable before sending).

### Architecture / Data Flow
- DB: `saved_prompts (id, user_id, title, content, course_id nullable, created_at)`.
- API: `GET/POST/DELETE /api/user?resource=saved_prompts`.
- Frontend: `src/ChatTab.jsx` — prompt picker panel; save current text action.

### Acceptance Criteria
- Save a prompt from compose bar → appears in picker.
- Select prompt → inserted into compose bar.
- Delete prompt → removed from picker.

### Implementation Plan
1. Migration: `saved_prompts` table (provide SQL in chat).
2. Add CRUD endpoints to `api/user.py`.
3. Add prompt picker UI to compose bar in `src/ChatTab.jsx`.
4. Add save-current-text action.

### Verification Plan
- CRUD round-trip for saved prompts.
- Prompt inserted correctly into compose bar on selection.
- Course-scoped prompts only appear in the correct course.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-saved-prompts-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-saved-prompts-implementation-plan.md`

### Files Likely Touched
- `api/user.py`
- `src/ChatTab.jsx`

### Risks / Dependencies
- Per-course vs. global scope needs UX decision.

---

## Superpowers Spec + Implementation Plan: Generate-From-Chat Shortcut

Category: New Suggestion  
Priority: P3  
Estimated Effort: M

### Current State
Chat and Generate tabs are adjacent in the course UI. There is no mechanism to bridge them — users cannot ask the AI to generate a quiz from the current conversation context or from a chat's source materials.

### Spec Scope
- **In scope**: "Generate from this conversation" button that opens the Generate tab pre-configured with the materials referenced in the current chat.
- **Out of scope**: Embedding full chat history into generation context; AI-driven auto-generation from chat summary.

### Target Outcome
- A "Generate →" button appears in the chat actions bar.
- Clicking it navigates to the Generate tab with the current chat's `context_material_ids` pre-selected.
- User proceeds through normal quiz/flashcard/report generation flow with materials pre-filled.

### Architecture / Data Flow
- `src/ChatTab.jsx`: Extract `context_material_ids` from current chat; pass them to `handleTabChange('generate')` via state.
- `src/Generations.jsx` / `src/Quiz.jsx`, `src/Flashcards.jsx`, `src/Reports.jsx`: Accept pre-selected material IDs prop and pre-check them in the material picker.
- `src/CoursePage.jsx`: Thread state through `handleTabChange`.

### Acceptance Criteria
- Clicking "Generate →" in a chat with 3 selected materials opens Generate tab with those 3 materials pre-checked.
- Generation proceeds normally from the pre-populated state.

### Implementation Plan
1. Add "Generate →" button to `src/ChatTab.jsx`; extract `context_material_ids` from active chat.
2. Update `handleTabChange` in `src/CoursePage.jsx` to accept optional state payload.
3. Update `src/Generations.jsx` to accept and pass `preSelectedMaterialIds` prop.
4. Update material pickers in `src/Quiz.jsx`, `src/Flashcards.jsx`, `src/Reports.jsx` to pre-check supplied IDs.

### Verification Plan
- Chat with 2 materials selected → click Generate → 2 materials pre-checked in quiz form.
- Generating with pre-checked materials produces a quiz scoped to those materials.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/2026-05-31-generate-from-chat-design.md`
- Plan: `docs/superpowers/plans/2026-05-31-generate-from-chat-implementation-plan.md`

### Files Likely Touched
- `src/ChatTab.jsx`
- `src/CoursePage.jsx`
- `src/Generations.jsx`
- `src/Quiz.jsx`
- `src/Flashcards.jsx`
- `src/Reports.jsx`

### Risks / Dependencies
- `context_material_ids` is stored per-chat in the DB and returned in message list API response; need to verify it is available in the chat list response or add a field.

---

## Recommended Execution Order _(reconciled 2026-06-01)_

1. **PageIndex Claude/Gemini** — make the agentic loop honor the selected provider; unblocks web search + generate-from-chat. Do the cross-provider eval before enabling in prod.
2. **Flashcard Play + Rating** — narrow, high-visibility; fixes dead UI. Build the rating UI (it doesn't exist).
3. **Web Search Toggle** — adds `web_search` to the PageIndex loop + a compose-bar toggle. Best after #1.
4. **Generate-from-Chat (rich)** — `propose_generation` agentic tool → Build/Refine card; rides on #1.
5. **Single-course chat search (snippet + jump-to)** — small enhancement to the existing search modal.
6. **Per-course model default** — small course-record + UI change.
7. **Dashboard analytics widget** — stats endpoint + widget.
8. **Saved prompt library** — independent; any quiet slot.

_Excluded:_ Chat Image Edit and Quiz Attempt History (already built — verify only); Chat Export and Flashcard Spaced Repetition (dropped by owner).

---

## Open Questions That Block Accurate Planning

1. **Web search production readiness**: Is `AGENTIC_WEB_SEARCH_ENABLED` intentionally off in production? Is there a Tavily budget? This blocks P1 web search toggle.
2. **PageIndex production flag**: Is `_is_pageindex_active()` returning true in production or is it behind a flag? The current code checks an env var (`PAGEINDEX_ENABLED` or similar) — need to confirm deployment state.
3. **Quiz attempt grader LLM budget**: Short/long answer grading requires an LLM call per attempt. What is the acceptable cost envelope for graded attempts?
4. **Sharing role permissions**: The sharing model has `role` field (seen in `_serialize_member`) but the code only checks `primary_creator`. Are viewer/editor roles intended? Any access control gaps to close?
5. **Chat message summarization**: Migration `006_chat_messages_summary.sql` exists — is this being used for long-context compression? If so, it is an invisible but critical correctness invariant to document.
6. **Multipart upload completion**: `complete_multipart_upload` is in `s3_utils.py` but unclear if the frontend calls it correctly for files >5 MB. Any partial upload orphan cleanup?
