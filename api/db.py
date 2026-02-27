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
            min_size=2,
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message_text TEXT NOT NULL,
                ai_response TEXT,
                visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_chat_course_created ON chat_messages(course_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_chat_user_course ON chat_messages(user_id, course_id);
            CREATE INDEX IF NOT EXISTS idx_chat_course_visibility_created ON chat_messages(course_id, visibility, created_at DESC);

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
        """)

        cursor.close()
        print("Database initialized successfully")
