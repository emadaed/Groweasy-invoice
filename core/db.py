# core/db.py - DB Engine (Postgres/SQLite)
from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///users.db')
DB_ENGINE = create_engine(DATABASE_URL)

print(f"✅ Database connected: {DATABASE_URL[:50]}...")  # Debug

def create_all_tables():
    """Create all required tables with ALL columns"""
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
                mobile_number TEXT,
                preferred_currency TEXT DEFAULT 'PKR',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_invoices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                invoice_number TEXT NOT NULL,
                client_name TEXT NOT NULL,
                invoice_date DATE NOT NULL,
                due_date DATE,
                grand_total DECIMAL(10,2) NOT NULL,
                status TEXT DEFAULT 'paid',
                invoice_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                tax_id TEXT,
                total_spent DECIMAL(10,2) DEFAULT 0,
                invoice_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                category TEXT NOT NULL,
                expense_date DATE NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory_items (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sku TEXT UNIQUE,
                category TEXT,
                description TEXT,
                current_stock INTEGER DEFAULT 0,
                min_stock_level INTEGER DEFAULT 5,
                cost_price DECIMAL(10,2),
                selling_price DECIMAL(10,2),
                supplier TEXT,
                location TEXT,
                barcode TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reference_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stock_alerts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                is_resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP.
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pending_invoices (
                user_id INTEGER PRIMARY KEY,
                invoice_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchase_orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                po_number TEXT NOT NULL,
                supplier_name TEXT NOT NULL,
                order_date DATE NOT NULL,
                delivery_date DATE,
                grand_total DECIMAL(10,2) NOT NULL,
                status TEXT DEFAULT 'pending',
                order_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                tax_id TEXT,
                total_purchased DECIMAL(10,2) DEFAULT 0,
                order_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                device_name TEXT,
                device_type TEXT,
                ip_address TEXT,
                user_agent TEXT,
                location TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        '''))
        print("✅ All tables created/verified in Postgres with full schema")

# Run on import (safe — IF NOT EXISTS)
create_all_tables()
