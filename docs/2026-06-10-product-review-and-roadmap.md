# Product Review & Roadmap — 2026-06-10

A consumer-eyed review of CourseMate's feature surface. All items below are **approved as-is** and ordered by category: incomplete surfaced features first, then consumer-facing improvements, then new feature ideas.

## What CourseMate is

CourseMate is a live (Vercel-hosted) AI study platform: students connect Notion or Google Drive (or upload files directly), the platform indexes materials into a page-level structure ("PageIndex"), and an agentic RAG chat assistant answers questions grounded in those pages with citations. On top of chat it offers async generation of flashcards, quizzes, and reports (SQS + Lambda workers), quiz attempts with LLM grading and history, exports to PDF/Notion/Drive, course sharing with collaborators, a prompt library, pinned responses, image attachments, web search, and multi-provider model switching (Claude/Gemini/GPT — bring-your-own-key). Stack: React/Vite/Tailwind + Python serverless handlers on Vercel + Neon Postgres/pgvector + AWS Lambdas.

The feature surface is broad and mostly real — exports, attempt grading, play mode, archives, and search are all wired end-to-end, and there are essentially no TODO/FIXME stubs in the code. The gaps are in polish, onboarding, and the learning loop rather than vaporware.

---

## 1. Incomplete surfaced features

### 1.1 No-API-key chat path is a silent dead end
The chat composer renders fully, but with no API key configured the model selector silently disappears (`src/ChatTab.jsx:3272`) and there is no guidance. New users hit a chat box that doesn't work with no explanation.
**Fix:** add an empty-state banner ("Add an API key in Profile to start chatting") and disable send with an explanation linking to the Profile page.

### 1.2 Flashcard ratings go nowhere
Ratings are surfaced in the flashcard viewer but stored only in `localStorage` keyed by generation (`src/utils/flashcardRatings.js`) — lost on device switch or cache clear, and never used to schedule review. The rating UI is effectively decorative.
**Fix:** persist ratings server-side per user. (Full spaced-repetition loop is item 2.5 below.)

### 1.3 Invite-by-email only works for existing users
`SharingAccessModal` surfaces "Invite by email address…" but `api/sharing.py` returns 404 "No user found with that email address" for anyone who hasn't signed up. The natural expectation — inviting a classmate by email — errors out, killing the viral loop.
**Fix:** a `pending_invites` table + invite email (or shareable invite link), auto-attaching membership on first Google sign-in with that email.

### 1.4 Notion/Drive sync edge cases are mid-fix
The last five commits are all sync-robustness fixes (stuck job cancellation, reconciling removed files, filtering unsupported Drive files) and the current branch is `fix-notion-drive`. Until merged, deleted/unsupported source files can leave inconsistent material lists.
**Fix:** land and verify the `fix-notion-drive` branch work.

### 1.5 Dead code flagged for removal
`SettingsIcon() { // removed soon` in `src/QuizViewer.jsx:45`.
**Fix:** remove it.

### 1.6 Legacy chunk/vector RAG path still alongside PageIndex
The README calls the old chunk/vector path a fallback. Not consumer-visible, but it's untested surface that can drift.
**Fix:** gate it behind an explicit flag or remove it.

---

## 2. Consumer-facing improvements

### 2.1 The BYOK onboarding wall — biggest conversion killer
The landing page's step 2 is literally "Add your API keys." Students won't get OpenAI/Anthropic keys; most will bounce before seeing value. There is no server-side default key fallback.
**Solution:** (a) immediate — the empty-state fix from 1.1; (b) real fix — a server-funded free tier on a cheap model (Haiku/Flash) with per-user rate limits or trial credits, keeping BYOK as the power-user path.

### 2.2 Mobile experience is essentially absent
`src/ChatTab.jsx` (3,405 lines) contains **zero** responsive breakpoint classes; Dashboard has 2, MaterialsPage has 1. For a student product, phone usage is the default context — especially flashcards, which already have a play mode begging to be a commute feature.
**Solution:** a responsive pass prioritized flashcards → chat → dashboard; collapse the chat sidebar into a drawer (collapse state already exists), add swipe gestures to the card viewer, and consider a PWA manifest for home-screen install.

### 2.3 Long silent waits during retrieval
Eval shows ~9.6s average retrieval latency, and the planner timeout was recently raised to 300s for gpt-5.x models. From the consumer's seat that's a frozen screen.
**Solution:** stream retrieval progress into the UI as status events ("Scanning Lecture 4 structure… fetching pages 10–14…") — the agent loop already knows which tool it's calling; surfacing that turns dead air into perceived intelligence. Converting the planner call to streaming also protects against proxy idle timeouts.

### 2.4 Pending invites for non-users
The full solution to 1.3: `pending_invites` table, invite email or shareable link, auto-attach on first sign-in.

### 2.5 Spaced-repetition flashcard loop
Building on 1.2: persist ratings server-side and build a spaced-repetition queue (FSRS or SM-2) with a "Due today" widget on the dashboard. The single highest-leverage retention feature available — it gives students a reason to return daily.

### 2.6 Sync transparency and freshness
Recent commit history is evidence consumers hit confusing sync states, and the 2-hour EventBridge poll means edits feel stale.
**Solution:** per-file sync status with error text and a per-file retry button in the Materials page, plus migrating to push notifications (Drive Changes API watch channels, Notion webhooks) for near-real-time freshness.

### 2.7 Retrieval recall + user feedback loop
Recall@5 is 0.654 and a Jun 10 session documented the agent missing sections that ChatGPT found with identical sources. The frontier-budget work addresses this; pair it with a consumer-facing feedback affordance (thumbs-down + "it missed something in [material]") so labeled failure cases accumulate for the eval set.

---

## 3. New feature ideas

### 3.1 Study planner / mastery tracking
Quiz attempt data (`quiz_attempts`, per-question correctness, grader feedback) already exists in Postgres but is never aggregated. A "weak topics" view that auto-proposes targeted flashcards/quizzes from missed questions closes the loop between assessment and study — mostly a read-model over existing data.

### 3.2 Notifications for ready generations
Generation is async with frontend polling, so users must keep the tab open. Add email (or web push) "Your quiz is ready" with a deep link — the viewer routes (`/course/:id/quiz/:generationId`) already exist.

### 3.3 Richer ingestion
YouTube lectures, pasted URLs, and Canvas/LMS sync. The provider abstraction (`api/services/providers/`) makes a third provider a natural extension.

### 3.4 Citation jump-to-page
Citations carry page metadata; rendering the source PDF page inline (or deep-linking to it) when a citation is clicked makes groundedness visible and differentiating.

### 3.5 Richer dashboard
`CourseStatsWidget` shows four raw counts (materials/generations/chats/messages). Replace with streaks, due cards, recent quiz scores, and last-synced status.

---

## Suggested sequencing

1. No-key empty state (hours) — 1.1
2. Pending invites (a day) — 1.3 / 2.4
3. Mobile pass on flashcards + chat (days) — 2.2
4. Server-side spaced repetition (the retention flywheel) — 1.2 / 2.5
5. Retrieval-quality work continues in parallel — 2.3 / 2.7
