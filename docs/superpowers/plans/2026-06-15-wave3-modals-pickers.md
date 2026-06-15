# Wave 3 — Modals & Pickers Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Checkbox steps.
>
> **Altitude note:** Follow `docs/superpowers/migration-checklist.md` for mechanical swaps. These four components are interaction-heavy (overlays, focus, keyboard) so behavior preservation is the priority — verify the trigger/open/close and selection flows still work identically.

**Goal:** Migrate the 2 modal components to `Dialog` and the 2 target pickers to `Popover` + `Command`, preserving all open/close, focus, and selection behavior.

**Architecture:** Presentation refactor with structural component swaps. The modals currently manage their own open state + hand-rolled `fixed inset-0` overlay; the pickers manage their own dropdown + search. Map these to the shadcn primitives' controlled APIs WITHOUT changing the data/callbacks they expose to parents (CoursePage / MaterialsPage rely on their props).

**Tech Stack:** Vite + React 19 (JSX), Tailwind v4, shadcn/ui (`dialog`, `popover`, `command` already installed).

**Verification model (per task):** `npm run build` clean → `npm test` green → MANUAL interaction check (open, close via X / Esc / overlay click, submit, keyboard nav). Grep gate per file. These are the highest-interaction-risk tasks in the rollout — do the manual check every time.

**Order:** CreateCourseModal → SharingAccessModal → GDriveTargetPicker → NotionTargetPicker.

---

### Task 1: CreateCourseModal → Dialog
**Files:** `src/CreateCourseModal.jsx` (171 lines; 3 `<button>`, 1 `<input>`, 1 `<textarea>`, 1 overlay, 4 indigo, 16 gray). Consumed by `CoursePage` header as `<CreateCourseModal />` (self-contained, renders its own trigger).
- [ ] **Step 1:** Identify the component's own open-state (`useState` boolean) and its trigger button. Replace the hand-rolled `fixed inset-0` overlay + panel with `Dialog`/`DialogContent`, keeping the existing open-state wired to `open`/`onOpenChange` (controlled), OR use `DialogTrigger asChild` around the existing trigger button. Preserve the create-course submit handler and its fetch exactly.
- [ ] **Step 2:** `<input>` (course title) → `Input` + `Label`; `<textarea>` (description) → `Textarea`. The 3 buttons → `Button` (submit=default, cancel=outline, trigger keeps its role). Use `DialogHeader`/`DialogTitle`/`DialogFooter`.
- [ ] **Step 3:** Retint 4 indigo + 16 gray. Build + test; grep clean.
- [ ] **Step 4:** MANUAL: open from CoursePage header, create a course, cancel, Esc-to-close, overlay-click-close all work.
- [ ] **Step 5:** Commit: `refactor(create-course): hand-rolled modal -> Dialog`.

### Task 2: SharingAccessModal → Dialog
**Files:** `src/SharingAccessModal.jsx` (256 lines; 3 `<button>`, 1 `<input>`, 8 indigo, 17 gray). Consumed by `CoursePage` as `<SharingAccessModal courseId csrfToken isOwner />`. Inventory shows no `fixed inset-0` overlay match — confirm whether it renders inline or as a modal; convert to `Dialog` only if it IS a modal, else treat as a `Card`-wrapped inline panel.
- [ ] **Step 1:** Determine modal vs inline. If modal → `Dialog` (as Task 1). If inline panel → wrap sections in `Card`. Preserve the `/api/sharing` calls, the owner-gated controls, and the pending-invite / collaborator list logic untouched.
- [ ] **Step 2:** `<input>` (invite email) → `Input` + `Label`; 3 buttons → `Button` (invite=default, remove=destructive/outline). Collaborator rows: status → `Badge`.
- [ ] **Step 3:** Retint 8 indigo + 17 gray. Build + test; grep clean.
- [ ] **Step 4:** MANUAL: invite flow, remove collaborator, owner vs non-owner visibility unchanged.
- [ ] **Step 5:** Commit: `refactor(sharing): -> Dialog/Card + shadcn`.

### Task 3: GDriveTargetPicker → Popover + Command
**Files:** `src/components/GDriveTargetPicker.jsx` (313 lines; 6 `<button>`, 2 `<input>`, 1 overlay, 13 indigo, 31 gray). Used by MaterialsPage sync flow.
- [ ] **Step 1:** Replace the hand-rolled dropdown/overlay with `Popover` (`PopoverTrigger` + `PopoverContent`). Inside, replace the search `<input>` + results list with `Command`/`CommandInput`/`CommandList`/`CommandItem` for the searchable folder/target list. Preserve the selection callback and the chosen-target data shape the parent consumes.
- [ ] **Step 2:** Remaining buttons → `Button`; second `<input>` (if a non-search field) → `Input`. Retint 13 indigo + 31 gray. Build + test; grep clean.
- [ ] **Step 3:** MANUAL: open picker, type to filter, select a target, confirm parent receives the same selection payload; keyboard nav (arrows/enter) works.
- [ ] **Step 4:** Commit: `refactor(gdrive-picker): -> Popover + Command`.

### Task 4: NotionTargetPicker → Popover + Command
**Files:** `src/components/NotionTargetPicker.jsx` (402 lines; 6 `<button>`, 2 `<input>`, 1 overlay, 11 indigo, 36 gray). Used by MaterialsPage sync flow. NOTE: Notion API uses `data_source` (renamed from database filter) — this is data-layer, do not touch it; only the picker UI changes.
- [ ] **Step 1:** Same pattern as Task 3 — `Popover` + `Command` for the searchable Notion target list. Preserve the selection payload and any workspace/database fetch logic.
- [ ] **Step 2:** Buttons → `Button`; non-search `<input>` → `Input`. Retint 11 indigo + 36 gray. Build + test; grep clean.
- [ ] **Step 3:** MANUAL: open, filter, select, keyboard nav; parent receives identical payload.
- [ ] **Step 4:** Commit: `refactor(notion-picker): -> Popover + Command`.

---

## Self-Review
- **Coverage:** All 4 components have tasks with concrete element inventory + interaction gotchas (controlled open-state, selection-payload preservation, owner-gating, Notion data_source caveat).
- **Behavior priority:** Every task ends with a MANUAL interaction check — these are the riskiest swaps.
- **Open question flagged:** SharingAccessModal modal-vs-inline must be confirmed at execution (Task 2 Step 1 branches on it).
- **Out of scope:** Monoliths (Wave 4).
