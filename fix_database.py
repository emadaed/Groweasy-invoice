# fix_database.py
from core.db import DB_ENGINE
from sqlalchemy import text
import os

def run_migrations():
    with DB_ENGINE.begin() as conn:
        print("🔧 Fixing database schema...")

        # 1. Check if stock_movements table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'stock_movements'
            )
        """)).scalar()

        if not result:
            print("Creating stock_movements table...")
            conn.execute(text("""
                CREATE TABLE stock_movements (
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

        # 2. Fix the HAVING clause issue by creating a view or fixing the query
        print("Creating database views for reports...")

        # Create a view for inventory reports
        conn.execute(text("""
            CREATE OR REPLACE VIEW inventory_report_view AS
            SELECT
                ii.id,
                ii.name,
                ii.current_stock,
                ii.cost_price,
                ii.selling_price,
                COALESCE(SUM(CASE
                    WHEN sm.movement_type = 'sale'
                    THEN ABS(sm.quantity)
                    ELSE 0
                END), 0) as units_sold_total
            FROM inventory_items ii
            LEFT JOIN stock_movements sm ON ii.id = sm.product_id
            WHERE ii.is_active = TRUE
            GROUP BY ii.id
        """))

        print("✅ Database fixes applied!")

        # 3. Verify tables
        tables = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)).fetchall()

        print(f"\n📊 Database tables: {[t[0] for t in tables]}")

if __name__ == "__main__":
    try:
        run_migrations()
        print("\n🎉 Database migration complete!")
    except Exception as e:
        print(f"❌ Error: {e}")
