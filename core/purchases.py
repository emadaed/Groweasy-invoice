# core/purchases.py - Purchase Order & Supplier Management
import sqlite3
import json
from datetime import datetime

def init_purchase_tables():
    """Initialize purchase order and supplier tables"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Suppliers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            tax_id TEXT,
            total_purchased DECIMAL(10,2) DEFAULT 0,
            order_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Purchase Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            po_number TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            order_date DATE NOT NULL,
            delivery_date DATE,
            grand_total DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'pending',
            order_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_purchase_orders ON purchase_orders(user_id, order_date)')

    conn.commit()
    conn.close()

def save_purchase_order(user_id, order_data):
    """Save purchase order and auto-update supplier"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Ensure tables exist
    init_purchase_tables()

    # Extract metadata
    po_number = order_data.get('invoice_number', 'PO-001')
    supplier_name = order_data.get('client_name', 'Unknown Supplier')
    order_date = order_data.get('invoice_date', '')
    delivery_date = order_data.get('due_date', '')
    grand_total = float(order_data.get('grand_total', 0))

    # Save purchase order
    order_json = json.dumps(order_data)
    c.execute('''
        INSERT INTO purchase_orders
        (user_id, po_number, supplier_name, order_date, delivery_date, grand_total, order_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, po_number, supplier_name, order_date, delivery_date, grand_total, order_json))

    # Auto-save supplier
    try:
        supplier_data = {
            'name': supplier_name,
            'email': order_data.get('client_email', ''),
            'phone': order_data.get('client_phone', ''),
            'address': order_data.get('client_address', ''),
            'tax_id': order_data.get('buyer_ntn', '')
        }

        c.execute('SELECT id FROM suppliers WHERE user_id = ? AND name = ?',
                 (user_id, supplier_data['name']))
        existing = c.fetchone()

        if existing:
            c.execute('''
                UPDATE suppliers SET
                email=?, phone=?, address=?, tax_id=?,
                order_count = order_count + 1,
                total_purchased = total_purchased + ?,
                updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (supplier_data.get('email'), supplier_data.get('phone'),
                  supplier_data.get('address'), supplier_data.get('tax_id'),
                  grand_total, existing[0]))
        else:
            c.execute('''
                INSERT INTO suppliers
                (user_id, name, email, phone, address, tax_id, total_purchased, order_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, supplier_data['name'], supplier_data.get('email'),
                  supplier_data.get('phone'), supplier_data.get('address'),
                  supplier_data.get('tax_id'), grand_total))

    except Exception as e:
        print(f"Supplier auto-save error: {e}")

    conn.commit()
    conn.close()
    return True

def get_purchase_orders(user_id, limit=50, offset=0):
    """Get purchase orders for user"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        SELECT id, po_number, supplier_name, order_date, delivery_date,
               grand_total, status, created_at, order_data
        FROM purchase_orders
        WHERE user_id = ?
        ORDER BY order_date DESC, created_at DESC
        LIMIT ? OFFSET ?
    ''', (user_id, limit, offset))

    orders = c.fetchall()
    conn.close()

    result = []
    for order in orders:
        result.append({
            'id': order[0],
            'po_number': order[1],
            'supplier_name': order[2],
            'order_date': order[3],
            'delivery_date': order[4],
            'grand_total': float(order[5]),
            'status': order[6],
            'created_at': order[7],
            'data': json.loads(order[8])
        })
    return result

def get_suppliers(user_id):
    """Get all suppliers"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Ensure table exists
    init_purchase_tables()

    c.execute('''
        SELECT id, name, email, phone, address, tax_id, total_purchased, order_count
        FROM suppliers WHERE user_id = ? ORDER BY name
    ''', (user_id,))

    suppliers = c.fetchall()
    conn.close()

    result = []
    for supplier in suppliers:
        result.append({
            'id': supplier[0],
            'name': supplier[1],
            'email': supplier[2],
            'phone': supplier[3],
            'address': supplier[4],
            'tax_id': supplier[5],
            'total_purchased': float(supplier[6]) if supplier[6] else 0,
            'order_count': supplier[7]
        })
    return result
