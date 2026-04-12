## Context

`ChatTab.jsx` is a 2356-line self-contained component with all chat logic, state, and sub-components inline. AI message bubbles (`MessageBubble`) currently render thumbs-up/down action buttons that have no functionality beyond UI. Pins will be purely client-side, stored in `localStorage` keyed by `course_id`, which avoids any backend work while still persisting across page refreshes.

The existing `switchBanner` pattern (a centered toast with `absolute top-3 left-1/2 -translate-x-1/2`) is the established way to show transient feedback — the pin toast will reuse the same visual approach.

## Goals / Non-Goals

**Goals:**
- Replace thumbs-up/down with a single pin icon on AI responses
- Show a brief "Saving…" toast on pin (mirrors existing `switchBanner` UX)
- Persist pins to `localStorage` under key `pins_<course_id>`
- Render a `PinsPanel` section below the chat box listing all saved pins
- Each pin row is expandable, showing the user prompt + AI reply as styled chat bubbles
- Chevron rotates up/down to indicate open/closed state

**Non-Goals:**
- No backend persistence — pins are localStorage only for this change
- No pin deletion UI (can be a follow-up)
- No AI-generated summaries (summary derived from first 4–5 words of the AI reply)
- No cross-course pin sharing

## Decisions

**Decision 1: localStorage vs backend storage**
localStorage was chosen because it requires zero API changes and zero migration risk. The feature can be promoted to backend persistence in a follow-up once UX is validated. Alternatives: a new `/api/pin` endpoint would add latency and complexity for what is initially a personal bookmark.

**Decision 2: Summary generation strategy**
The 4–5 word summary is derived by taking the first sentence (or first 5 words) of the AI response text, truncated with an ellipsis. This avoids an extra LLM call and is always available synchronously. Alternative: use the chat title — but that reflects the full conversation, not the specific pinned message.

**Decision 3: PinsPanel placement**
The Pins panel sits below the main chat `div` inside the right-hand column (same flex column as the input bar and `SourcesPanel`). This keeps the chat area clean and the pins discoverable without a separate route. Alternative: a sidebar section — but pins are per-message, not per-conversation, making a bottom panel more natural.

**Decision 4: Reuse `MessageBubble` for pin card rendering**
Pin cards render the user message and AI reply using the same `MessageBubble` component to maintain visual consistency. The `onCiteClick`, `onRegenerate`, and edit props are omitted (passed as `null`) to keep pin cards read-only.

## Risks / Trade-offs

- `localStorage` has a ~5 MB limit across all keys. Many pinned responses with long content could approach this. → Mitigation: serialize only `{ id, chat_id, chatTitle, modelLabel, summary, pinnedAt, userContent, aiContent }` — strip `tool_trace` and other heavy fields.
- Pins are lost if the user clears browser storage. → Acceptable for MVP; backend persistence is the follow-up.
- If the chat title changes after pinning, the stored title becomes stale. → Store the title at pin time; no live sync needed.

## Open Questions

- Should there be a maximum pin count per course? (Suggested: 50, soft limit with no enforcement for now)
- Should pinning the same message a second time un-pin it (toggle), or silently no-op? (Suggested: toggle with "Removed pin" toast)
