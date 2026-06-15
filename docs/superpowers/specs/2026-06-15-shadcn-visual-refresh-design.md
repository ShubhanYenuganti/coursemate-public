# shadcn/ui Visual Refresh — Design

**Date:** 2026-06-15
**Status:** Approved (design); pending implementation plan
**Scope:** Presentation layer only. No business logic, API, SSE/streaming, routing, or KaTeX/markdown pipeline changes.

## Goal

Use shadcn/ui as the foundation for a genuine **visual refresh** of the CourseMate frontend (35 components, ~16.5k lines of JSX) — not a like-for-like primitive swap. Outcome: a cohesive, modern look applied consistently across every page.

## Design Direction

- **Aesthetic:** Clean Minimal — neutral grays, generous whitespace, subtle borders, content-first. This is shadcn's `radix-luma` / neutral base, kept as the structural foundation.
- **Accent:** the existing brand indigo, **Tailwind `indigo-600` (`#4f46e5`)**, used as the single accent for primary actions, progress, links, badges, and focus rings. (Chosen because the codebase already uses `indigo-600` ~104 times with a full indigo ramp.)
- **Theme:** **light-only** for now. The app currently has no dark mode (zero `dark:` classes, no toggle). shadcn's `.dark` token block stays in `App.css` but dormant, so dark mode can be enabled later with no rework.

## Current State (verified)

- Vite + React 19, **JavaScript** (`.jsx`, no TypeScript). Routing centralized in `src/App.jsx`.
- Tailwind v4 via `@tailwindcss/postcss` (PostCSS), `@import "tailwindcss"` in `src/App.css`.
- shadcn installed: `style: radix-luma`, `tsx: false`, base color neutral, icon library `lucide`, global CSS `src/App.css`. `radix-ui` + `lucide-react` deps present. `button.jsx` in `src/components/ui/`, `cn()` in `src/lib/utils.js`. `@` → `./src` alias wired in `vite.config.js` + `jsconfig.json`; build verified clean.
- Large monoliths: `ChatTab.jsx` (3,422 lines), `MaterialsPage.jsx` (2,279).

## Section 1 — Token Foundation

shadcn `init` wrote `:root` (light) and `.dark` (dormant) CSS-variable blocks into `src/App.css`, currently neutral. Every shadcn component references these variables, so re-pointing a few variables re-themes all shadcn components without per-component edits.

Changes in `:root`:
- `--primary` → `#4f46e5` (indigo-600); `--primary-foreground` → white
- `--ring` → indigo-600 (focus rings match accent)
- `--accent` / `--accent-foreground` → light indigo (indigo-50 / indigo-700) for hover/selected states
- `--background`, `--foreground`, `--border`, `--muted` → stay neutral (Clean Minimal)

`.dark` block left in place, unused. The existing `@theme` block (custom animations `fadeInUp`, `float`, `shake`) is untouched and coexists with the shadcn variables. The ~104 hand-written `indigo-600` utilities keep working during the transition, and new shadcn components automatically match them — no flag day.

## Section 2 — Shared Primitives Layer

Batch-add the reused primitives up front (source files in `src/components/ui/`, all indigo via Section 1):

| Primitive | Replaces |
|---|---|
| `button` (done) | ad-hoc indigo buttons |
| `card` | Dashboard / CoursePage / Quiz / Flashcard panels |
| `dialog` | CreateCourseModal, SharingAccessModal |
| `tabs` | tab UI inside ChatTab |
| `input`, `textarea`, `label` | SearchChat + forms |
| `select`, `popover`, `command` | NotionTargetPicker, GDriveTargetPicker |
| `badge` | status/"due" pills |
| `progress` | course/quiz progress bars |
| `dropdown-menu` | profile / overflow menus |
| `sonner` | toast notifications |
| `skeleton` | loading states |
| `tooltip` | SM-2 hint, icon buttons |

**Chat conversation surface:** shadcn has no chat/message-thread primitive. The bespoke conversation UI — message bubbles (`isUser` branching, avatars), markdown+KaTeX rendering, streaming status bubble (bouncing indigo dots), citation/source pins — is **hand-restyled** to the Clean-Minimal/indigo look during ChatTab's decompose pass (decision: **full visual refresh** of the chat surface, not chrome-only). Primitives cover only the chrome: composer (`Textarea`+`Button`, custom auto-grow retained), action buttons, tabs, menus, tooltips, toasts.

## Section 3 — Migration Pattern (set by CoursePage pilot)

**Pilot = `CoursePage.jsx` (416 lines)** — moderate size, exercises the real primitives most pages reuse. It becomes the reference implementation, producing a written migration checklist reused verbatim for all later pages (this is what makes rollout fast — pattern-matching, not problem-solving).

Per-page pattern:
1. Inventory the page's UI into primitives.
2. Replace structural wrappers with shadcn primitives; move indigo utilities onto the token system.
3. Extract repeated blocks into small local components (e.g. `<CourseHeader>`, `<MaterialCard>`).
4. Verify (see Section 4 loop).

## Section 4 — Rollout, Monoliths, Verification

**Order:**
1. Foundation — Section 1 tokens + Section 2 primitives install.
2. Pilot: CoursePage → migration checklist.
3. Wave 1 (small/high-visibility): LandingPage, Dashboard, ProfilePage, SignInPage, LegalPage/Privacy/Terms.
4. Wave 2 (feature pages): Flashcards, FlashcardViewer, Quiz, QuizViewer, Reports, ReportsViewer, Generations, CardViewer.
5. Wave 3 (modals & pickers): CreateCourseModal, SharingAccessModal → `Dialog`; NotionTargetPicker, GDriveTargetPicker → `Popover`+`Command`.
6. Wave 4 (monoliths, decompose + restyle): MaterialsPage (2,279); ChatTab (3,422, incl. full conversation refresh).

**Monolith handling:** decompose-as-we-restyle. ChatTab splits into focused subcomponents — `<MessageBubble>`, `<StreamingStatus>`, `<Composer>`, `<ConversationList>`, `<CitationPins>` — each independently styleable and testable instead of one 3.4k-line file.

**Verification loop (per page):**
- Page renders + interactions work (manual eyeball vs. mockup).
- `npm test` (Vitest) green.
- `npm run build` clean (catches alias/import breaks).
- Surgical diffs: every changed line traces to the refresh.

**Untouched:** business logic, API calls, SSE/streaming, routing, KaTeX/markdown pipeline.

## Implementation Note

When implementation begins, create a new git branch first (`git checkout -b ...`) before any code changes.
