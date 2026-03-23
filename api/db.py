"""
Database connection with connection pooling and schema management.
"""
import os
import psycopg
from psycopg_pool import ConnectionPool
from contextlib import contextmanager

_pool = None


def _get_pool():
    """Get or create the connection pool (lazy singleton)."""
    global _pool
    if _pool is None:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        _pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": psycopg.rows.dict_row},
        )
    return _pool


@contextmanager
def get_db():
    """Context manager for database connections from the pool."""
    pool = _get_pool()
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;

            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                google_id VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                email_verified BOOLEAN DEFAULT FALSE,
                name VARCHAR(255),
                given_name VARCHAR(255),
                family_name VARCHAR(255),
                picture TEXT,
                locale VARCHAR(10),
                address TEXT,
                google_access_token TEXT,
                google_refresh_token TEXT,
                google_id_token TEXT,
                token_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                username TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                session_token VARCHAR(128) UNIQUE NOT NULL,
                google_id VARCHAR(255) NOT NULL REFERENCES users(google_id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                revoked BOOLEAN DEFAULT FALSE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
            CREATE INDEX IF NOT EXISTS idx_sessions_google_id ON sessions(google_id);

            CREATE TABLE IF NOT EXISTS courses (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                material_ids JSONB NOT NULL DEFAULT '[]',
                co_creator_ids JSONB NOT NULL DEFAULT '[]',
                primary_creator INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                visibility VARCHAR(20) NOT NULL DEFAULT 'private',
                tags JSONB NOT NULL DEFAULT '[]',
                cover_image_url TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS materials (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                file_url TEXT NOT NULL,
                file_type VARCHAR(50),
                source_type VARCHAR(20) NOT NULL DEFAULT 'upload',
                uploaded_by INTEGER NOT NULL,
                course_id INTEGER,
                visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private')),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_materials_course_visibility ON materials(course_id, visibility);
            CREATE INDEX IF NOT EXISTS idx_materials_uploader_visibility ON materials(course_id, uploaded_by, visibility);

            CREATE TABLE IF NOT EXISTS course_members (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL CHECK (role IN ('owner','admin','creator')),
                invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP,
                UNIQUE(course_id, user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_course_members_course_id ON course_members(course_id);
            CREATE INDEX IF NOT EXISTS idx_course_members_user_id ON course_members(user_id);
            CREATE INDEX IF NOT EXISTS idx_course_members_course_role ON course_members(course_id, role);

            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(500) NOT NULL,
                visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public', 'private')),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP,
                message_count INTEGER NOT NULL DEFAULT 0,
                is_archived BOOLEAN NOT NULL DEFAULT FALSE
            );

            CREATE INDEX IF NOT EXISTS idx_chats_course_updated
                ON chats(course_id, updated_at DESC)
                WHERE is_archived = FALSE;

            CREATE INDEX IF NOT EXISTS idx_chats_user_course
                ON chats(user_id, course_id, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_chats_title_search
                ON chats USING GIN (to_tsvector('english', title));

            CREATE INDEX IF NOT EXISTS idx_chats_course_visibility
                ON chats(course_id, visibility, updated_at DESC);

            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                parent_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                ai_provider VARCHAR(20) CHECK (ai_provider IN ('gemini', 'openai', 'claude')),
                ai_model VARCHAR(100),
                temperature DECIMAL(3,2) CHECK (temperature >= 0 AND temperature <= 2),
                max_tokens INTEGER CHECK (max_tokens > 0),
                context_material_ids JSONB NOT NULL DEFAULT '[]',
                retrieved_chunk_ids JSONB DEFAULT '[]',
                context_token_count INTEGER,
                response_token_count INTEGER,
                response_time_ms INTEGER,
                finish_reason VARCHAR(50),
                message_index INTEGER NOT NULL,
                is_edited BOOLEAN NOT NULL DEFAULT FALSE,
                edited_at TIMESTAMP,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, message_index)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat_index
                ON chat_messages(chat_id, message_index)
                WHERE is_deleted = FALSE;

            CREATE INDEX IF NOT EXISTS idx_messages_chat_content_search
                ON chat_messages USING GIN (to_tsvector('english', content))
                WHERE is_deleted = FALSE;

            CREATE INDEX IF NOT EXISTS idx_messages_course_content_search
                ON chat_messages(course_id)
                INCLUDE (chat_id, content, created_at)
                WHERE is_deleted = FALSE;

            CREATE INDEX IF NOT EXISTS idx_messages_content_fulltext
                ON chat_messages USING GIN (to_tsvector('english', content))
                WHERE is_deleted = FALSE;

            CREATE INDEX IF NOT EXISTS idx_messages_user_course
                ON chat_messages(user_id, course_id, created_at DESC)
                WHERE is_deleted = FALSE;

            CREATE INDEX IF NOT EXISTS idx_messages_materials
                ON chat_messages USING GIN (context_material_ids)
                WHERE jsonb_array_length(context_material_ids) > 0;

            CREATE INDEX IF NOT EXISTS idx_messages_created
                ON chat_messages(created_at DESC);

            CREATE TABLE IF NOT EXISTS chat_material_usage (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                first_used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER NOT NULL DEFAULT 1,
                UNIQUE(chat_id, material_id)
            );

            CREATE INDEX IF NOT EXISTS idx_usage_chat ON chat_material_usage(chat_id);
            CREATE INDEX IF NOT EXISTS idx_usage_material ON chat_material_usage(material_id);

            CREATE OR REPLACE FUNCTION update_chat_on_message()
            RETURNS TRIGGER AS $$
            BEGIN
                UPDATE chats
                SET
                    updated_at = NEW.created_at,
                    last_message_at = NEW.created_at,
                    message_count = message_count + 1
                WHERE id = NEW.chat_id;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trigger_update_chat_on_message ON chat_messages;
            CREATE TRIGGER trigger_update_chat_on_message
                AFTER INSERT ON chat_messages
                FOR EACH ROW
                EXECUTE FUNCTION update_chat_on_message();

            CREATE OR REPLACE FUNCTION track_material_usage()
            RETURNS TRIGGER AS $$
            DECLARE
                material_id_val INTEGER;
            BEGIN
                IF jsonb_array_length(NEW.context_material_ids) > 0 THEN
                    FOR material_id_val IN
                        SELECT jsonb_array_elements_text(NEW.context_material_ids)::INTEGER
                    LOOP
                        INSERT INTO chat_material_usage (chat_id, material_id)
                        VALUES (NEW.chat_id, material_id_val)
                        ON CONFLICT (chat_id, material_id)
                        DO UPDATE SET
                            last_used_at = CURRENT_TIMESTAMP,
                            usage_count = chat_material_usage.usage_count + 1;
                    END LOOP;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trigger_track_material_usage ON chat_messages;
            CREATE TRIGGER trigger_track_material_usage
                AFTER INSERT ON chat_messages
                FOR EACH ROW
                EXECUTE FUNCTION track_material_usage();

            CREATE TABLE IF NOT EXISTS material_generations (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                generated_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                generation_type VARCHAR(50),
                visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_generations_course_visibility ON material_generations(course_id, visibility);
            CREATE INDEX IF NOT EXISTS idx_generations_creator_course_visibility ON material_generations(generated_by, course_id, visibility);

            CREATE TABLE IF NOT EXISTS user_api_keys (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider      VARCHAR(20) NOT NULL CHECK (provider IN ('gemini', 'openai', 'claude')),
                encrypted_key TEXT        NOT NULL,
                created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, provider)
            );

            CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON user_api_keys(user_id);

            CREATE TABLE IF NOT EXISTS material_chunks (
                id              SERIAL PRIMARY KEY,
                material_id     INTEGER      NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                course_id       INTEGER      NOT NULL REFERENCES courses(id)   ON DELETE CASCADE,
                chunk_index     INTEGER      NOT NULL,
                chunk_text      TEXT         NOT NULL,
                chunk_type      VARCHAR(20)  NOT NULL DEFAULT 'paragraph',
                page_number     INTEGER,
                token_count     INTEGER      NOT NULL,
                embedding       vector(1024) NOT NULL,
                model_name      VARCHAR(100) NOT NULL DEFAULT 'cohere-embed-english-v3.0',
                created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(material_id, chunk_index)
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_material_id ON material_chunks(material_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_course_id   ON material_chunks(course_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON material_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);

            CREATE TABLE IF NOT EXISTS material_embed_jobs (
                id              SERIAL PRIMARY KEY,
                material_id     INTEGER      NOT NULL REFERENCES materials(id) ON DELETE CASCADE UNIQUE,
                status          VARCHAR(20)  NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'processing', 'done', 'failed', 'skipped')),
                chunks_created  INTEGER,
                error_message   TEXT,
                started_at      TIMESTAMP,
                completed_at    TIMESTAMP,
                created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_embed_jobs_status      ON material_embed_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_embed_jobs_material_id ON material_embed_jobs(material_id);
        """)

        # RAG schema: documents, chunks, chat_sessions, messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_uri   TEXT NOT NULL,
                modality     TEXT NOT NULL DEFAULT 'pdf',
                raw_content  TEXT,
                metadata     JSONB DEFAULT '{}',
                ingested_at  TIMESTAMPTZ DEFAULT now(),
                source_type  TEXT NOT NULL DEFAULT 'general',
                material_id  INTEGER REFERENCES materials(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chunks (
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

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id      UUID,
                created_at   TIMESTAMPTZ DEFAULT now(),
                session_meta JSONB DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id     UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role           TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
                content        TEXT NOT NULL,
                embedding      VECTOR(1024),
                tool_calls     JSONB DEFAULT '[]',
                grounding_refs JSONB DEFAULT '[]',
                created_at     TIMESTAMPTZ DEFAULT now()
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);")
        cursor.execute("CREATE INDEX IF NOT EXISTS chunks_doc_page_type_idx ON chunks (document_id, chunk_index, retrieval_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS chunks_parent_idx ON chunks (parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS chunks_source_type_idx ON chunks (source_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS chunks_problem_id_idx ON chunks (problem_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS messages_session_idx ON messages (session_id, created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS messages_embedding_idx ON messages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);")

        # Add new columns to existing tables (idempotent)
        cursor.execute("ALTER TABLE materials ADD COLUMN IF NOT EXISTS doc_type TEXT NOT NULL DEFAULT 'general';")
        cursor.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS session_uuid UUID NOT NULL DEFAULT gen_random_uuid();")

        # Phase 1 migration: message embeddings for conversation grounding (Phase 2)
        cursor.execute("""
            ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_embedding vector(1024);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_embedding
                ON chat_messages USING ivfflat (message_embedding vector_cosine_ops)
                WITH (lists = 50);
        """)

        # Phase 1 migration: web search cache (Phase 2)
        cursor.execute("""
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
        """)

        cursor.close()
        print("Database initialized successfully")
