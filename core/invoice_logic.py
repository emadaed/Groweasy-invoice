# invoice_logic.py
def prepare_invoice_data(form_data, files=None):
    """Prepare complete invoice data with FBR fields"""

    # Extract existing data - USE getlist() for array fields
    items = []
    item_names = form_data.getlist('item_name[]')  # Changed to getlist
    item_qtys = form_data.getlist('item_qty[]')    # Changed to getlist
    item_prices = form_data.getlist('item_price[]') # Changed to getlist
    item_ids = form_data.getlist('item_id[]')

    for i in range(len(item_names)):
        if item_names[i].strip():
            qty = float(item_qtys[i]) if i < len(item_qtys) and item_qtys[i] else 0
            price = float(item_prices[i]) if i < len(item_prices) and item_prices[i] else 0
            product_id = item_ids[i] if i < len(item_ids) and item_ids[i] else None

            items.append({
                'name': item_names[i],
                'qty': qty,
                'price': price,
                'total': qty * price,
                'product_id': product_id
            })

    subtotal = sum(item['total'] for item in items)
    tax_rate = float(form_data.get('tax_rate', 0))  # Remove [0]
    discount_rate = float(form_data.get('discount_rate', 0))  # Remove [0]

    discount_amount = subtotal * (discount_rate / 100)
    taxable_amount = subtotal - discount_amount
    tax_amount = taxable_amount * (tax_rate / 100)
    grand_total = subtotal - discount_amount + tax_amount

    # Handle logo file upload
    logo_b64 = None
    if files and 'logo' in files and files['logo'].filename:
        from werkzeug.utils import secure_filename
        import base64
        logo_file = files['logo']
        if logo_file and logo_file.filename:
            logo_b64 = base64.b64encode(logo_file.read()).decode('utf-8')

    # Enhanced with FBR fields - REMOVE ALL [0] INDEXING
    return {
        # Existing fields
        'items': items,
        'subtotal': subtotal,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'discount_rate': discount_rate,
        'discount_amount': discount_amount,
        'grand_total': grand_total,
        'invoice_number': form_data.get('invoice_number', 'INV-00001'),  # Remove [0]
        'invoice_date': form_data.get('invoice_date', ''),  # Remove [0]
        'client_name': form_data.get('client_name', ''),  # Remove [0]
        'client_email': form_data.get('client_email', ''),  # Remove [0]
        'client_phone': form_data.get('client_phone', ''),  # Remove [0]
        'client_address': form_data.get('client_address', ''),  # Remove [0]

        # Business Information
        'company_name': form_data.get('company_name', 'Your Company Name'),  # Remove [0]
        'company_address': form_data.get('company_address', '123 Business Street, City, State 12345'),  # Remove [0]
        'company_phone': form_data.get('company_phone', '+1 (555) 123-4567'),  # Remove [0]
        'company_email': form_data.get('company_email', 'hello@company.com'),  # Remove [0]
        'company_tax_id': form_data.get('company_tax_id', ''),  # Remove [0]
        'due_date': form_data.get('due_date', ''),  # Remove [0]
        'payment_terms': form_data.get('payment_terms', 'Due upon receipt'),  # Remove [0]
        'payment_methods': form_data.get('payment_methods', 'Bank Transfer, Credit Card'),  # Remove [0]
        'notes': form_data.get('notes', ''),  # Remove [0]

        # FBR Specific Fields
        'seller_ntn': form_data.get('seller_ntn', ''),  # Remove [0]
        'seller_strn': form_data.get('seller_strn', ''),  # Remove [0]
        'buyer_ntn': form_data.get('buyer_ntn', ''),  # Remove [0]
        'buyer_strn': form_data.get('buyer_strn', ''),  # Remove [0]
        'invoice_type': form_data.get('invoice_type', 'S'),  # Remove [0] - S for Sale

        # Logo handling
        'logo_b64': logo_b64
    }
