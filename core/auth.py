import sqlite3
import hashlib
import os
import json
from datetime import datetime

def init_db():
    """Initialize SQLite database for users"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT,
            company_address TEXT,
            company_phone TEXT,
            company_tax_id TEXT,
            seller_ntn TEXT,
            seller_strn TEXT,
            mobile_number TEXT,
            preferred_currency TEXT DEFAULT 'PKR',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # User Invoices
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_number TEXT NOT NULL,
            client_name TEXT NOT NULL,
            invoice_date DATE NOT NULL,
            due_date DATE,
            grand_total DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'paid',
            invoice_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_user_invoices ON user_invoices(user_id, invoice_date)')

    # Customers
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            tax_id TEXT,
            total_spent DECIMAL(10,2) DEFAULT 0,
            invoice_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Expenses
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            category TEXT NOT NULL,
            expense_date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Inventory Items
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Stock Movements
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reference_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES inventory_items (id)
        )
    ''')

    # Stock Alerts
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES inventory_items (id)
        )
    ''')

    # Pending Invoices (for session management)
    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_invoices (
            user_id INTEGER PRIMARY KEY,
            invoice_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # User Sessions (multi-device management)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            device_name TEXT,
            device_type TEXT,
            ip_address TEXT,
            user_agent TEXT,
            location TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions ON user_sessions(user_id, is_active)')

    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email, password, company_name=""):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, password_hash, company_name) VALUES (?, ?, ?)',
                 (email, hash_password(password), company_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(email, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id, password_hash FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    conn.close()

    if user and user[1] == hash_password(password):
        return user[0]
    return None

def update_user_profile(user_id, company_name=None, company_address=None, company_phone=None,
                       company_tax_id=None, seller_ntn=None, seller_strn=None, preferred_currency=None):
    """Update user profile information"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    updates = []
    params = []

    if company_name is not None:
        updates.append("company_name = ?")
        params.append(company_name)
    if company_address is not None:
        updates.append("company_address = ?")
        params.append(company_address)
    if company_phone is not None:
        updates.append("company_phone = ?")
        params.append(company_phone)
    if company_tax_id is not None:
        updates.append("company_tax_id = ?")
        params.append(company_tax_id)
    if seller_ntn is not None:
        updates.append("seller_ntn = ?")
        params.append(seller_ntn)
    if seller_strn is not None:
        updates.append("seller_strn = ?")
        params.append(seller_strn)
    if preferred_currency is not None:
        updates.append("preferred_currency = ?")
        params.append(preferred_currency)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        params.append(user_id)

        c.execute(query, params)
        conn.commit()

    conn.close()
    return True

def change_user_password(user_id, new_password):
    """Change user password"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
              (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
    return True

def get_user_profile(user_id):
    """Get user profile information"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''SELECT id, email, company_name, company_address, company_phone,
                        company_tax_id, seller_ntn, seller_strn, preferred_currency, created_at
                 FROM users WHERE id = ?''', (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        return {
            'id': user[0],
            'email': user[1],
            'company_name': user[2],
            'company_address': user[3],
            'company_phone': user[4],
            'company_tax_id': user[5],
            'seller_ntn': user[6],
            'seller_strn': user[7],
            'preferred_currency': user[8],
            'created_at': user[9]
        }
    return None

def get_user_invoices(user_id, limit=50, offset=0, search=None):
    """Get invoices for a user with search and pagination"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    query = '''
        SELECT id, invoice_number, client_name, invoice_date, due_date,
               grand_total, status, created_at, invoice_data
        FROM user_invoices
        WHERE user_id = ?
    '''
    params = [user_id]

    if search:
        query += ' AND (invoice_number LIKE ? OR client_name LIKE ?)'
        search_term = f'%{search}%'
        params.extend([search_term, search_term])

    query += ' ORDER BY invoice_date DESC, created_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    c.execute(query, params)
    invoices = c.fetchall()
    conn.close()

    result = []
    for invoice in invoices:
        result.append({
            'id': invoice[0],
            'invoice_number': invoice[1],
            'client_name': invoice[2],
            'invoice_date': invoice[3],
            'due_date': invoice[4],
            'grand_total': float(invoice[5]),
            'status': invoice[6],
            'created_at': invoice[7],
            'data': json.loads(invoice[8])
        })
    return result

def get_invoice_count(user_id, search=None):
    """Get total count of invoices for pagination"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    query = 'SELECT COUNT(*) FROM user_invoices WHERE user_id = ?'
    params = [user_id]

    if search:
        query += ' AND (invoice_number LIKE ? OR client_name LIKE ?)'
        search_term = f'%{search}%'
        params.extend([search_term, search_term])

    c.execute(query, params)
    count = c.fetchone()[0]
    conn.close()
    return count

def get_revenue_analytics(user_id, period='monthly'):
    """Get revenue analytics for dashboard"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if period == 'monthly':
        query = '''
            SELECT
                STRFTIME('%Y-%m', invoice_date) as month,
                COUNT(*) as invoice_count,
                SUM(grand_total) as total_revenue,
                AVG(grand_total) as avg_invoice
            FROM user_invoices
            WHERE user_id = ?
            GROUP BY STRFTIME('%Y-%m', invoice_date)
            ORDER BY month DESC
            LIMIT 12
        '''
    else:
        query = '''
            SELECT
                STRFTIME('%Y', invoice_date) as year,
                COUNT(*) as invoice_count,
                SUM(grand_total) as total_revenue,
                AVG(grand_total) as avg_invoice
            FROM user_invoices
            WHERE user_id = ?
            GROUP BY STRFTIME('%Y', invoice_date)
            ORDER BY year DESC
        '''

    c.execute(query, (user_id,))
    results = c.fetchall()
    conn.close()

    analytics = []
    for row in results:
        analytics.append({
            'period': row[0],
            'invoice_count': row[1],
            'total_revenue': float(row[2]) if row[2] else 0,
            'avg_invoice': float(row[3]) if row[3] else 0
        })

    return analytics

def get_client_analytics(user_id):
    """Get top clients by revenue"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    query = '''
        SELECT
            client_name,
            COUNT(*) as invoice_count,
            SUM(grand_total) as total_spent,
            AVG(grand_total) as avg_invoice
        FROM user_invoices
        WHERE user_id = ?
        GROUP BY client_name
        ORDER BY total_spent DESC
        LIMIT 10
    '''

    c.execute(query, (user_id,))
    results = c.fetchall()
    conn.close()

    clients = []
    for row in results:
        clients.append({
            'client_name': row[0],
            'invoice_count': row[1],
            'total_spent': float(row[2]) if row[2] else 0,
            'avg_invoice': float(row[3]) if row[3] else 0
        })

    return clients

def get_business_summary(user_id):
    """Get overall business summary"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        SELECT
            COUNT(*) as total_invoices,
            SUM(grand_total) as total_revenue,
            AVG(grand_total) as avg_invoice,
            MIN(invoice_date) as first_invoice,
            MAX(invoice_date) as last_invoice
        FROM user_invoices
        WHERE user_id = ?
    ''', (user_id,))

    summary = c.fetchone()
    conn.close()

    if summary and summary[0] > 0:
        return {
            'total_invoices': summary[0],
            'total_revenue': float(summary[1]) if summary[1] else 0,
            'avg_invoice': float(summary[2]) if summary[2] else 0,
            'first_invoice': summary[3],
            'last_invoice': summary[4]
        }
    else:
        return {
            'total_invoices': 0,
            'total_revenue': 0,
            'avg_invoice': 0,
            'first_invoice': None,
            'last_invoice': None
        }

def save_user_invoice(user_id, invoice_data):
    """Save invoice data with metadata"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    invoice_number = invoice_data.get('invoice_number', 'Unknown')
    client_name = invoice_data.get('client_name', 'Unknown Client')
    invoice_date = invoice_data.get('invoice_date', '')
    due_date = invoice_data.get('due_date', '')
    grand_total = float(invoice_data.get('grand_total', 0))

    invoice_json = json.dumps(invoice_data)

    c.execute('''
        INSERT INTO user_invoices
        (user_id, invoice_number, client_name, invoice_date, due_date, grand_total, invoice_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, invoice_number, client_name, invoice_date, due_date, grand_total, invoice_json))

    # Auto-save customer
    try:
        customer_data = {
            'name': client_name,
            'email': invoice_data.get('client_email', ''),
            'phone': invoice_data.get('client_phone', ''),
            'address': invoice_data.get('client_address', ''),
            'tax_id': invoice_data.get('buyer_ntn', '')
        }

        c.execute('SELECT id FROM customers WHERE user_id = ? AND name = ?',
                 (user_id, customer_data['name']))
        existing = c.fetchone()

        if existing:
            c.execute('''
                UPDATE customers SET
                email=?, phone=?, address=?, tax_id=?,
                invoice_count = invoice_count + 1,
                total_spent = total_spent + ?,
                updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (customer_data.get('email'), customer_data.get('phone'),
                  customer_data.get('address'), customer_data.get('tax_id'),
                  grand_total, existing[0]))
        else:
            c.execute('''
                INSERT INTO customers
                (user_id, name, email, phone, address, tax_id, total_spent, invoice_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, customer_data['name'], customer_data.get('email'),
                  customer_data.get('phone'), customer_data.get('address'),
                  customer_data.get('tax_id'), grand_total))

    except Exception as e:
        print(f"Customer auto-save error: {e}")

    conn.commit()
    conn.close()
    return True

def get_customers(user_id):
    """Get all customers"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        SELECT id, name, email, phone, address, tax_id, total_spent, invoice_count
        FROM customers WHERE user_id = ? ORDER BY name
    ''', (user_id,))

    customers = c.fetchall()
    conn.close()

    result = []
    for customer in customers:
        result.append({
            'id': customer[0],
            'name': customer[1],
            'email': customer[2],
            'phone': customer[3],
            'address': customer[4],
            'tax_id': customer[5],
            'total_spent': float(customer[6]) if customer[6] else 0,
            'invoice_count': customer[7]
        })
    return result

def save_expense(user_id, expense_data):
    """Save business expense"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        INSERT INTO expenses (user_id, description, amount, category, expense_date, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, expense_data['description'], expense_data['amount'],
          expense_data['category'], expense_data['expense_date'],
          expense_data.get('notes', '')))

    conn.commit()
    conn.close()
    return True

def get_expenses(user_id, limit=50):
    """Get expenses for a user"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        SELECT id, description, amount, category, expense_date, notes, created_at
        FROM expenses WHERE user_id = ?
        ORDER BY expense_date DESC, created_at DESC
        LIMIT ?
    ''', (user_id, limit))

    expenses = c.fetchall()
    conn.close()

    result = []
    for expense in expenses:
        result.append({
            'id': expense[0],
            'description': expense[1],
            'amount': float(expense[2]),
            'category': expense[3],
            'expense_date': expense[4],
            'notes': expense[5],
            'created_at': expense[6]
        })
    return result

## Expense summary
def get_expense_summary(user_id):
    """Get expense summary by category"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        SELECT category, SUM(amount) as total, COUNT(*) as count
        FROM expenses WHERE user_id = ?
        GROUP BY category ORDER BY total DESC
    ''', (user_id,))

    summary = c.fetchall()
    conn.close()

    result = []
    for item in summary:
        result.append({
            'category': item[0],
            'total': float(item[1]) if item[1] else 0,
            'count': item[2]
        })
    return result
