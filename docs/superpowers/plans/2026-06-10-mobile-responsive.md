# Mobile Responsive Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make flashcards, chat, and the dashboard usable one-handed on a 375px phone, and add a PWA manifest for home-screen install.

**Architecture:** Additive Tailwind `sm:`/`md:` classes on existing elements (no layout rewrite), reusing the chat's existing `sidebarCollapsed` state for a mobile drawer, a pure `swipeDirection` helper for card gestures, a Playwright 375px overflow smoke, and a manifest-only PWA.

**Tech Stack:** React + Vite + Tailwind, vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-10-mobile-responsive-design.md`

---

### Task 1: Swipe helper (pure, tested)

**Files:**
- Create: `src/utils/swipe.js`
- Test: `src/utils/swipe.test.js`

- [ ] **Step 1: Write the failing test**

```js
import { describe, it, expect } from 'vitest';
import { swipeDirection } from './swipe';

describe('swipeDirection', () => {
  it('detects left swipe past threshold', () => {
    expect(swipeDirection(300, 200, 50)).toBe('left');
  });
  it('detects right swipe past threshold', () => {
    expect(swipeDirection(200, 300, 50)).toBe('right');
  });
  it('ignores movement below threshold', () => {
    expect(swipeDirection(200, 210, 50)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/utils/swipe.test.js` — FAIL (module missing).

- [ ] **Step 3: Implement**

```js
// Pure: classify a horizontal swipe from start/end X. Returns 'left' | 'right' | null.
export function swipeDirection(startX, endX, threshold = 50) {
  const dx = endX - startX;
  if (Math.abs(dx) < threshold) return null;
  return dx < 0 ? 'left' : 'right';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/utils/swipe.test.js` — PASS.

- [ ] **Step 5: Commit**

```bash
git add src/utils/swipe.js src/utils/swipe.test.js
git commit -m "feat: add pure swipeDirection helper"
```

---

### Task 2: Flashcards mobile + swipe

**Files:**
- Modify: `src/FlashcardViewer.jsx`

- [ ] **Step 1: Enlarge tap targets and reflow controls**

On the flip/prev/next/rate control buttons, add `min-h-[44px] min-w-[44px]` and ensure the control
row uses `flex-wrap gap-2` so the play-interval control wraps on narrow widths. On the card
container add responsive padding `px-3 sm:px-6`.

- [ ] **Step 2: Wire swipe to advance/retreat**

Import the helper and attach touch handlers to the card container:

```jsx
import { swipeDirection } from './utils/swipe';
// inside component:
const touchStartX = useRef(null);
const onTouchStart = (e) => { touchStartX.current = e.changedTouches[0].clientX; };
const onTouchEnd = (e) => {
  const dir = swipeDirection(touchStartX.current ?? 0, e.changedTouches[0].clientX);
  if (dir === 'left') goNext();      // use the existing next handler name in this file
  if (dir === 'right') goPrev();     // use the existing prev handler name
};
// on the card wrapper: onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}
```

Use the file's existing next/prev handler names (search for the buttons that change `currentIndex`).

- [ ] **Step 3: Manually verify at 375px**

Run: `npm run dev`, open devtools responsive @375px on a flashcard generation. Swipe advances cards;
buttons are comfortably tappable; nothing overflows horizontally.

- [ ] **Step 4: Commit**

```bash
git add src/FlashcardViewer.jsx
git commit -m "feat: mobile flashcard layout with swipe navigation"
```

---

### Task 3: Chat sidebar → mobile drawer

**Files:**
- Modify: `src/ChatTab.jsx` (sidebar wrapper, header, message list, composer)

- [ ] **Step 1: Make the persistent rail desktop-only**

On the sidebar container, add `hidden md:flex` so it shows only at `md+`. Keep the existing
`sidebarCollapsed`/`sidebarWidth` behavior for desktop.

- [ ] **Step 2: Add a mobile drawer using the same state**

Add a `md:hidden` hamburger button in the chat header that toggles `sidebarCollapsed`. Render a
mobile drawer that reuses the existing chat list markup:

```jsx
{/* Mobile drawer */}
<div className={`md:hidden fixed inset-0 z-40 ${sidebarCollapsed ? 'pointer-events-none' : ''}`}>
  <div
    className={`absolute inset-0 bg-black/30 transition-opacity ${sidebarCollapsed ? 'opacity-0' : 'opacity-100'}`}
    onClick={() => setSidebarCollapsed(true)}
  />
  <div className={`absolute inset-y-0 left-0 w-72 bg-white shadow-xl transform transition-transform ${sidebarCollapsed ? '-translate-x-full' : 'translate-x-0'}`}>
    {/* render the same chat-list component used in the desktop rail */}
  </div>
</div>
```

Initialize `sidebarCollapsed` to `true` on first mount for `<md` so the drawer starts closed.

- [ ] **Step 3: Reflow message list and composer**

Message list container: `px-2 md:px-6`. Composer wrapper: full width on mobile; reduce model-selector
chrome with `text-[11px]`. Ensure message bubbles use `max-w-[85%] md:max-w-[75%]`.

- [ ] **Step 4: Manually verify at 375px**

Run: `npm run dev`. Hamburger opens/closes the drawer; backdrop closes it; messages and composer fit
with no horizontal scroll.

- [ ] **Step 5: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat: mobile chat drawer and responsive composer"
```

---

### Task 4: Dashboard single-column

**Files:**
- Modify: `src/Dashboard.jsx`

- [ ] **Step 1: Responsive grid + wrapping header**

Course grid container: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4`. Header action row:
`flex flex-wrap gap-2`.

- [ ] **Step 2: Manually verify at 375px** — single column, header wraps, no overflow.

- [ ] **Step 3: Commit**

```bash
git add src/Dashboard.jsx
git commit -m "feat: responsive single-column dashboard on mobile"
```

---

### Task 5: PWA manifest

**Files:**
- Create: `public/manifest.webmanifest`
- Create: `public/icon-192.png`, `public/icon-512.png` (export from existing favicon/logo)
- Modify: `index.html` (add `<link rel="manifest">` + theme-color)

- [ ] **Step 1: Add the manifest**

```json
{
  "name": "CourseMate",
  "short_name": "CourseMate",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#4f46e5",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- [ ] **Step 2: Reference it in `index.html`**

Inside `<head>`:

```html
<link rel="manifest" href="/manifest.webmanifest" />
<meta name="theme-color" content="#4f46e5" />
```

- [ ] **Step 3: Verify installability**

Run: `npm run build && npm run preview`. In Chrome devtools → Application → Manifest, confirm it
loads with icons and no errors; the install prompt is available.

- [ ] **Step 4: Commit**

```bash
git add public/manifest.webmanifest public/icon-192.png public/icon-512.png index.html
git commit -m "feat: add PWA manifest for home-screen install"
```

---

### Task 6: Playwright 375px overflow smoke

**Files:**
- Create: `tests/playwright/mobile_overflow.spec.js` (match the repo's existing Playwright runner style under `tests/playwright/`)

- [ ] **Step 1: Write the test**

For each of `/dashboard`, a course chat, and a flashcard viewer route, set viewport to 375×812 and
assert no horizontal overflow:

```js
// Pseudocode shape — adapt to the repo's existing Playwright auth/setup helpers in tests/playwright/.
test('no horizontal overflow at 375px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const path of ['/dashboard', COURSE_CHAT_PATH, FLASHCARD_PATH]) {
    await page.goto(BASE_URL + path);
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  }
});
```

> Reuse the existing Playwright login/context helpers already present under `tests/playwright/`
> (Google OAuth is handled there); do not reinvent auth.

- [ ] **Step 2: Run it**

Run the repo's Playwright command (see `tests/playwright/`), e.g. against a dev server.
Expected: PASS (no overflow) on all three surfaces after Tasks 2–4.

- [ ] **Step 3: Commit**

```bash
git add tests/playwright/mobile_overflow.spec.js
git commit -m "test: 375px no-horizontal-overflow smoke for key surfaces"
```

---

## Self-Review

- **Spec coverage:** flashcards+swipe (T1–2), chat drawer (T3), dashboard grid (T4), PWA (T5),
  Playwright overflow verification (T6). ✓
- **Surgical:** every change is additive `sm:`/`md:` classes or reuse of existing `sidebarCollapsed`
  state — no desktop-layout rewrite. ✓
- **Anchors over guesses:** plan tells the engineer to reuse existing next/prev handlers, chat-list
  markup, and Playwright auth helpers rather than inventing them. ✓
