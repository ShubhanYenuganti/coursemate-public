-- Phase 1 Schema Migration: vector(384) → vector(1024) + Phase 2 prep columns
-- Run with: psql "$NEON_DIRECT" -f migrate_to_neon.sql

-- 1. Drop old 384D IVFFlat index
DROP INDEX IF EXISTS idx_chunks_embedding;

-- 2. Change embedding dimension (destructive — existing chunks will be wiped below)
ALTER TABLE material_chunks ALTER COLUMN embedding TYPE vector(1024);

-- 3. Recreate IVFFlat index at new dimension
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON material_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 4. Wipe existing 384D chunks + reset embed jobs for re-ingestion
DELETE FROM material_chunks;
UPDATE material_embed_jobs
    SET status         = 'pending',
        started_at     = NULL,
        completed_at   = NULL,
        error_message  = NULL,
        chunks_created = NULL;

-- 5. Phase 2 prep: message embeddings for conversation grounding
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_embedding vector(1024);
CREATE INDEX IF NOT EXISTS idx_messages_embedding
    ON chat_messages USING ivfflat (message_embedding vector_cosine_ops)
    WITH (lists = 50);

-- 6. Phase 2 prep: web search cache
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

-- Verification
SELECT 'material_chunks embedding dim' AS check,
       atttypmod - 1 AS dimension
FROM   pg_attribute
WHERE  attrelid = 'material_chunks'::regclass AND attname = 'embedding';

SELECT 'material_chunks rows (should be 0)' AS check, COUNT(*) AS value FROM material_chunks;
SELECT 'embed_jobs reset to pending' AS check, COUNT(*) AS value FROM material_embed_jobs WHERE status = 'pending';
SELECT 'web_cache table exists' AS check, COUNT(*) AS value FROM web_cache;
