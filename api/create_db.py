"""
Create the application database on the server if it doesn't exist.
Run this once before init_db.py when using a new RDS instance (the default
'postgres' database exists; your app database may not).

    cd api && python create_db.py
"""
import os
import sys
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
import psycopg


def main():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set!")
        print("Set it in .env or pass it when running this script.")
        sys.exit(1)

    parsed = urlparse(db_url)
    # path is like '/coursemate' or '/coursemate-db'
    db_name = (parsed.path or "/coursemate").lstrip("/") or "coursemate"
    # Connect to the default 'postgres' database to create our database
    admin_url = urlunparse(parsed._replace(path="/postgres"))
    host_part = f"{parsed.hostname}:{parsed.port or 5432}/postgres"
    print(f"Connecting to: {host_part}")
    print(f"Creating database '{db_name}' if it does not exist...")

    try:
        with psycopg.connect(admin_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (db_name,),
                )
                if cur.fetchone():
                    print(f"Database '{db_name}' already exists.")
                else:
                    cur.execute(f'CREATE DATABASE "{db_name}"')
                    print(f"Database '{db_name}' created.")
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
