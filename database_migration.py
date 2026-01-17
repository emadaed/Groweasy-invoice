# database_migration.py
from core.db import DB_ENGINE
from sqlalchemy import text

def fix_database():
    with DB_ENGINE.begin() as conn:
        print("🔧 Fixing database schema...")

        # Create stock_movements table if missing
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                movement_type VARCHAR(50) NOT NULL,
                reference_id VARCHAR(100),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Created stock_movements table")

        # Fix purchase_orders table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                po_number VARCHAR(50) UNIQUE NOT NULL,
                order_data TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Verified purchase_orders table")

        print("🎉 Database migration complete!")

if __name__ == "__main__":
    fix_database()
