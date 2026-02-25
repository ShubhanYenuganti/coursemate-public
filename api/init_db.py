"""
Database initialization script.
Run this to set up the database schema:
    cd api && python init_db.py
"""
import os
from dotenv import load_dotenv
from db import init_db

if __name__ == "__main__":
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

    if not os.environ.get('DATABASE_URL'):
        print("Error: DATABASE_URL environment variable is not set!")
        print("\nCreate a .env file in the project root with:")
        print("DATABASE_URL=postgresql://user:password@localhost:5432/coursemate")
        print("\nSee CLOUD_SETUP.md for full setup instructions.")
        exit(1)

    db_url = os.environ.get('DATABASE_URL')
    host_part = db_url.split('@')[1] if '@' in db_url else 'database'
    print(f"Initializing database...")
    print(f"Connecting to: {host_part}")

    try:
        init_db()
        print("Database setup complete!")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        exit(1)
