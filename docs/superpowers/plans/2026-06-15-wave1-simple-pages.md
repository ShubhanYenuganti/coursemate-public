# Wave 1 — Simple Pages Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
>
> **Altitude note:** These pages follow the *proven CoursePage pattern*. The exact class→token and element→primitive mappings live in `docs/superpowers/migration-checklist.md` (canonical, exact) with the CoursePage commits (`f11d11f`…`056518f`) as worked examples. Each task below is concrete about WHICH elements in WHICH file to migrate and the file-specific gotchas; apply the checklist mappings for the mechanical swaps. Do not invent new patterns.

**Goal:** Migrate the 7 simple/low-risk pages to shadcn primitives + indigo Clean-Minimal tokens.

**Architecture:** Pure presentation refactor. Markup/className only — no handler, state, API, or routing changes. Token foundation + primitives already in place (branch `shadcn-visual-refresh`).

**Tech Stack:** Vite + React 19 (JSX), Tailwind v4, shadcn/ui (radix-luma, indigo tokens).

**Verification model (per task):** `npm run build` clean → `npm test` green → visual check vs Clean-Minimal/indigo. Grep gate per file: `grep -nE "gray-[0-9]|bg-white|indigo-[0-9]|red-[0-9]" src/<File>.jsx` returns only intentional remainders (ideally empty). NO DOM test harness exists — do not add one.

**Order (smallest/lowest-risk first):** SignInPage → LegalPage → PrivacyPolicy → TermsOfService → Dashboard → LandingPage → ProfilePage.

---

### Task 1: SignInPage
**Files:** Modify `src/SignInPage.jsx` (71 lines; 0 `<button>`, 3 indigo, 4 gray).
- [ ] **Step 1:** No native buttons (Google sign-in widget). Retint the 3 `indigo-*` and 4 `gray-*` utilities to tokens per checklist §4 (`indigo-600`→`primary`, grays→`foreground`/`muted-foreground`/`border`). Do NOT alter the Google sign-in init logic.
- [ ] **Step 2:** `npm run build && npm test` → green. Grep gate clean.
- [ ] **Step 3:** Commit: `refactor(signin): retint to Clean Minimal tokens`.

### Task 2: LegalPage
**Files:** Modify `src/LegalPage.jsx` (36 lines; wrapper, 5 indigo, 10 gray).
- [ ] **Step 1:** This is a layout wrapper around PrivacyPolicy/TermsOfService. Retint indigo/gray utilities to tokens (checklist §4). If it has a back/nav `<button>`-like link, convert to `Button variant="ghost"`.
- [ ] **Step 2:** Build + test green; grep gate clean.
- [ ] **Step 3:** Commit: `refactor(legal): retint wrapper to tokens`.

### Task 3: PrivacyPolicy
**Files:** Modify `src/PrivacyPolicy.jsx` (123 lines; 0 indigo, 0 gray).
- [ ] **Step 1:** Inventory says zero hardcoded colors — likely already neutral prose. Verify with `grep -nE "gray-[0-9]|indigo-[0-9]|text-\[" src/PrivacyPolicy.jsx`. If truly none, ensure headings/links use `text-foreground`/`text-primary` tokens where appropriate; otherwise NO-OP and document it.
- [ ] **Step 2:** Build + test green.
- [ ] **Step 3:** Commit only if changed: `refactor(privacy): align prose to tokens` (skip if no-op).

### Task 4: TermsOfService
**Files:** Modify `src/TermsOfService.jsx` (115 lines; 0 indigo, 0 gray).
- [ ] **Step 1:** Same as Task 3 — verify no hardcoded colors; align links/headings to tokens if any. Likely no-op.
- [ ] **Step 2:** Build + test green.
- [ ] **Step 3:** Commit only if changed: `refactor(terms): align prose to tokens` (skip if no-op).

### Task 5: Dashboard
**Files:** Modify `src/Dashboard.jsx` (65 lines; 2 `<button>`, 2 indigo, 6 gray).
- [ ] **Step 1:** Convert the 2 `<button>`s to `Button` (pick variant by role: primary CTA = default, secondary = outline, icon/nav = ghost+icon). Retint 2 indigo + 6 gray to tokens. If Dashboard renders course cards/panels, wrap them in `Card` per checklist §3.
- [ ] **Step 2:** Build + test green; grep gate clean.
- [ ] **Step 3:** Commit: `refactor(dashboard): -> shadcn Button/Card + tokens`.

### Task 6: LandingPage
**Files:** Modify `src/LandingPage.jsx` (371 lines; 6 `<button>`, 1 overlay, 20 indigo, 49 gray).
- [ ] **Step 1:** Convert the 6 `<button>`s to `Button` (hero CTAs = default/lg; nav = ghost). The 1 modal/overlay (`fixed inset-0`/`z-50`): if it's a dialog, convert to `Dialog` per checklist §3; if it's a decorative gradient blob, leave structure and retint only.
- [ ] **Step 2:** Retint all 20 indigo + 49 gray to tokens (checklist §4). This is the public first impression — match the Clean-Minimal/indigo mockup closely.
- [ ] **Step 3:** Build + test green; grep gate clean; visual check.
- [ ] **Step 4:** Commit (may split CTA vs. retint): `refactor(landing): -> shadcn + Clean Minimal tokens`.

### Task 7: ProfilePage
**Files:** Modify `src/ProfilePage.jsx` (758 lines; 19 `<button>`, 3 `<input>`, 1 overlay, 20 indigo, 82 gray).
- [ ] **Step 1:** Largest Wave-1 page. Convert 19 `<button>`s → `Button`; 3 `<input>`s → `Input` (+`Label` where a field label exists). The 1 overlay → `Dialog` if it's a modal (e.g. confirm/delete).
- [ ] **Step 2:** Group settings sections into `Card`s per checklist §3 for visual consistency with CoursePage.
- [ ] **Step 3:** Retint 20 indigo + 82 gray to tokens. Watch for `text-red-*` → `text-destructive` (error/delete states).
- [ ] **Step 4:** Build + test green; grep gate clean; visual check.
- [ ] **Step 5:** Commit per section: `refactor(profile): <section> -> shadcn`.

---

## Self-Review
- **Coverage:** All 7 Wave-1 files have a task. Each names its concrete elements (from inventory) and the primitive mapping.
- **No placeholders:** Exact swap strings are the canonical ones in `migration-checklist.md`; each task specifies which elements/gotchas apply to that file.
- **Risk:** Pure presentation; build + existing tests + grep gate guard every task. PrivacyPolicy/TermsOfService may be no-ops (documented).
- **Out of scope:** Feature pages (Wave 2), modals/pickers (Wave 3), monoliths (Wave 4).
