import sqlite3
import hashlib
import os
import json
from datetime import datetime

def init_db():
    """Initialize SQLite database for users"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT,
            company_address TEXT,
            company_phone TEXT,
            company_tax_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            invoice_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
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
        return False  # User already exists
    finally:
        conn.close()

def verify_user(email, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id, password_hash FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    conn.close()

    if user and user[1] == hash_password(password):
        return user[0]  # Return user ID
    return None

def update_user_profile(user_id, company_name=None, company_address=None, company_phone=None, company_tax_id=None):
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

    c.execute('SELECT id, email, company_name, company_address, company_phone, company_tax_id, created_at FROM users WHERE id = ?', (user_id,))
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
            'created_at': user[6]
        }
    return None

def save_user_invoice(user_id, invoice_data):
    """Save invoice data for user history"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Convert invoice data to JSON string
    invoice_json = json.dumps(invoice_data)

    c.execute('INSERT INTO user_invoices (user_id, invoice_data) VALUES (?, ?)',
             (user_id, invoice_json))
    conn.commit()
    conn.close()
    return True

def get_user_invoices(user_id):
    """Get all invoices for a user"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('SELECT id, invoice_data, created_at FROM user_invoices WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    invoices = c.fetchall()
    conn.close()

    result = []
    for invoice in invoices:
        result.append({
            'id': invoice[0],
            'data': json.loads(invoice[1]),
            'created_at': invoice[2]
        })
    return result
