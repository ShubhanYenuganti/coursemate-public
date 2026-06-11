# Remove Dead `SettingsIcon` in QuizViewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the unused `SettingsIcon` component (flagged `// removed soon`) from `src/QuizViewer.jsx`.

**Architecture:** Pure deletion. Verified there are zero references to `SettingsIcon` anywhere in `src/` — only the definition at `src/QuizViewer.jsx:45` exists.

**Tech Stack:** React + Vite, ESLint.

**Spec:** None — trivial dead-code removal, no architectural decisions.

---

### Task 1: Delete the component and prove nothing breaks

**Files:**
- Modify: `src/QuizViewer.jsx:45-53` (remove the `SettingsIcon` function)

- [ ] **Step 1: Confirm zero references (guard against accidental breakage)**

Run: `rg -n "SettingsIcon" src`
Expected: exactly one line — the definition at `src/QuizViewer.jsx:45`. If any other line appears, STOP and reassess; the component is in use.

- [ ] **Step 2: Delete the function**

Remove this entire block from `src/QuizViewer.jsx` (lines 45–53):

```jsx
function SettingsIcon() { // removed soon
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
```

- [ ] **Step 3: Lint + build to verify no dangling reference**

Run: `npx eslint src/QuizViewer.jsx && npm run build`
Expected: no errors, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/QuizViewer.jsx
git commit -m "chore: remove unused SettingsIcon from QuizViewer"
```

---

## Self-Review

- **Spec coverage:** the one roadmap requirement (1.5 remove dead code) is the whole plan. ✓
- **No placeholders:** exact block to delete is shown verbatim. ✓
- **Safety:** Step 1 reference-check prevents deleting something secretly in use. ✓
