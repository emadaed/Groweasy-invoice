from datetime import datetime

def build_invoice_data(customer_name, items):
    subtotal = sum(i['price'] * i['qty'] for i in items)
    tax = round(subtotal * 0.15, 2)
    total = subtotal + tax
    return {
        "invoice_no": f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "date": datetime.now().strftime('%Y-%m-%d'),
        "customer_name": customer_name,
        "items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
    }
