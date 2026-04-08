import os
from contextlib import contextmanager

import psycopg


@contextmanager
def get_db():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError('DATABASE_URL environment variable is not set')

    conn = psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
