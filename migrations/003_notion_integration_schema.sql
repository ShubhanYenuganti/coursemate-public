-- Migration 003: Notion integration + selection persistence schema
-- Run with:
--   psql "$DATABASE_URL" -f migrations/003_notion_integration_schema.sql

BEGIN;

-- D2: OAuth-backed user integrations (provider-agnostic).
CREATE TABLE IF NOT EXISTS user_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    encrypted_token TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, provider)
);

-- D3: Sticky export targets per user/course/provider/generation type.
CREATE TABLE IF NOT EXISTS course_export_targets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    generation_type VARCHAR(30) NOT NULL,
    external_target_id TEXT NOT NULL,
    external_target_title TEXT,
    external_target_type VARCHAR(20),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, provider, generation_type)
);

-- D8: Source points watched by integration pollers.
CREATE TABLE IF NOT EXISTS integration_source_points (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    external_id TEXT NOT NULL,
    external_title TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, provider, external_id)
);

-- D9: Per-user/per-context material selection persistence.
CREATE TABLE IF NOT EXISTS material_selections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    context VARCHAR(30) NOT NULL,
    provider VARCHAR(50),
    selected BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, material_id, context)
);

-- Materials sync tracking fields for provider-backed content.
ALTER TABLE materials ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE materials ADD COLUMN IF NOT EXISTS external_last_edited TEXT;

COMMIT;
