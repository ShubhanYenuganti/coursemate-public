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
        """)

        cursor.close()
        print("Database initialized successfully")
