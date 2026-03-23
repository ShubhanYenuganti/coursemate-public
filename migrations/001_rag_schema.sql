-- Migration 001: Voyage AI RAG schema (consolidated)
-- Run once against Neon DB.
-- Drops and recreates new RAG tables cleanly (no prior state assumed).
-- Does NOT touch existing app tables except to add two new columns.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Drop legacy + prior RAG tables in dependency order
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS material_chunks CASCADE;
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

-- Documents: one row per source file
CREATE TABLE documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_uri   TEXT NOT NULL,
    modality     TEXT NOT NULL DEFAULT 'pdf',
    raw_content  TEXT,
    metadata     JSONB DEFAULT '{}',
    ingested_at  TIMESTAMPTZ DEFAULT now(),
    source_type  TEXT NOT NULL DEFAULT 'general',
    material_id  INTEGER REFERENCES materials(id) ON DELETE CASCADE
);

-- Chunks: parent and child chunks with dual embeddings
CREATE TABLE chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content           TEXT NOT NULL,
    retrieval_type    TEXT NOT NULL DEFAULT 'visual',
    embedding         VECTOR(1024) NOT NULL,
    chunk_index       INT NOT NULL,
    modal_meta        JSONB DEFAULT '{}',
    parent_id         UUID REFERENCES chunks(id),
    is_parent         BOOLEAN NOT NULL DEFAULT false,
    source_type       TEXT NOT NULL DEFAULT 'general',
    course_id         TEXT,
    week              INT,
    problem_id        TEXT,
    related_chunk_ids UUID[] NOT NULL DEFAULT '{}'
);

-- Add new columns to existing app tables (idempotent guards)
ALTER TABLE materials ADD COLUMN IF NOT EXISTS doc_type TEXT NOT NULL DEFAULT 'general';
ALTER TABLE chats     ADD COLUMN IF NOT EXISTS session_uuid UUID NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_embedding vector(1024);

-- Indexes
CREATE INDEX chunks_embedding_idx     ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX chunks_doc_page_type_idx ON chunks (document_id, chunk_index, retrieval_type);
CREATE INDEX chunks_parent_idx        ON chunks (parent_id);
CREATE INDEX chunks_source_type_idx   ON chunks (source_type);
CREATE INDEX chunks_problem_id_idx    ON chunks (problem_id);
CREATE INDEX IF NOT EXISTS idx_messages_embedding
    ON chat_messages USING ivfflat (message_embedding vector_cosine_ops) WITH (lists = 50);
