import base64, io
from datetime import datetime
from werkzeug.utils import secure_filename
from core.utils import random_invoice_number

def safe_float(value, default=0.0):
    """Safely convert to float, handling blanks or invalids."""
    try:
        if value in (None, "", []):
            return default
        return float(value)
    except Exception:
        return default

def prepare_invoice_data(form_data, files):
    """Parse form fields & files into structured dict."""
    def val(key, default=""):
        v = form_data.get(key)
        return v[0] if isinstance(v, list) else (v or default)

    items = []
    names = form_data.get("item_name[]", [])
    qtys = form_data.get("item_qty[]", [])
    prices = form_data.get("item_price[]", [])

    for i in range(len(names)):
        name = names[i].strip() if i < len(names) else ""
        qty = safe_float(qtys[i] if i < len(qtys) else 0)
        price = safe_float(prices[i] if i < len(prices) else 0)
        if name:
            items.append({
                "name": name,
                "qty": qty,
                "price": price,
                "total": qty * price
            })

    subtotal = sum(i["total"] for i in items)
    discount_pct = safe_float(val("discount"))
    tax_rate = safe_float(val("tax"))
    discount_amount = subtotal * (discount_pct / 100)
    taxed = (subtotal - discount_amount) * (1 + tax_rate / 100)

    # --- Logo Handling ---
    logo_b64 = None
    logo_path = "static/assets/logo.png"
    if "logo" in files and files["logo"]:
        file = files["logo"]
        filename = secure_filename(file.filename)
        saved_path = f"static/assets/{filename}"
        file.save(saved_path)
        with open(saved_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        logo_path = saved_path

    return {
        "invoice_number": val("invoice_number", random_invoice_number()),
        "invoice_date": datetime.now().strftime("%Y-%m-%d"),
        "client_name": val("client_name"),
        "client_email": val("client_email"),
        "client_address": val("client_address"),
        "tax_rate": tax_rate,
        "discount_pct": discount_pct,
        "discount_amount": discount_amount,
        "subtotal": subtotal,
        "total": taxed,
        "items": items,
        "logo_b64": logo_b64,
        "logo_path": logo_path
    }
