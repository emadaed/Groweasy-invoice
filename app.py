from flask import Flask, render_template, request, send_file
import io, json, base64
from pathlib import Path
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("form.html")

@app.route("/preview", methods=["POST"])
def preview_invoice():
    try:
        form_data = request.form.to_dict(flat=False)
        files = request.files
        data = prepare_invoice_data(form_data, files)

        # QR creation
        qr_dir = Path("static/assets/qr")
        qr_dir.mkdir(parents=True, exist_ok=True)
        qr_path = qr_dir / f"{data['invoice_number']}.png"
        logo_path = data.get("logo_path", "static/assets/logo.png")
        make_qr_with_logo(f"Invoice {data['invoice_number']} for {data['client_name']}", logo_path, qr_path)
        with open(qr_path, "rb") as f:
            qr_b64 = base64.b64encode(f.read()).decode("utf-8")

        return render_template("invoice.html", data=data, qr_b64=qr_b64, preview=True)
    except Exception as e:
        app.logger.error(f"Preview failed: {e}", exc_info=True)
        return f"Error generating preview: {e}", 500

@app.route("/download", methods=["POST"])
def download_invoice():
    try:
        data = json.loads(request.form.get("data"))
        html = render_template("invoice.html", data=data, preview=False, qr_b64=data.get("qr_b64"))
        pdf_bytes = generate_pdf(html)
        return send_file(io.BytesIO(pdf_bytes),
                         mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"{data.get('invoice_number','invoice')}.pdf")
    except Exception as e:
        app.logger.error(f"Download failed: {e}", exc_info=True)
        return f"Error generating PDF: {e}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
