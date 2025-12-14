# core/db.py - DB Engine (Postgres/SQLite)
from sqlalchemy import create_engine
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///users.db')
DB_ENGINE = create_engine(DATABASE_URL)

print(f"✅ Database connected: {DATABASE_URL[:50]}...")  # Debug
