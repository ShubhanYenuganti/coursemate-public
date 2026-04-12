-- Migration: 006_chat_messages_summary
-- Short phrase from the LLM for pin previews and related UI (nullable for legacy rows).

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS summary TEXT;
