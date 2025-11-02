def prepare_invoice_data(form_data, files=None):
    """Prepare complete invoice data with professional fields"""
    
    # Extract existing data
    items = []
    item_names = form_data.get('item_name[]', [])
    item_qtys = form_data.get('item_qty[]', [])
    item_prices = form_data.get('item_price[]', [])
    
    for i in range(len(item_names)):
        if item_names[i].strip():
            qty = float(item_qtys[i]) if i < len(item_qtys) and item_qtys[i] else 0
            price = float(item_prices[i]) if i < len(item_prices) and item_prices[i] else 0
            items.append({
                'name': item_names[i],
                'qty': qty,
                'price': price,
                'total': qty * price
            })
    
    subtotal = sum(item['total'] for item in items)
    tax_rate = float(form_data.get('tax_rate', [0])[0])
    discount_rate = float(form_data.get('discount_rate', [0])[0])
    
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
    
    # PROFESSIONAL FIELDS WITH DEFAULTS
    return {
        # Existing fields
        'items': items,
        'subtotal': subtotal,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'discount_rate': discount_rate,
        'discount_amount': discount_amount,
        'grand_total': grand_total,
        'invoice_number': form_data.get('invoice_number', ['INV-00001'])[0],
        'invoice_date': form_data.get('invoice_date', [''])[0],
        'client_name': form_data.get('client_name', [''])[0],
        'client_email': form_data.get('client_email', [''])[0],
        'client_phone': form_data.get('client_phone', [''])[0],
        'client_address': form_data.get('client_address', [''])[0],
        
        # NEW PROFESSIONAL FIELDS (with defaults)
        'company_name': form_data.get('company_name', ['Your Company Name'])[0],
        'company_address': form_data.get('company_address', ['123 Business Street, City, State 12345'])[0],
        'company_phone': form_data.get('company_phone', ['+1 (555) 123-4567'])[0],
        'company_email': form_data.get('company_email', ['hello@company.com'])[0],
        'company_tax_id': form_data.get('company_tax_id', [''])[0],
        'due_date': form_data.get('due_date', [''])[0],
        'payment_terms': form_data.get('payment_terms', ['Due upon receipt'])[0],
        'payment_methods': form_data.get('payment_methods', ['Bank Transfer, Credit Card'])[0],
        'notes': form_data.get('notes', [''])[0],
        
        # Logo handling
        'logo_b64': logo_b64
    }
