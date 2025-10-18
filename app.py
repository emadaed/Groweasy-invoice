from flask import Flask, render_template, request, send_file
from weasyprint import HTML
from io import BytesIO
from utils.invoice_logic import build_invoice_data

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/generate', methods=['POST'])
def generate_invoice():
    customer_name = request.form['customer_name']
    items = [
        {"name": request.form['item1'], "qty": int(request.form['qty1']), "price": float(request.form['price1'])},
        {"name": request.form['item2'], "qty": int(request.form['qty2']), "price": float(request.form['price2'])},
    ]
    data = build_invoice_data(customer_name, items)
    html = render_template('invoice.html', data=data)

    pdf = BytesIO()
    HTML(string=html).write_pdf(pdf)
    pdf.seek(0)
    filename = f"{data['invoice_no']}.pdf"
    return send_file(pdf, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
