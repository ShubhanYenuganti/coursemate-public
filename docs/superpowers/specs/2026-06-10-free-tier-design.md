# Server-Funded Free Tier — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 2.1b (the real fix for the BYOK onboarding wall)
**Scope:** New `free_tier_usage` table, pure budget logic, credential resolution in the chat send path (`api/chat.py` / `api/llm.py`), `src/ChatTab.jsx` + `src/LandingPage.jsx` copy. Builds on the `no-api-key-chat-empty-state` item (which is the interim gate).

## Problem

The landing page's onboarding step 2 is "Add your API keys." Students rarely hold OpenAI/Anthropic
keys, so most bounce before seeing value. The interim fix (item 1.1) explains the wall; this item
removes it for first-time users by funding a small daily allowance on a cheap model.

## Goal

A signed-in user with **no** API key can send a limited number of chat messages per day on a
server-funded cheap model (e.g. Gemini Flash or Claude Haiku), with a visible remaining-quota
indicator. Power users still add their own key for unlimited use and model choice.

## Decisions

1. **Per-user daily cap, server-held key.** A single server credential (new env var, e.g.
   `FREE_TIER_GEMINI_KEY` or reuse an existing server key) drives a fixed cheap model. Cap is a
   constant (e.g. `FREE_TIER_DAILY_MESSAGES = 10`), counted per UTC day in `free_tier_usage`.
2. **Free tier only when the user has zero keys.** If the user has any provider key, we never spend
   server budget — their key is used as today. This keeps cost bounded and predictable.
3. **Pure budget function.** `free_tier_decision(used_today, has_own_key, cap)` →
   `{ allowed, remaining, reason }` lives in a small module and is the TDD core. The DB only supplies
   `used_today`.
4. **Count on successful send.** Increment usage after a message is accepted for generation, not on
   failed/aborted requests, so users aren't charged for errors.
5. **Cheap model is fixed and not user-selectable on the free tier.** Model choice is a paid-key
   feature; the free tier always uses the configured cheap model id.
6. **Abuse guard is the daily cap + auth.** No payment/credits system in v1 (YAGNI); the cap bounds
   spend. A future credits/billing item can layer on the same table.

## Schema — `migrations/013_free_tier_usage.sql`

```sql
CREATE TABLE IF NOT EXISTS free_tier_usage (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date DATE    NOT NULL,
    count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, usage_date)
);
```

## Budget logic — `api/services/free_tier.py`

```python
FREE_TIER_DAILY_MESSAGES = 10
FREE_TIER_PROVIDER = "gemini"
FREE_TIER_MODEL_ID = "gemini-3-flash-preview"   # cheap, fast

def free_tier_decision(used_today: int, has_own_key: bool, cap: int = FREE_TIER_DAILY_MESSAGES) -> dict:
    if has_own_key:
        return {"allowed": True, "remaining": None, "reason": "own_key", "use_free_tier": False}
    remaining = max(0, cap - used_today)
    if remaining <= 0:
        return {"allowed": False, "remaining": 0, "reason": "free_tier_exhausted", "use_free_tier": True}
    return {"allowed": True, "remaining": remaining, "reason": "free_tier", "use_free_tier": True}
```

## Send-path integration

In the chat send handler, before invoking the model:
1. Determine `has_own_key` from the existing api-keys lookup.
2. Read `used_today` from `free_tier_usage` for `(user, today)`.
3. `decision = free_tier_decision(used_today, has_own_key)`.
4. If `not decision["allowed"]` → return a clear 429-style payload the UI renders ("You've used today's
   free messages — add an API key in Profile for unlimited chat").
5. If `decision["use_free_tier"]` → use the server free-tier key + `FREE_TIER_MODEL_ID`; otherwise use
   the user's key/model as today.
6. On a successful send, `UPSERT free_tier_usage` incrementing `count` (only when `use_free_tier`).

## Frontend

- `src/ChatTab.jsx`: when on the free tier, show "N free messages left today" near the composer; on
  exhaustion show the upgrade prompt linking to `/profile`. Reuse the `no-api-key` banner component
  for the exhausted/zero-key states.
- `src/LandingPage.jsx`: change step 2 copy from "Add your API keys" to "Start chatting free — add a
  key later for unlimited use."

## Verification

- pytest: `free_tier_decision` table — own key (bypass), under cap (allowed + remaining), at/over cap
  (blocked). Usage increment is idempotent per day (upsert).
- Manual: brand-new user with no key sends messages, sees the counter decrement, hits the cap and
  gets the upgrade prompt; adding a key removes the limit.
