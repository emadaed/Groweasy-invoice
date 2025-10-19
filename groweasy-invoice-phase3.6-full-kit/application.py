from flask import Flask, render_template, make_response, url_for
from utils.pdf_utils import render_invoice_pdf
app = Flask(__name__)

@app.route('/')
def index():
    return "GrowEasy-Invoice — Phase 3.6 baseline (Flask app) - /invoice to generate PDF"

@app.route('/invoice')
def invoice():
    # Example invoice context (replace with real data)
    ctx = {
        "invoice_no": "INV-20251019-001",
        "date": "2025-10-19",
        "bill_to": {
            "name": "Acme Corp",
            "address": "123 Example Street",
        },
        "items": [
            {"desc": "Consulting", "qty": 1, "unit": "service", "price": 150.00},
            {"desc": "Development", "qty": 10, "unit": "hour", "price": 25.00},
        ],
        "notes": "Thanks for your business.",
        "subtotal": 400.00,
        "tax": 40.00,
        "total": 440.00,
    }

    pdf_bytes = render_invoice_pdf(render_template("invoice.html", **ctx))
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=invoice.pdf'
    return response

@app.route('/health')
def health():
    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
