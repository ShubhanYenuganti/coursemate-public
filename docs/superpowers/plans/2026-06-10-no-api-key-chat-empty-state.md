# No-API-Key Chat Empty State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user has no provider API key, the chat composer shows an explanatory banner linking to Profile and disables send, instead of silently hiding the model selector.

**Architecture:** Extract a pure `composerGateState(availableModels)` helper (unit-tested with vitest), then wire it into the composer in `src/ChatTab.jsx` to drive a banner + disabled send button. No backend changes.

**Tech Stack:** React + Vite, react-router (`Link`), vitest.

**Spec:** `docs/superpowers/specs/2026-06-10-no-api-key-chat-empty-state-design.md`

---

### Task 1: Pure composer-gate helper

**Files:**
- Create: `src/utils/composerGate.js`
- Test: `src/utils/composerGate.test.js`

- [ ] **Step 1: Write the failing test**

```js
import { describe, it, expect } from 'vitest';
import { composerGateState } from './composerGate';

describe('composerGateState', () => {
  it('allows sending when at least one provider key exists', () => {
    const gate = composerGateState(['openai']);
    expect(gate.canSend).toBe(true);
    expect(gate.bannerText).toBeNull();
  });

  it('blocks sending and explains when no keys exist', () => {
    const gate = composerGateState([]);
    expect(gate.canSend).toBe(false);
    expect(gate.bannerText).toMatch(/Profile/);
    expect(gate.disabledReason).toMatch(/Profile/);
  });

  it('treats a non-array (still loading) as no keys', () => {
    const gate = composerGateState(undefined);
    expect(gate.canSend).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/utils/composerGate.test.js`
Expected: FAIL — cannot resolve `./composerGate`.

- [ ] **Step 3: Write minimal implementation**

```js
// Pure: decides whether the chat composer can send, and what to tell the user if not.
export function composerGateState(availableModels) {
  const hasKey = Array.isArray(availableModels) && availableModels.length > 0;
  const msg = 'Add an API key in your Profile to start chatting.';
  return {
    canSend: hasKey,
    bannerText: hasKey ? null : msg,
    disabledReason: hasKey ? null : msg,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/utils/composerGate.test.js`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/utils/composerGate.js src/utils/composerGate.test.js
git commit -m "feat: add composerGateState helper for no-key chat gating"
```

---

### Task 2: Render the empty-state banner in the composer

**Files:**
- Modify: `src/ChatTab.jsx` (composer component containing the model selector near line 3260–3300; import section at top)

- [ ] **Step 1: Import the helper and react-router Link**

At the top of `src/ChatTab.jsx`, add (next to existing imports):

```jsx
import { Link } from 'react-router-dom';
import { composerGateState } from './utils/composerGate';
```

If `react-router-dom` is already imported, add only `composerGate`. Verify the existing import style — `src/App.jsx` uses `react-router-dom`.

- [ ] **Step 2: Compute the gate where `availableModels` is in scope**

In the composer component (the one rendering the `availableModels.length > 0` block at line ~3272), add near the top of the component body:

```jsx
const gate = composerGateState(availableModels);
```

- [ ] **Step 3: Render the banner above the textarea**

Immediately above the composer's input row (the `<div className="flex items-center justify-end gap-1 ...">` at ~line 3260), add:

```jsx
{gate.bannerText && (
  <div className="mx-3 mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
    {gate.bannerText}{' '}
    <Link to="/profile" className="font-medium text-amber-900 underline hover:text-amber-950">
      Open Profile
    </Link>
  </div>
)}
```

- [ ] **Step 4: Manually verify the banner renders**

Run: `npm run dev`, open a course chat as a user with no API keys configured.
Expected: amber banner appears above the composer with an "Open Profile" link; clicking navigates to `/profile`.

- [ ] **Step 5: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat: show no-API-key banner above chat composer"
```

---

### Task 3: Disable send when gated

**Files:**
- Modify: `src/ChatTab.jsx` (send button + submit handler)

- [ ] **Step 1: Guard the submit handler**

Find the function that sends a message (the handler invoked by the send button and by Enter — search for `setSending(true)`). At the very top of that function body add:

```jsx
if (!gate.canSend) return;
```

- [ ] **Step 2: Disable the send button with an explanatory title**

On the send `<button>` (the primary submit control in the composer), add/extend:

```jsx
disabled={!gate.canSend || sending}
title={gate.disabledReason || undefined}
```

Ensure the existing `disabled` condition (likely `sending` or empty-input) is merged, not replaced.

- [ ] **Step 3: Guard the Enter-to-send keydown**

In the textarea `onKeyDown` handler (search for `key === 'Enter'`), add `gate.canSend &&` to the condition that triggers send, e.g.:

```jsx
if (e.key === 'Enter' && !e.shiftKey && gate.canSend) {
  e.preventDefault();
  handleSend();
}
```

- [ ] **Step 4: Manually verify**

Run: `npm run dev`. As a no-key user: send button is greyed and shows the tooltip on hover; pressing Enter does nothing. Add a key in Profile, reload → send works and banner is gone.

- [ ] **Step 5: Commit**

```bash
git add src/ChatTab.jsx
git commit -m "feat: disable chat send when no API key is configured"
```

---

## Self-Review

- **Spec coverage:** banner (Task 2), disabled send + tooltip (Task 3), pure testable helper (Task 1), unchanged behavior when a key exists (helper `canSend=true` path). ✓
- **Type consistency:** `composerGateState` returns `{ canSend, bannerText, disabledReason }` used identically in Tasks 2–3. ✓
- **No placeholders:** all code shown. The only lookup left to the engineer is the exact name of the send handler/keydown — instructions give the search anchors (`setSending(true)`, `key === 'Enter'`). ✓
