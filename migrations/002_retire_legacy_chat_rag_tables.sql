-- Migration 002: retire legacy conversation/retrieval tables after cutover.
-- Preconditions:
--   1) No runtime reads/writes depend on messages/material_chunks.
--   2) chat_messages.message_embedding backfill completed.

DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS material_chunks CASCADE;
