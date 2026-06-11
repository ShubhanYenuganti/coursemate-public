# Roadmap Execution Index — 2026-06-10

Priority-ordered execution index for [`docs/2026-06-10-product-review-and-roadmap.md`](../../2026-06-10-product-review-and-roadmap.md). The roadmap's 18 entries collapse to **16 work items** because the roadmap itself pairs three of them (1.3+2.4, 1.2+2.5, and folds 2.1a into 1.1).

Each item links its design spec (`docs/superpowers/specs/`) and execution plan (`docs/superpowers/plans/`). Two trivial items are plan-only (no architectural decisions to capture).

| # | Priority | Roadmap item(s) | Work item | Spec | Plan |
|---|----------|-----------------|-----------|------|------|
| 1 | P0 | 1.1, 2.1a | No-API-key chat empty state | `specs/2026-06-10-no-api-key-chat-empty-state-design.md` | `plans/2026-06-10-no-api-key-chat-empty-state.md` |
| 2 | P0 | 1.5 | Remove dead `SettingsIcon` in QuizViewer | — | `plans/2026-06-10-remove-quizviewer-dead-icon.md` |
| 3 | P1 | 1.3, 2.4 | Pending invites for non-users | `specs/2026-06-10-pending-invites-design.md` | `plans/2026-06-10-pending-invites.md` |
| 4 | P1 | 1.2, 2.5 | Server-side ratings + spaced repetition | `specs/2026-06-10-spaced-repetition-design.md` | `plans/2026-06-10-spaced-repetition.md` |
| 5 | P1 | 1.6 | Gate/remove legacy chunk-vector RAG path | `specs/2026-06-10-legacy-rag-retirement-design.md` | `plans/2026-06-10-legacy-rag-retirement.md` |
| 6 | P1 | 1.4 | Verify & land `fix-notion-drive` | — | `plans/2026-06-10-land-fix-notion-drive.md` |
| 7 | P2 | 2.2 | Mobile responsive pass | `specs/2026-06-10-mobile-responsive-design.md` | `plans/2026-06-10-mobile-responsive.md` |
| 8 | P2 | 2.3 | Streaming retrieval progress | `specs/2026-06-10-streaming-retrieval-progress-design.md` | `plans/2026-06-10-streaming-retrieval-progress.md` |
| 9 | P2 | 2.7 | Retrieval feedback loop | `specs/2026-06-10-retrieval-feedback-design.md` | `plans/2026-06-10-retrieval-feedback.md` |
| 10 | P2 | 2.1b | Server-funded free tier | `specs/2026-06-10-free-tier-design.md` | `plans/2026-06-10-free-tier.md` |
| 11 | P3 | 2.6 | Sync transparency + push freshness | `specs/2026-06-10-sync-transparency-design.md` | `plans/2026-06-10-sync-transparency.md` |
| 12 | P3 | 3.2 | Generation-ready notifications | `specs/2026-06-10-generation-notifications-design.md` | `plans/2026-06-10-generation-notifications.md` |
| 13 | P3 | 3.1 | Study planner / mastery tracking | `specs/2026-06-10-mastery-tracking-design.md` | `plans/2026-06-10-mastery-tracking.md` |
| 14 | P3 | 3.4 | Citation jump-to-page | `specs/2026-06-10-citation-jump-to-page-design.md` | `plans/2026-06-10-citation-jump-to-page.md` |
| 15 | P3 | 3.5 | Richer dashboard | `specs/2026-06-10-richer-dashboard-design.md` | `plans/2026-06-10-richer-dashboard.md` |
| 16 | P4 | 3.3 | Richer ingestion (YouTube/URL/LMS) | `specs/2026-06-10-richer-ingestion-design.md` | `plans/2026-06-10-richer-ingestion.md` |

## Sequencing rationale

- **P0** — hours of work, unblock new-user onboarding and remove flagged dead code.
- **P1** — the incomplete surfaced features plus the retention flywheel (spaced repetition). Migration-numbering order if run together: invites → `010`, ratings → `011`.
- **P2** — consumer polish that lifts the daily experience (mobile, perceived latency, retrieval quality, free-tier conversion).
- **P3** — engagement and freshness features that build on existing data/routes.
- **P4** — largest surface; new ingestion providers.

## Migration numbering

The repo is at `migrations/009_page_token_counts.sql`. New migrations introduced by these plans, in priority order:

- `010_pending_invites.sql` (item 3)
- `011_flashcard_reviews.sql` (item 4)
- `012_retrieval_feedback.sql` (item 9)
- `013_free_tier_usage.sql` (item 10)
- `014_notification_jobs.sql` (item 12)

Renumber if items are executed out of order.
