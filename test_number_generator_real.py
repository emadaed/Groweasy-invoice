# test_number_generator_real.py
import os
os.environ['DATABASE_URL'] = 'sqlite:///users.db'

from core.number_generator import NumberGenerator
from sqlalchemy import text
from core.db import DB_ENGINE

print("🧪 REAL Number Generator Test")
print("=" * 40)

test_user_id = 1

# Clear any test data first
with DB_ENGINE.begin() as conn:
    conn.execute(text("DELETE FROM user_invoices WHERE user_id = :uid"), {"uid": test_user_id})
    conn.execute(text("DELETE FROM purchase_orders WHERE user_id = :uid"), {"uid": test_user_id})

print("📊 Database cleared for testing")

# Test 1: Invoice numbers (should start from 00001)
print("\n📄 Testing Invoice Numbers:")
for i in range(3):
    inv_number = NumberGenerator.generate_invoice_number(test_user_id)
    print(f"  Generated: {inv_number}")

    # Actually insert to simulate real usage
    with DB_ENGINE.begin() as conn:
        conn.execute(text("""
            INSERT INTO user_invoices
            (user_id, invoice_number, client_name, invoice_date, grand_total, invoice_data)
            VALUES (:uid, :num, 'Test Client', '2024-01-01', 100.0, '{}')
        """), {"uid": test_user_id, "num": inv_number})

    print(f"  Inserted into database")

# Test 2: PO numbers (should start from 00001)
print("\n📋 Testing Purchase Order Numbers:")
for i in range(3):
    po_number = NumberGenerator.generate_po_number(test_user_id)
    print(f"  Generated: {po_number}")

    # Actually insert to simulate real usage
    with DB_ENGINE.begin() as conn:
        conn.execute(text("""
            INSERT INTO purchase_orders
            (user_id, po_number, supplier_name, order_date, grand_total, order_data)
            VALUES (:uid, :num, 'Test Supplier', '2024-01-01', 100.0, '{}')
        """), {"uid": test_user_id, "num": po_number})

    print(f"  Inserted into database")

# Verify final state
print("\n📊 Final Database State:")
with DB_ENGINE.connect() as conn:
    invoices = conn.execute(text("SELECT invoice_number FROM user_invoices ORDER BY id")).fetchall()
    print(f"  Invoices: {[i[0] for i in invoices]}")

    pos = conn.execute(text("SELECT po_number FROM purchase_orders ORDER BY id")).fetchall()
    print(f"  Purchase Orders: {[p[0] for p in pos]}")

print("=" * 40)
print("✅ Expected: INV-00001, INV-00002, INV-00003, PO-00001, PO-00002, PO-00003")
