# core/db.py - DB Engine (Postgres/SQLite)
from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///users.db')
DB_ENGINE = create_engine(DATABASE_URL)

print(f"✅ Database connected: {DATABASE_URL[:50]}...")  # Debug

def create_all_tables():
    """Create all required tables in Postgres (safe for repeated calls)"""
    with DB_ENGINE.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                company_name TEXT,
                company_address TEXT,
                company_phone TEXT,
                company_email TEXT,
                company_tax_id TEXT,
                seller_ntn TEXT,
                seller_strn TEXT,
                preferred_currency TEXT DEFAULT 'PKR',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_invoices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                invoice_number TEXT,
                client_name TEXT,
                invoice_date DATE,
                due_date DATE,
                grand_total DECIMAL(10,2) NOT NULL,
                status TEXT DEFAULT 'paid',
                invoice_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory_items (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                current_stock INTEGER DEFAULT 0,
                min_stock_level INTEGER DEFAULT 5,
                selling_price DECIMAL(10,2),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                movement_type TEXT,
                quantity INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pending_invoices (
                user_id INTEGER PRIMARY KEY,
                invoice_data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchase_orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                po_number TEXT,
                supplier_name TEXT,
                grand_total DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                total_spent DECIMAL(10,2) DEFAULT 0,
                invoice_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                description TEXT,
                amount DECIMAL(10,2),
                category TEXT,
                expense_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                tax_id TEXT,
                total_purchased DECIMAL(10,2) DEFAULT 0,
                order_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        '''))
        print("✅ All tables created/verified in Postgres")

# Run on import (safe — IF NOT EXISTS)
create_all_tables()
