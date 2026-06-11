# No-API-Key Chat Empty State — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 1.1 (incomplete surfaced feature) + 2.1a (onboarding wall, immediate fix)
**Scope:** Chat composer in `src/ChatTab.jsx`. No backend changes. The deeper "server-funded free tier" is a separate item (`free-tier`).

## Problem

`src/ChatTab.jsx` loads the user's configured providers via `GET /api/user?resource=api_keys`
(around line 1559) and sets `availableModels` to the providers that have a key. The composer's
model selector is rendered only when `availableModels.length > 0` (`src/ChatTab.jsx:3272`). A brand
new user with no key configured therefore sees a fully-rendered chat box with **no model selector
and no explanation** — typing and pressing send silently does nothing useful. This is the single
biggest first-run dead end, and the landing page funnels every new user straight into it.

## Goal

When the user has no usable provider key, the composer:
1. Shows a clear inline banner: "Add an API key in your Profile to start chatting." with a link to
   the Profile page.
2. Disables the send button and the textarea submit, with a tooltip/`title` explaining why.
3. Leaves everything else (chat history, sidebar) usable so the user can still read prior chats.

When at least one key exists, behavior is unchanged.

## Decisions

1. **No backend change.** The `api_keys` resource already returns `{ provider: bool }`; the only
   signal needed (`availableModels.length === 0`) is already computed.
2. **Extract a pure helper** `composerGateState(availableModels)` into `src/utils/` so the
   gate logic is unit-testable with vitest (the repo already has `src/utils/*.test.js`).
3. **Link, don't modal.** The banner links to `/profile`; we do not auto-open a modal — the user
   may be mid-read of an existing chat.
4. **Disable, don't hide, the send button.** Hiding it reproduces the original "silent" problem.
   A visibly-disabled button with a `title` is discoverable.

## The helper

`src/utils/composerGate.js`:

```js
// Pure: decides whether the chat composer can send, and what to tell the user if not.
export function composerGateState(availableModels) {
  const hasKey = Array.isArray(availableModels) && availableModels.length > 0;
  return {
    canSend: hasKey,
    bannerText: hasKey ? null : 'Add an API key in your Profile to start chatting.',
    disabledReason: hasKey ? null : 'Add an API key in your Profile to start chatting.',
  };
}
```

## Wiring (in `src/ChatTab.jsx`)

- Compute `const gate = composerGateState(availableModels);` in the composer component.
- Render the banner above the textarea when `gate.bannerText` is non-null, with a
  `<Link to="/profile">` (the app uses react-router — see `src/App.jsx` routes, `/profile` exists).
- Add `disabled={!gate.canSend || sending}` to the send button and `title={gate.disabledReason}`.
- In the submit handler (`handleSend` / keydown-enter), early-return when `!gate.canSend`.

## Out of scope

- Server-funded free tier / trial credits (separate `free-tier` item).
- Changing the landing-page onboarding copy (tracked under the free-tier item).

## Verification

- vitest unit test for `composerGateState` (both branches).
- Manual / Playwright: load a chat as a user with zero keys → banner visible, send disabled;
  add a key → banner gone, send enabled.
