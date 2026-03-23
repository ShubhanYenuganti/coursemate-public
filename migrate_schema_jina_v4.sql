-- Schema migration: Jina v4 + parent-child chunks
-- Run this against the Neon database before deploying the updated Lambda.

-- materials: add semantic doc type
ALTER TABLE materials ADD COLUMN IF NOT EXISTS doc_type VARCHAR(30);
ALTER TABLE materials ADD COLUMN IF NOT EXISTS week INTEGER;

-- material_chunks: parent-child + metadata
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES material_chunks(id) ON DELETE CASCADE;
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS is_parent BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS source_type VARCHAR(30);
-- source_type enum: slide, lecture_note, reading, hw_instruction, hw_solution, quiz, exam, coding_spec, code_file, default
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS week INTEGER;
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS section_title TEXT;
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS position_in_doc DECIMAL(5,4);  -- 0.0–1.0
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS problem_id TEXT;  -- e.g. "hw3_q2"
ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS related_chunk_ids JSONB NOT NULL DEFAULT '[]';

-- embedding stays vector(1024) — Jina output truncated via Matryoshka
-- invalidate existing chunks (different embedding model)
DROP INDEX IF EXISTS idx_chunks_embedding;
DELETE FROM material_chunks;
UPDATE material_embed_jobs SET status='pending', started_at=NULL, completed_at=NULL,
    error_message=NULL, chunks_created=NULL;
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON material_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- new indices for parent-child queries
CREATE INDEX IF NOT EXISTS idx_chunks_parent_id ON material_chunks(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chunks_is_parent ON material_chunks(is_parent, course_id);
CREATE INDEX IF NOT EXISTS idx_chunks_problem_id ON material_chunks(problem_id) WHERE problem_id IS NOT NULL;
