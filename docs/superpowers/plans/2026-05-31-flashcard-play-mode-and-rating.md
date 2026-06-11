# Flashcard Play Mode + Rating — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the dead Play button to an auto-advance study mode, and add a per-card thumbs up/down rating, in `src/FlashcardViewer.jsx`.

**Architecture:** Pure client-side. Play mode is an interval that flips then advances through `displayCards`, stopping at the end. Ratings are per-card state persisted to `localStorage` keyed by generation id (no backend — spaced repetition is explicitly out of scope).

**Tech Stack:** React (`src/FlashcardViewer.jsx`), `localStorage`. No backend changes.

**Spec:** Derived from `docs/2026-05-31-feature-review-and-build-roadmap.md` (P0 row). Note: the roadmap stated a thumb-rating UI already exists — it does **not** (no rating markup in the component). This plan builds it.

---

## Roadmap-vs-reality note

- The Play button (`src/FlashcardViewer.jsx` line ~647) renders with **no `onClick`** — confirmed dead.
- There is **no** existing rating UI in the component — this plan adds it from scratch.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/FlashcardViewer.jsx` | Play interval + rating state/UI + persistence | Modify |
| `src/utils/flashcardRatings.js` | localStorage read/write helpers for ratings | Create |
| `tests/flashcardRatings.test.js` | Unit test for the persistence helpers | Create |

---

## Task 1: Rating persistence helpers (testable, isolated)

**Files:**
- Create: `src/utils/flashcardRatings.js`
- Test: `tests/flashcardRatings.test.js`

> Confirm the test runner first: `cd /Users/shubhan/OneShotCourseMate && rg -n "\"test\"|vitest|jest" package.json`. Use whichever is configured. Steps below assume `vitest`/`jest`-style `expect`.

- [ ] **Step 1: Write the failing test**

```js
import { loadRatings, setRating } from '../src/utils/flashcardRatings';

beforeEach(() => localStorage.clear());

test('setRating then loadRatings round-trips by generation id', () => {
  setRating('gen-42', 3, 'up');
  setRating('gen-42', 7, 'down');
  expect(loadRatings('gen-42')).toEqual({ 3: 'up', 7: 'down' });
});

test('loadRatings returns empty object when none stored', () => {
  expect(loadRatings('gen-99')).toEqual({});
});

test('setRating to null clears a card rating', () => {
  setRating('gen-1', 0, 'up');
  setRating('gen-1', 0, null);
  expect(loadRatings('gen-1')).toEqual({});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shubhan/OneShotCourseMate && npx vitest run tests/flashcardRatings.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helpers**

`src/utils/flashcardRatings.js`:

```js
const KEY = (genId) => `flashcard_ratings_${genId}`;

export function loadRatings(genId) {
  if (!genId) return {};
  try {
    return JSON.parse(localStorage.getItem(KEY(genId)) || '{}');
  } catch {
    return {};
  }
}

export function setRating(genId, index, value) {
  if (!genId) return;
  const ratings = loadRatings(genId);
  if (value == null) {
    delete ratings[index];
  } else {
    ratings[index] = value;
  }
  localStorage.setItem(KEY(genId), JSON.stringify(ratings));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shubhan/OneShotCourseMate && npx vitest run tests/flashcardRatings.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/flashcardRatings.js tests/flashcardRatings.test.js
git commit -m "feat(flashcards): add localStorage rating persistence helpers"
```

---

## Task 2: Per-card rating UI

**Files:**
- Modify: `src/FlashcardViewer.jsx` (import helpers; state near line 165; render near the card body ~line 595; bottom toolbar)

- [ ] **Step 1: Import helpers and add rating state**

At the top import:
```jsx
import { loadRatings, setRating } from './utils/flashcardRatings';
```

Add state near the other `useState` calls (line ~165):
```jsx
const [ratings, setRatings] = useState(() => loadRatings(generationId));
```

Add a handler near `handleFlip` (line ~223):
```jsx
function rateCard(value) {
  const next = ratings[currentIndex] === value ? null : value;
  setRating(generationId, currentIndex, next);
  setRatings((prev) => {
    const copy = { ...prev };
    if (next == null) delete copy[currentIndex]; else copy[currentIndex] = next;
    return copy;
  });
}
```

- [ ] **Step 2: Render the rating buttons**

Place a rating control next to the Prev/Next group in the footer (after the Prev/Next `div`, before Play/Shuffle, around line 643):

```jsx
<div className="flex items-center gap-2">
  <button
    type="button"
    onClick={() => rateCard('up')}
    aria-label="Mark known"
    className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors ${
      ratings[currentIndex] === 'up'
        ? 'border-green-400 text-green-600 bg-green-50'
        : 'border-gray-200 text-gray-400 hover:border-green-400 hover:text-green-600 hover:bg-green-50'
    }`}
  >👍</button>
  <button
    type="button"
    onClick={() => rateCard('down')}
    aria-label="Mark needs review"
    className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors ${
      ratings[currentIndex] === 'down'
        ? 'border-rose-400 text-rose-600 bg-rose-50'
        : 'border-gray-200 text-gray-400 hover:border-rose-400 hover:text-rose-600 hover:bg-rose-50'
    }`}
  >👎</button>
</div>
```

- [ ] **Step 3: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 4: Manual check**

Rate a card 👍, navigate away and back → rating persists. Reload page → rating restored from localStorage.

- [ ] **Step 5: Commit**

```bash
git add src/FlashcardViewer.jsx
git commit -m "feat(flashcards): per-card thumbs rating with persistence"
```

---

## Task 3: Play mode (auto-advance)

**Files:**
- Modify: `src/FlashcardViewer.jsx` (state, an interval effect, the Play button at line ~647)

- [ ] **Step 1: Add playing state and the interval effect**

Add state (line ~165):
```jsx
const [playing, setPlaying] = useState(false);
const PLAY_INTERVAL_MS = 4000;
```

Add an effect (after the existing effects, ~line 181). It reveals the answer, then advances; stops at the last card:
```jsx
useEffect(() => {
  if (!playing) return undefined;
  const tick = setInterval(() => {
    setIsFlipped((flipped) => {
      if (!flipped) return true;           // first show the answer
      // already flipped: advance or stop
      setCurrentIndex((i) => {
        if (i >= total - 1) { setPlaying(false); return i; }
        if (trackProgress) setSeen((prev) => new Set(prev).add(i));
        return i + 1;
      });
      return false;                        // reset flip for the next card
    });
  }, PLAY_INTERVAL_MS);
  return () => clearInterval(tick);
}, [playing, total, trackProgress]);
```

- [ ] **Step 2: Wire the Play button to toggle**

At the Play button (line ~647), add the handler and active state:
```jsx
<button
  type="button"
  onClick={() => setPlaying((p) => !p)}
  aria-label={playing ? 'Pause' : 'Play'}
  className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors ${
    playing
      ? 'border-indigo-400 text-indigo-600 bg-indigo-50'
      : 'border-gray-200 text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50'
  }`}
>
  {playing ? <PauseIcon /> : <PlayIcon />}
</button>
```

Add a minimal `PauseIcon` near `PlayIcon` (line ~103):
```jsx
function PauseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="5" width="4" height="14" rx="1" />
      <rect x="14" y="5" width="4" height="14" rx="1" />
    </svg>
  );
}
```

- [ ] **Step 3: Stop playback when leaving / manual nav**

To avoid fighting the user, stop play on manual navigation. In `goNext` and `goPrev` (lines ~206, ~215), add `setPlaying(false);` at the top of each.

- [ ] **Step 4: Build to verify compile**

Run: `cd /Users/shubhan/OneShotCourseMate && npm run build`
Expected: success.

- [ ] **Step 5: Manual verification**

1. Click Play → card flips to the answer, then advances every ~4s; icon shows Pause and is highlighted.
2. Reaches the last card → playback auto-stops.
3. Clicking Prev/Next mid-play stops playback.

- [ ] **Step 6: Commit**

```bash
git add src/FlashcardViewer.jsx
git commit -m "feat(flashcards): wire Play button to auto-advance study mode"
```

---

## Self-Review Notes

- **Spec coverage:** Play button wired (Task 3) ✓; per-card rating (Tasks 1–2) ✓; persistence without backend (Task 1, localStorage) ✓; spaced repetition intentionally excluded ✓.
- **YAGNI:** ratings are local-only because no consumer (spaced repetition) exists; if a backend consumer is added later, swap `flashcardRatings.js` for an API-backed module — the component only depends on `loadRatings`/`setRating`.
- **Type consistency:** `ratings` is an index→`'up'|'down'` map in both the helper and the component; `playing` toggles consistently; `PLAY_INTERVAL_MS` single source.
- **Soft spot:** test runner (vitest vs jest) — Task 1 Step opens with a confirming grep.
```
