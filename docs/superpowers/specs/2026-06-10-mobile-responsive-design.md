# Mobile Responsive Pass — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 2.2
**Scope:** `src/FlashcardViewer.jsx`, `src/ChatTab.jsx`, `src/Dashboard.jsx`, plus a PWA manifest. Prioritized flashcards → chat → dashboard.

## Problem

`src/ChatTab.jsx` (3,405 lines) has **zero** Tailwind responsive breakpoint classes (`sm:`/`md:`/`lg:`);
`Dashboard.jsx` has 2, `MaterialsPage.jsx` has 1. For a student product the phone is the default
device — especially flashcards, which already have a "play" mode that wants to be a commute feature.
Today the chat sidebar, composer, and card controls assume desktop width and overflow or clip on
mobile.

## Goal

The three highest-traffic surfaces are usable one-handed on a ~375px-wide phone:
1. **Flashcards** — full-bleed card, large tap targets for flip/next/prev/rate, swipe to advance.
2. **Chat** — sidebar collapses into a drawer (collapse state already exists:
   `sidebarCollapsed`/`SIDEBAR_DEFAULT_WIDTH` in `ChatTab.jsx`); composer and message bubbles reflow.
3. **Dashboard** — course grid becomes a single column; widgets stack.
Plus a PWA manifest so the app can be installed to the home screen.

## Decisions

1. **Mobile-first additive classes, not a rewrite.** Add `sm:`/`md:` modifiers to existing
   elements; never restructure working desktop layout. This honors the "surgical changes" rule and
   keeps the giant `ChatTab.jsx` diff reviewable.
2. **Reuse existing state.** The chat sidebar already has `sidebarCollapsed`; the mobile drawer is a
   CSS/transform treatment of that same state plus a hamburger toggle and a backdrop — no new data
   model.
3. **Swipe via a tiny pure helper.** A `swipeDirection(touchStartX, touchEndX, threshold)` helper in
   `src/utils/` is unit-testable; the viewer wires `onTouchStart/onTouchEnd` to it.
4. **Verify with Playwright viewports**, not screenshots-by-eye only. The repo already runs
   Playwright (`tests/playwright/`); add a 375px-viewport smoke that asserts no horizontal overflow
   on the three surfaces.
5. **PWA is manifest-only in v1.** A `manifest.webmanifest` + icons + `<link rel="manifest">`.
   Service-worker/offline is out of scope (YAGNI for v1).

## Breakpoint plan (concrete)

- **FlashcardViewer:** card container `w-full max-w-2xl` → on mobile `px-3`; control bar buttons
  `min-h-[44px] min-w-[44px]` (Apple tap-target minimum); play-interval control wraps. Swipe left =
  next, right = prev.
- **ChatTab:** sidebar wrapper gets `hidden md:flex` for the persistent rail; on `<md` a drawer
  (`fixed inset-y-0 left-0 z-40 transform transition-transform` toggled by `sidebarCollapsed`) with a
  `md:hidden` hamburger button in the header and a tap-to-close backdrop. Message list `px-2 md:px-6`;
  composer `text-sm` and full-width.
- **Dashboard:** course grid `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`; header actions wrap.

## Verification

- vitest: `swipeDirection` helper (left/right/below-threshold).
- Playwright @375px: load flashcards, chat, dashboard; assert
  `document.documentElement.scrollWidth <= window.innerWidth` (no horizontal scroll) and that the
  chat hamburger opens/closes the drawer.
- Manual: real-device or devtools-responsive walkthrough of the three surfaces.
