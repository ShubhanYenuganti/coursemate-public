# Wave 4 — Monolith Decomposition + Restyle Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Checkbox steps.
>
> **Altitude note:** Mechanical swaps follow `docs/superpowers/migration-checklist.md`. This plan adds STRUCTURAL extraction: both files already contain named in-file sub-components, so decomposition = move each into its own file (behavior-preserving) THEN restyle it to shadcn. Each component = extract → restyle → verify → commit.

**Goal:** Decompose `MaterialsPage.jsx` (2,279 lines) and `ChatTab.jsx` (3,422 lines) into focused per-component files, and restyle each to shadcn + indigo tokens — including a full visual refresh of the chat conversation surface (bubbles, streaming indicator, pins).

**Architecture:** Two sub-phases. 4A = MaterialsPage, 4B = ChatTab. For each in-file component, create `src/<Page>/<Component>.jsx`, move the code verbatim, wire imports/exports, confirm build+tests, commit (extraction). Then a second commit restyles it. **Critical export constraints:** `CoursePage.jsx` imports `MaterialsPage` (default) from `./MaterialsPage.jsx` AND imports `ChatTab` (default) + `{ PROVIDER_MODELS }` from `./ChatTab.jsx`. The default exports and the `PROVIDER_MODELS` re-export MUST remain on those two entry files.

**Tech Stack:** Vite + React 19 (JSX), Tailwind v4, shadcn/ui.

**Verification model (per task):** `npm run build` clean → `npm test` green → manual/visual check. Extraction tasks: behavior must be byte-identical (only file location changes) — diff the moved code to confirm no edits crept in. Restyle tasks: apply checklist mappings. NO DOM test harness — don't add one.

---

## Phase 4A — MaterialsPage decomposition

Target dir: `src/MaterialsPage/`. Source line ranges in current `src/MaterialsPage.jsx`. MaterialsPage has **4 `<select>`** (doc-type in StagingItemRow; filters in FilterBar) — apply the Radix Select empty-string sentinel rule (checklist §3) when restyling those.

### Task 4A.1: Extract constants + atoms
- [ ] Create `src/MaterialsPage/constants.js` (from lines 12–130) and `src/MaterialsPage/atoms.jsx` (FileTypeIcon 132, Spinner 192, VisibilityToggle 215, TrashIcon 248, SourceTypeBadge 691, EmbedStatusBadge 705). Move verbatim, export each, import back into MaterialsPage.jsx. Build + test. Commit: `refactor(materials): extract constants + atoms`.

### Task 4A.2: Restyle atoms
- [ ] In `atoms.jsx`: badges → `Badge`; `Spinner` default `className="text-indigo-500"` → `text-primary`; retint grays. Build + test. Commit: `refactor(materials): atoms -> shadcn Badge/tokens`.

### Task 4A.3: Extract + restyle UploadZone (270–357)
- [ ] Move to `src/MaterialsPage/UploadZone.jsx`; restyle dropzone borders/buttons to tokens + `Button`. Build + test. Commit (extract then restyle, or one commit if small).

### Task 4A.4: Extract + restyle UploadItemRow (359–448)
- [ ] Move to `src/MaterialsPage/UploadItemRow.jsx`; row buttons → `Button`, status → `Badge`, `Progress` for upload bar. Build + test. Commit.

### Task 4A.5: Extract + restyle StagingItemRow (450–509)
- [ ] Move to `src/MaterialsPage/StagingItemRow.jsx`. GOTCHA: doc-type `<select>` → `Select` with sentinel rule. Buttons → `Button`. Build + test. Commit.

### Task 4A.6: Extract + restyle SyncModal (509–670) → Dialog
- [ ] Move to `src/MaterialsPage/SyncModal.jsx`; convert to `Dialog` (controlled open-state preserved). Preserve sync job submission logic. MANUAL interaction check. Commit: `refactor(materials): SyncModal -> Dialog`.

### Task 4A.7: Extract + restyle ProgressPanel (746–878)
- [ ] Move to `src/MaterialsPage/ProgressPanel.jsx`; retint, `Progress` bars, `Button` for dismiss. Preserve the localStorage-backed progress state contract (props from CoursePage). Build + test. Commit.

### Task 4A.8: Extract + restyle MaterialCard (880–1031)
- [ ] Move to `src/MaterialsPage/MaterialCard.jsx`; wrap in `Card`, buttons → `Button`, badges → `Badge`. Build + test. Commit.

### Task 4A.9: Extract + restyle FilterBar (1035–1096)
- [ ] Move to `src/MaterialsPage/FilterBar.jsx`. GOTCHA: filter `<select>`s → `Select` with sentinel rule (or `ToggleGroup`/`Tabs` if pill-style). Build + test. Commit.

### Task 4A.10: Restyle main MaterialsPage container (1098+)
- [ ] In `src/MaterialsPage.jsx` (now slim): retint remaining shell grays/indigo to tokens, remaining buttons → `Button`. Confirm DEFAULT export unchanged. Grep gate clean. Build + test; visual check. Commit: `refactor(materials): container shell -> tokens`.

---

## Phase 4B — ChatTab decomposition + chat-surface refresh

Target dir: `src/ChatTab/`. Source line ranges in current `src/ChatTab.jsx`. **Keep `export default ChatTab` and the `export { PROVIDER_MODELS }` re-export on `src/ChatTab.jsx`** (CoursePage depends on both).

### Task 4B.1: Extract icons (18–229)
- [ ] Move all icon components (PlusIcon … PaperclipIcon, SpinnerIcon, NotionBadgeIcon) into `src/ChatTab/icons.jsx`; export each; import back. Pure move. Build + test. Commit: `refactor(chat): extract icons`.

### Task 4B.2: Extract atoms (FileTypeBadge 240, MaterialToggle 260) + helpers (286–322)
- [ ] `src/ChatTab/atoms.jsx` + `src/ChatTab/helpers.js`. Move verbatim. Build + test. Commit.

### Task 4B.3: Extract + restyle ConversationList (ConvItem 324, ArchivedConvItem 354)
- [ ] `src/ChatTab/ConversationList.jsx`; restyle list rows to tokens, action buttons → `Button` ghost/icon, `DropdownMenu` for the per-conversation overflow (archive/delete/rename). Build + test. Commit.

### Task 4B.4: Extract + restyle SourcesPanel (378–534)
- [ ] `src/ChatTab/SourcesPanel.jsx`; retint, buttons → `Button`, close → ghost icon. Preserve chunk/citation data flow. Build + test. Commit.

### Task 4B.5: Extract + FULL RESTYLE MessageBubble (534–1027) — chat surface
- [ ] `src/ChatTab/MessageBubble.jsx` (~490 lines, the largest unit). Extract first (verify build), then full visual refresh to Clean-Minimal/indigo: user vs assistant bubble styling, avatar, edit/copy/pin/revert action buttons → `Button` ghost/icon + `Tooltip`. PRESERVE: `ReactMarkdown` + KaTeX rendering pipeline, the `_streaming`/`_generationProposal` branches, and all message-action handlers. Build + test; visual check vs mockup. Commit: `refactor(chat): MessageBubble -> extracted + Clean Minimal`.

### Task 4B.6: Extract + FULL RESTYLE StreamingStatus (LiveStatusLine 1035, ToolTraceIndicator 1166) — chat surface
- [ ] `src/ChatTab/StreamingStatus.jsx`; restyle the streaming status bubble + bouncing dots (`bg-indigo-400 animate-bounce` → `bg-primary`/token), retrieval-progress indicator to tokens. Preserve the live tool-trace data wiring. Build + test; visual check. Commit.

### Task 4B.7: Extract + FULL RESTYLE PinsPanel (1204–1328) — chat surface
- [ ] `src/ChatTab/PinsPanel.jsx`; restyle pinned message cards → `Card`/tokens, expand/collapse + delete → `Button`/`Tooltip`. Preserve pin data + delete handler. Build + test; visual check. Commit.

### Task 4B.8: Extract + restyle Composer (from main, ~line 1330+)
- [ ] `src/ChatTab/Composer.jsx`; the composer `<textarea>` (auto-grow, max-height logic at line ~1330) → keep auto-grow logic, restyle with `Textarea`/tokens; send/attach buttons → `Button`; model picker → `DropdownMenu` or `Select`. PRESERVE the `composerGate` logic and auto-resize behavior. Build + test (`composerGate.test.js` must stay green). Commit.

### Task 4B.9: Restyle main ChatTab container (1353+)
- [ ] In slim `src/ChatTab.jsx`: tab UI → `Tabs`; remaining shell grays/indigo → tokens; `sonner` for toasts; `Skeleton` for loading. Confirm DEFAULT export + `PROVIDER_MODELS` re-export intact. Grep gate clean. Build + test; full manual chat smoke test (send message, stream, pin, edit, sources, new/archive conversation). Commit: `refactor(chat): container -> Tabs + tokens`.

---

## Self-Review
- **Coverage:** Every in-file sub-component of both monoliths has an extract+restyle task with concrete source line ranges and target file paths. Chat-surface full-refresh (4B.5–4B.7) covered per the design decision.
- **Export safety:** Default exports + `PROVIDER_MODELS` re-export constraints called out explicitly (CoursePage depends on them).
- **Test safety:** `FlashcardViewer.test.jsx` not in scope; `composerGate.test.js` + `syncWorkflow.test.js` must stay green (4B.8 flagged).
- **Gotchas:** 4 MaterialsPage `<select>`s (sentinel rule), SyncModal→Dialog, KaTeX/markdown + streaming/auto-grow logic preservation all flagged.
- **Sequencing:** Extraction precedes restyle within each task so a regression is bisectable to either the move or the styling.
- **No placeholders:** Exact swaps via the checklist; structural tasks carry real line ranges + paths.
