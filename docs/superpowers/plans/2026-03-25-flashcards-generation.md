# Flashcards Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement end-to-end async flashcard generation with queue-backed processing, viewer-template-compatible APIs, and regeneration/session flows matching hardened quiz Session 2 behavior.

**Architecture:** A single `api/flashcards.py` Vercel Python serverless handler acts as an orchestration runtime only (estimate, queue start, history/status/get, save, resolve, export, delete). Actual LLM generation runs in `lambda/flashcards_generate/handler.py` from SQS messages after commit-before-enqueue transitions. Frontend (`Flashcards.jsx`, `FlashcardViewer.jsx`, `FlashcardViewerRoute.jsx`, `GenerationConfirmModal.jsx`, `MaterialsPage.jsx`) is lifecycle-driven (`draft -> queued -> generating -> ready|failed`) with polling/resume and deep-link reopening.

**Tech Stack:** Python 3 / psycopg (PostgreSQL), requests (provider REST APIs), AWS SQS + Lambda, React + Tailwind CSS, Vercel Python Serverless Functions, pytest

---

## File Map

| File | Change | Responsibility |
| --- | --- | --- |
| `api/db.py` | Modify | Add flashcard generation/card tables, lifecycle constraints, indexes |
| `api/flashcards.py` | Create | All flashcards API actions and queue orchestration |
| `api/services/flashcards_token_estimator.py` | Create | Deterministic token-range estimation for estimate modal/history |
| `api/services/flashcards_pdf_builder.py` | Create | PDF export rendering for persisted flashcards |
| `lambda/flashcards_generate/handler.py` | Create | Queue-triggered generation runtime and persistence |
| `lambda/flashcards_generate/db.py` | Create | Worker DB access helpers |
| `lambda/flashcards_generate/Dockerfile` | Create | Worker image build |
| `lambda/flashcards_generate/requirements.txt` | Create | Worker runtime deps |
| `lambda/flashcards_generate/build.sh` | Create | Build/push/package helper |
| `lambda/flashcards_generate/iam/api-send-message-policy.json` | Create | API runtime permission template to enqueue messages |
| `lambda/flashcards_generate/iam/worker-consume-policy.json` | Create | Worker permission template to consume queue + write logs |
| `scripts/infra/setup_flashcards_generation_infra.sh` | Create | Idempotent queue/DLQ/event-source setup script |
| `docs/superpowers/specs/2026-03-25-flashcards-generation-infra-runbook.md` | Create | Infra runbook and rollout guidance |
| `src/Flashcards.jsx` | Modify | Estimate-confirm-generate flow, history polling, draft handling |
| `src/FlashcardViewer.jsx` | Modify | Save/export/regenerate/resolve wiring |
| `src/FlashcardViewerRoute.jsx` | Create | Generation-id route loader + regeneration/status loop |
| `src/components/GenerationConfirmModal.jsx` | Modify | Flashcards mode, provider/model picker, loading-safe actions |
| `src/MaterialsPage.jsx` | Modify | Reopen flashcards generations from materials deep links |
| `src/QuizViewerRoute.jsx` | Modify | Session 2 parity cleanup for provider source path |
| `src/App.jsx` | Modify | Route registration for flashcard viewer route |
| `tests/test_flashcards_phase2_validation.py` | Create | Estimator + normalization + PDF builder validations |

---

## Session 2 Changes to Replicate (Quiz -> Flashcards)

- [ ] **Lifecycle parity:** Use explicit async statuses `draft|queued|generating|ready|failed` (not synchronous generation status assumptions).
- [ ] **Commit-before-enqueue:** Persist transition to `queued` and commit transaction before sending SQS message.
- [ ] **Row lock transition guard:** Use `FOR UPDATE` and allow only `draft|failed -> queued` on queue-start action.
- [ ] **Provider/model snapshot parity:** Save provider/model overrides at queue-start so worker executes exact selected model.
- [ ] **JSONB serialization parity:** Serialize dict/list payloads with `json.dumps` before DB writes.
- [ ] **Region fallback parity:** Resolve AWS region via explicit chain (`AWS_REGION`, `AWS_DEFAULT_REGION`, fallback).
- [ ] **Delete backpropagation parity:** On generation delete, remove linked artifact material first to avoid orphaned generated material.
- [ ] **Polling resilience parity:** Frontend must resume polling from backend statuses after refresh/navigation.
- [ ] **Modal concurrency parity:** Disable confirm/cancel while queue-start request is in-flight.

---

## Task 1: Database Schema and Persistence Contract

**Files:**
- Modify: `api/db.py`

- [ ] **Step 1: Add `flashcard_generations` table with async lifecycle + snapshots**

Include: ownership (`course_id`, `generated_by`), generation params (`topic`, `card_count`, `depth`), model snapshot (`provider`, `model_id`, `generation_settings`), source snapshot (`selected_material_ids`), token estimate snapshot columns, status/error, lineage (`parent_generation_id`), and artifact linkage (`artifact_material_id`).

- [ ] **Step 2: Add `flashcard_cards` table for canonical card persistence**

Persist per-card data with deterministic order: `generation_id`, `card_index`, `front_text`, `back_text`, optional `hint_text` and metadata.

- [ ] **Step 3: Add required indexes for history/polling/viewer performance**

Indexes include: `(course_id, generated_by, created_at DESC)`, `(status, created_at DESC)`, and `(generation_id, card_index)`.

- [ ] **Step 4: Ensure status constraint + default align to async flow**

Constraint must include all five statuses and default to `draft` for estimate-created rows.

- [ ] **Step 5: Verify schema compiles/loads**

Run: `python3 -m py_compile api/db.py`

---

## Task 2: API Runtime (`api/flashcards.py`) as Queue Orchestrator

**Files:**
- Create: `api/flashcards.py`
- Create: `api/services/flashcards_token_estimator.py`
- Create: `api/services/flashcards_pdf_builder.py`

- [ ] **Step 1: Implement POST `action=estimate`**

Validate access + inputs, calculate token ranges, persist draft generation row, and return modal payload (`generation_id`, token estimates, settings snapshot, provider/model).

- [ ] **Step 2: Implement POST `action=generate` (queue-start only)**

Lock generation row with `FOR UPDATE`, validate ownership and status transition guard, persist provider/model overrides, set status `queued`, commit, then enqueue message and return 202 payload.

- [ ] **Step 3: Implement GET `action=list_generations`**

Return per-course generation history with status, settings snapshot, and token estimates for Flashcards history panel.

- [ ] **Step 4: Implement GET `action=get_generation_status`**

Return lightweight polling payload (`generation_id`, `status`, `error?`) for active jobs.

- [ ] **Step 5: Implement GET `action=get_generation`**

Return viewer-ready payload including persisted cards and lineage metadata.

- [ ] **Step 6: Implement POST `action=save_artifact`**

Create material row (`source_type='generated'`, `doc_type='flashcards'`) and persist `artifact_material_id` link.

- [ ] **Step 7: Implement POST `action=resolve_regeneration`**

Support `save_both`, `replace`, and `revert` semantics matching quiz Session 2 behavior.

- [ ] **Step 8: Implement GET `action=export_pdf`**

Generate downloadable PDF from persisted cards via `flashcards_pdf_builder`.

- [ ] **Step 9: Implement DELETE generation endpoint with artifact backprop cleanup**

Delete linked generated material first (if present), then remove generation.

- [ ] **Step 10: Verify module compile**

Run: `python3 -m py_compile api/flashcards.py api/services/flashcards_token_estimator.py api/services/flashcards_pdf_builder.py`

---

## Task 3: Queue Worker Runtime (`lambda/flashcards_generate`)

**Files:**
- Create: `lambda/flashcards_generate/handler.py`
- Create: `lambda/flashcards_generate/db.py`
- Create: `lambda/flashcards_generate/Dockerfile`
- Create: `lambda/flashcards_generate/requirements.txt`
- Create: `lambda/flashcards_generate/build.sh`

- [ ] **Step 1: Build SQS handler skeleton with per-record processing**

Parse message payload, fetch generation row, enforce idempotent transition `queued -> generating`, and skip already-terminal rows.

- [ ] **Step 2: Implement provider parity calls (OpenAI/Claude/Gemini)**

Use direct REST request helpers with robust error extraction and stable payload conventions.

- [ ] **Step 3: Implement robust JSON extraction + schema normalization**

Handle fenced/raw/object outputs; normalize aliases (`front/back`, `term/definition`, `question/answer`, optional hint fields).

- [ ] **Step 4: Persist cards and finish lifecycle transition**

Write ordered cards to `flashcard_cards`, clear prior cards for regeneration if needed, mark generation `ready`.

- [ ] **Step 5: Implement failure handling path**

Capture bounded error text and set generation `failed` without crashing batch processor.

- [ ] **Step 6: Verify worker scripts compile**

Run:
- `python3 -m py_compile lambda/flashcards_generate/handler.py lambda/flashcards_generate/db.py`
- `bash -n lambda/flashcards_generate/build.sh`

---

## Task 4: Frontend Integration and Viewer Routing

**Files:**
- Modify: `src/Flashcards.jsx`
- Modify: `src/FlashcardViewer.jsx`
- Create: `src/FlashcardViewerRoute.jsx`
- Modify: `src/components/GenerationConfirmModal.jsx`
- Modify: `src/MaterialsPage.jsx`
- Modify: `src/App.jsx`
- Modify: `src/QuizViewerRoute.jsx` (parity cleanup)

- [ ] **Step 1: Switch Flashcards generation flow to estimate -> confirm -> queue-start**

Remove legacy synchronous assumptions and call `/api/flashcards` actions only.

- [ ] **Step 2: Add persistent generation history + status badges**

Show draft/queued/generating/ready/failed with polling for in-flight rows.

- [ ] **Step 3: Add polling resume behavior and cleanup**

On mount/history fetch, auto-attach polling for queued/generating rows; cleanup timers on unmount/course change.

- [ ] **Step 4: Ensure confirm modal supports flashcards mode with model override**

Display flashcards token and summary fields; allow provider/model selection; disable actions while queueing.

- [ ] **Step 5: Wire viewer actions for save/export/regenerate/resolve**

Integrate with `save_artifact`, `export_pdf`, and `resolve_regeneration`.

- [ ] **Step 6: Add dedicated viewer route for generation deep-links**

Load by `generation_id`, support regeneration from route context, and poll route-level regeneration status.

- [ ] **Step 7: Add materials deep-link reopening**

Handle `flashcards://generation/<id>` links and navigate to `/course/:id/flashcards/:generationId`.

- [ ] **Step 8: Implement parity cleanup + race fixes from final pass**

- Prevent `loadHistory` callback churn from causing avoidable re-fetch loops.
- Prevent duplicate route-level regenerate confirms while queue start is in-flight.
- Disable modal cancel during loading to avoid mid-submit race.

- [ ] **Step 9: Regenerate must return to prefilled editor controls (not direct estimate confirm only)**

- For both list and viewer regenerate actions, reopen the generator/editor state first with prefilled values from the selected generation.
- Prefill all editable controls, not just provider/model:
  - Quiz: topic, TF/SA/LA/MCQ counts, MCQ option count, selected sources, provider, model.
  - Flashcards: topic, card count, depth, selected sources, provider, model.
- Preserve parent generation lineage by storing pending parent id and applying it on next Generate click.
- Only then run estimate -> confirm -> queue after the user can modify controls.

- [ ] **Step 10: Saved button visual parity across viewers**

- Match saved-state visual treatment used in quiz viewer:
  - saved: green border + green tint background + green text + non-interactive cursor
  - error: red border/text with retry affordance
  - idle: neutral gray style

- [ ] **Step 11: Floating course toolbar parity in route-level viewers**

- Route-level viewer flows must preserve the persistent floating toolbar from CoursePage/Quiz route.
- Add toolbar actions for `Materials`, `Chat`, `Generate` that:
  - write `localStorage.setItem('coursemate_active_tab_<courseId>', tab)`
  - navigate back to `/course/<courseId>`
- Keep toolbar optional/injected so embedded/non-route viewer contexts do not double-render navigation chrome.

---

## Task 5: Infrastructure and Runbook

**Files:**
- Create: `scripts/infra/setup_flashcards_generation_infra.sh`
- Create: `lambda/flashcards_generate/iam/api-send-message-policy.json`
- Create: `lambda/flashcards_generate/iam/worker-consume-policy.json`
- Create: `docs/superpowers/specs/2026-03-25-flashcards-generation-infra-runbook.md`

- [ ] **Step 1: Add idempotent infra setup script**

Provision DLQ, primary queue, redrive policy, and event source mapping.

- [ ] **Step 2: Add IAM policy templates for API enqueue and worker consume**

Keep permissions narrowly scoped to queue and runtime needs.

- [ ] **Step 3: Document rollout + rollback runbook**

Cover env vars, deployment order, verification checks, and rollback knobs.

- [ ] **Step 4: Validate shell + JSON artifacts**

Run:
- `bash -n scripts/infra/setup_flashcards_generation_infra.sh`
- `python3 -m json.tool lambda/flashcards_generate/iam/api-send-message-policy.json`
- `python3 -m json.tool lambda/flashcards_generate/iam/worker-consume-policy.json`

---

## Task 6: Tests and Final Verification

**Files:**
- Create: `tests/test_flashcards_phase2_validation.py`

- [ ] **Step 1: Add estimator validation tests**

Assert deterministic, bounded token estimate behavior.

- [ ] **Step 2: Add worker normalization tests**

Validate alias mappings and structural normalization behavior.

- [ ] **Step 3: Add PDF builder smoke test**

Assert non-empty bytes output with mocked rendering dependency.

- [ ] **Step 4: Run flashcards test suite**

Run: `python3 -m pytest tests/test_flashcards_phase2_validation.py -q`
Expected: all tests pass.

- [ ] **Step 5: Run quiz regression suite**

Run: `python3 -m pytest tests/test_quiz_validation.py tests/test_quiz_phase2_validation.py -q`
Expected: existing quiz tests remain green.

- [ ] **Step 6: Manual validation checklist**

1. Estimate creates draft and opens confirm modal with token ranges.
2. Confirm transitions draft to queued and history shows in-flight status.
3. Refresh during queued/generating resumes polling and final ready state.
4. Viewer route deep-link regenerate + resolution banner flow.
5. Save artifact creates generated material and deep-link reopens viewer.
6. Delete generation removes linked artifact material.
7. Export PDF downloads valid deck.
8. Regenerate from both list and viewer returns to prefilled generator controls before estimate/confirm.
9. Saved button style matches quiz parity (green saved state, red error retry state).
10. Route viewer shows floating toolbar with working Materials/Chat/Generate navigation.

---

## Implementation Outcome (What Was Delivered)

- Database schema for async flashcards lifecycle and card persistence was added.
- `api/flashcards.py` was implemented with full action surface (`estimate`, `generate`, `list`, `status`, `get`, `save_artifact`, `resolve_regeneration`, `export_pdf`, delete).
- Queue worker runtime was implemented under `lambda/flashcards_generate` with provider parity and idempotent lifecycle handling.
- Frontend flow was migrated to async estimate-confirm-queue with polling history and deep-link route reopening.
- Infra setup script, IAM templates, and runbook were added.
- Flashcards validation tests were added and passing.
- Final-pass race/churn fixes were applied in `Flashcards.jsx`, `FlashcardViewerRoute.jsx`, and `GenerationConfirmModal.jsx`.
