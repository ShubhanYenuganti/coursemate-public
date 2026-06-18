# Wave 2 — Feature Pages Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Checkbox steps.
>
> **Altitude note:** Follow the proven CoursePage pattern. Exact mappings in `docs/superpowers/migration-checklist.md`; CoursePage commits are worked examples. Tasks below carry each file's element inventory + gotchas.

**Goal:** Migrate the 8 feature pages (flashcards, quizzes, reports, generations, card viewer) to shadcn primitives + indigo tokens.

**Architecture:** Presentation-only refactor; no logic/state/API/routing changes. These pages are large (800–1100 lines) and button-heavy, so commit per logical section.

**Tech Stack:** Vite + React 19 (JSX), Tailwind v4, shadcn/ui.

**Verification model (per task):** `npm run build` clean → `npm test` green → visual check. Grep gate per file. NO DOM test harness — don't add one. NOTE: `FlashcardViewer.test.jsx` exists (pure-logic test for `getFlashcardRatingKey`) and MUST stay green — do not change `FlashcardViewer`'s exported helpers or rating-key logic.

**Order (smallest first):** Generations → CardViewer → ReportsViewer → Reports → FlashcardViewer → Flashcards → QuizViewer → Quiz.

---

### Task 1: Generations
**Files:** `src/Generations.jsx` (107 lines; 1 `<button>`, 1 indigo, 4 gray).
- [ ] Convert the 1 button → `Button`; retint 1 indigo + 4 gray to tokens. Build + test green; grep clean. Commit: `refactor(generations): -> shadcn Button + tokens`.

### Task 2: CardViewer
**Files:** `src/CardViewer.jsx` (285 lines; 4 `<button>`, 1 `<input>`, 9 indigo, 18 gray).
- [ ] Convert 4 buttons → `Button`; the 1 `<input>` → `Input` (+`Label` if labeled). Wrap the card-display surface in `Card` if appropriate. Retint 9 indigo + 18 gray. Build + test; grep clean. Commit: `refactor(cardviewer): -> shadcn + tokens`.

### Task 3: ReportsViewer
**Files:** `src/ReportsViewer.jsx` (865 lines; 13 `<button>`, 2 overlays, 8 indigo, 72 gray).
- [ ] Convert 13 buttons → `Button`. The 2 overlays (`fixed inset-0`/`z-50`) → `Dialog` if modals (e.g. confirm-delete, share). Retint 8 indigo + 72 gray (heavy gray → mostly `text-muted-foreground`/`border`). Use `Badge` for any status pills, `Skeleton` for loading. Build + test; grep clean. Commit per section: `refactor(reportsviewer): <section> -> shadcn`.

### Task 4: Reports
**Files:** `src/Reports.jsx` (1034 lines; 10 `<button>`, 1 `<textarea>`, 28 indigo, 63 gray).
- [ ] Convert 10 buttons → `Button`; 1 `<textarea>` → `Textarea`. Wrap report cards/panels in `Card`. Retint 28 indigo + 63 gray. Build + test; grep clean. Commit per section: `refactor(reports): <section> -> shadcn`.

### Task 5: FlashcardViewer
**Files:** `src/FlashcardViewer.jsx` (864 lines; 24 `<button>`, **1 `<select>`**, 2 overlays, 30 indigo, 58 gray).
- [ ] GOTCHA A: the 1 `<select>` → shadcn `Select` with the Radix **empty-string sentinel** rule (checklist §3 — map `'none'`/`'default'`→`''`). Verify what `''` means for that select before mapping.
- [ ] GOTCHA B: do NOT touch `getFlashcardRatingKey` or any exported helper / the SM-2 rating logic — `FlashcardViewer.test.jsx` covers it and must stay green.
- [ ] Convert 24 buttons → `Button` (the rating buttons carry the SM-2 hint tooltip — use `Tooltip`). 2 overlays → `Dialog` if modals. Retint 30 indigo + 58 gray. Use `Progress` for any deck progress bar. Build + test; grep clean. Commit per section: `refactor(flashcardviewer): <section> -> shadcn`.

### Task 6: Flashcards
**Files:** `src/Flashcards.jsx` (1047 lines; 14 `<button>`, 1 `<input>`, 24 indigo, 68 gray).
- [ ] Convert 14 buttons → `Button`; 1 `<input>` → `Input`. The Due-Today widget / deck cards → `Card` + `Badge` (carry over the courseId-scoped widget styling). Retint 24 indigo + 68 gray. Build + test; grep clean. Commit per section: `refactor(flashcards): <section> -> shadcn`.

### Task 7: QuizViewer
**Files:** `src/QuizViewer.jsx` (1023 lines; 18 `<button>`, 1 `<input>`, 1 `<textarea>`, 2 overlays, 20 indigo, 98 gray).
- [ ] Convert 18 buttons → `Button`; `<input>`→`Input`, `<textarea>`→`Textarea`. Answer choices → consider `RadioGroup` (add via `npx shadcn add radio-group` if not present) ONLY if it maps cleanly to existing choice logic; otherwise `Button`-style toggles retinted to tokens. 2 overlays → `Dialog` if modals. Retint 20 indigo + 98 gray (highest gray count in the wave). `Progress` for quiz progress. Build + test; grep clean. Commit per section: `refactor(quizviewer): <section> -> shadcn`.

### Task 8: Quiz
**Files:** `src/Quiz.jsx` (1073 lines; 14 `<button>`, 1 `<input>`, 27 indigo, 69 gray).
- [ ] Convert 14 buttons → `Button`; 1 `<input>` → `Input`. Quiz list/config panels → `Card`. Retint 27 indigo + 69 gray. Build + test; grep clean. Commit per section: `refactor(quiz): <section> -> shadcn`.

---

## Self-Review
- **Coverage:** All 8 feature pages have tasks with concrete element counts + per-file gotchas (FlashcardViewer select sentinel + test-protected helper; QuizViewer RadioGroup caveat).
- **Test safety:** Explicitly protects `FlashcardViewer.test.jsx`.
- **No placeholders:** Exact swaps via `migration-checklist.md`; tasks specify elements/gotchas.
- **Out of scope:** Modals/pickers (Wave 3), monoliths (Wave 4). Note `RadioGroup` is the only potential new primitive — gated on a clean mapping.
