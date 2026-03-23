-- Consolidation migration: chat_messages embeddings + legacy table retirement.
-- Run with: psql "$NEON_DIRECT" -f migrate_to_neon.sql

-- 1. Ensure canonical message embedding column/index exists.
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_embedding vector(1024);
CREATE INDEX IF NOT EXISTS idx_messages_embedding
    ON chat_messages USING ivfflat (message_embedding vector_cosine_ops)
    WITH (lists = 50);

-- 2. Keep web cache schema ready.
CREATE TABLE IF NOT EXISTS web_cache (
    id           SERIAL PRIMARY KEY,
    query_hash   TEXT        NOT NULL UNIQUE,
    url          TEXT        NOT NULL,
    snippet      TEXT        NOT NULL,
    embedding    vector(1024),
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ttl_seconds  INT         NOT NULL DEFAULT 3600
);
CREATE INDEX IF NOT EXISTS idx_web_cache_hash ON web_cache(query_hash);

-- 3. Retire legacy tables after cutover/backfill.
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS material_chunks CASCADE;

-- Verification
SELECT 'messages table dropped' AS check, to_regclass('public.messages') IS NULL AS value;
SELECT 'material_chunks table dropped' AS check, to_regclass('public.material_chunks') IS NULL AS value;
SELECT 'web_cache table exists' AS check, COUNT(*) AS value FROM web_cache;
