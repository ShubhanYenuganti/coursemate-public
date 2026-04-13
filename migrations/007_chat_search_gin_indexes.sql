-- Migration: 007_chat_search_gin_indexes
-- GIN indexes for full-text search over chat titles and message content.
-- Required for chat_search endpoint performance at scale (>500 chats).

CREATE INDEX IF NOT EXISTS idx_chats_title_fts
  ON chats USING gin(to_tsvector('english', COALESCE(title, '')));

CREATE INDEX IF NOT EXISTS idx_chat_messages_content_fts
  ON chat_messages USING gin(to_tsvector('english', content));