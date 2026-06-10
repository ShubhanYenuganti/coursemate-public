-- Migration: 008_feature_roadmap_schema
-- Schema for the 2026-05-31 feature roadmap build (docs/2026-05-31-feature-review-and-build-roadmap.md).
-- Covers: Saved Prompt Library, Per-Course Model Default, and Generate-From-Chat
-- conversation context. Idempotent — safe to re-run.

-- Saved Prompt Library (api/prompts.py): per-user reusable chat prompts.
CREATE TABLE IF NOT EXISTS saved_prompts (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title      TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_saved_prompts_user_created
  ON saved_prompts (user_id, created_at DESC);

-- Per-Course Model Default (api/course.py, api/courses.py): course-level default
-- AI provider/model used to seed the chat model picker. Nullable = no default set.
ALTER TABLE courses
  ADD COLUMN IF NOT EXISTS default_ai_provider TEXT,
  ADD COLUMN IF NOT EXISTS default_ai_model    TEXT;

-- Generate-From-Chat: conversation summary persisted on each generation so the
-- worker can use the chat discussion as a primary source. Nullable for legacy rows.
ALTER TABLE quiz_generations
  ADD COLUMN IF NOT EXISTS conversation_context TEXT;

ALTER TABLE flashcard_generations
  ADD COLUMN IF NOT EXISTS conversation_context TEXT;

ALTER TABLE report_generations
  ADD COLUMN IF NOT EXISTS conversation_context TEXT;
