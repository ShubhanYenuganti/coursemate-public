-- Migration: 004_pinned_messages
-- Creates the pinned_messages table for storing user-pinned AI chat responses.

CREATE TABLE IF NOT EXISTS pinned_messages (
  id                   SERIAL PRIMARY KEY,
  user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  course_id            INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  chat_id              INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  user_message_id      INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  assistant_message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  ai_summary           VARCHAR(300),
  pinned_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
  UNIQUE (user_id, assistant_message_id)
);

CREATE INDEX IF NOT EXISTS idx_pinned_messages_course_user
  ON pinned_messages (course_id, user_id);
