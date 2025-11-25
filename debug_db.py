# debug_db.py
import sqlite3
import os

def check_database():
    print("🔍 CHECKING DATABASE STATE...")

    if not os.path.exists('users.db'):
        print("❌ ERROR: users.db file does not exist!")
        return

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Check all tables
    print("\n📊 ALL TABLES:")
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    for table in tables:
        print(f"   - {table[0]}")

    # Check customers table structure
    print("\n👥 CUSTOMERS TABLE STRUCTURE:")
    try:
        c.execute("PRAGMA table_info(customers);")
        columns = c.fetchall()
        if columns:
            for col in columns:
                print(f"   - {col[1]} ({col[2]})")
        else:
            print("   ❌ CUSTOMERS TABLE DOES NOT EXIST!")
    except:
        print("   ❌ CUSTOMERS TABLE DOES NOT EXIST!")

    # Check customers data
    print("\n📋 CUSTOMERS DATA:")
    try:
        c.execute("SELECT * FROM customers;")
        customers = c.fetchall()
        if customers:
            for customer in customers:
                print(f"   - ID: {customer[0]}, Name: {customer[2]}, Invoices: {customer[8]}")
        else:
            print("   ⚠️  No customers in database")
    except Exception as e:
        print(f"   ❌ Error reading customers: {e}")

    # Check invoices data
    print("\n🧾 INVOICES DATA:")
    try:
        c.execute("SELECT id, invoice_number, client_name FROM user_invoices;")
        invoices = c.fetchall()
        if invoices:
            for invoice in invoices:
                print(f"   - Invoice: {invoice[1]}, Client: {invoice[2]}")
        else:
            print("   ⚠️  No invoices in database")
    except Exception as e:
        print(f"   ❌ Error reading invoices: {e}")

    conn.close()
    print("\n✅ DEBUG COMPLETE")

if __name__ == "__main__":
    check_database()
