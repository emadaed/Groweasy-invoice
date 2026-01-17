# test_po_creation.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from core.invoice_service import InvoiceService

# Test form data extraction
test_form_data = {
    'supplier_name': 'Test Supplier',
    'supplier_email': 'test@supplier.com',
    'po_date': '2024-01-17',
    'items[0][name]': 'Test Product 1',
    'items[0][price]': '100.50',
    'items[0][qty]': '2',
    'items[1][name]': 'Test Product 2',
    'items[1][price]': '50.00',
    'items[1][qty]': '3',
    'tax_rate': '17',
    'shipping_cost': '50'
}

print("🧪 Testing purchase order creation...")
service = InvoiceService(1)  # User ID 1 for testing

# Test item extraction
items = service._extract_items(test_form_data, prefix='')
print(f"✅ Extracted {len(items)} items")

# Test PO creation
po_data, errors = service.create_purchase_order(test_form_data)

if errors:
    print("❌ Errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print(f"✅ PO created: {po_data['po_number']}")
    print(f"  Supplier: {po_data['supplier_name']}")
    print(f"  Total: {po_data['grand_total']}")
    print(f"  Items: {len(po_data['items'])}")
