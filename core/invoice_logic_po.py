# core/invoice_logic_po.py
"""
Purchase Order data preparation - NO stock validation
"""

def prepare_po_data(form_data, files):
    """Prepare PO data without stock validation"""
    from datetime import datetime

    # Basic info
    po_data = {
        'client_name': form_data.get('client_name', ''),
        'client_email': form_data.get('client_email', ''),
        'client_phone': form_data.get('client_phone', ''),
        'client_address': form_data.get('client_address', ''),
        'company_name': form_data.get('company_name', ''),
        'company_address': form_data.get('company_address', ''),
        'company_phone': form_data.get('company_phone', ''),
        'invoice_date': form_data.get('invoice_date', datetime.now().strftime('%Y-%m-%d')),
        'due_date': form_data.get('due_date', ''),
        'subtotal': float(form_data.get('subtotal', 0)),
        'tax_rate': float(form_data.get('tax_rate', 0)),
        'tax_amount': float(form_data.get('tax_amount', 0)),
        'grand_total': float(form_data.get('grand_total', 0)),
        'notes': form_data.get('notes', ''),
        'invoice_type': 'P',
        'buyer_ntn': form_data.get('buyer_ntn', ''),
        'seller_ntn': form_data.get('seller_ntn', ''),
        'items': []
    }

    # Extract items
    i = 1
    while True:
        product_name = form_data.get(f'item_product_{i}')
        if not product_name:
            break

        qty = float(form_data.get(f'item_qty_{i}', 0))
        price = float(form_data.get(f'item_price_{i}', 0))

        # Find product_id if exists
        product_id = None
        from core.db import DB_ENGINE
        from sqlalchemy import text
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text("""
                SELECT id FROM inventory_items
                WHERE name = :name AND is_active = TRUE
                LIMIT 1
            """), {"name": product_name}).fetchone()
            if result:
                product_id = result[0]

        po_data['items'].append({
            'product_id': product_id,
            'name': product_name,
            'qty': qty,
            'price': price,
            'total': qty * price
        })

        i += 1

    return po_data
