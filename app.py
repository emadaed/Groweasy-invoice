# ============================================================
# GrowEasy-Invoice | Unified Flask App (Preview + PDF Download)
# Phase 4.2 – Stable Functional Build
# ============================================================

from flask import Flask, render_template, request, send_file
from weasyprint import HTML
from datetime import datetime
from pathlib import Path
import io, base64, json, qrcode
from PIL import Image

app = Flask(__name__)

# -----------------------------------------------
# Home (Form page)
# -----------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("form.html")


# -----------------------------------------------
# Preview Invoice (HTML view with QR + logo)
# -----------------------------------------------
@app.route("/preview", methods=["POST"])
def preview_invoice():
    try:
        # --- Gather form data ---
        client_name = request.form.get("client_name", "").strip()
        client_email = request.form.get("client_email", "").strip()
        client_address = request.form.get("client_address", "").strip()
        tax_rate = float(request.form.get("tax_rate") or 0)
        discount_pct = float(request.form.get("discount_pct") or 0)
        invoice_number = request.form.get("invoice_number") or f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # --- Optional logo upload ---
        logo_b64 = None
        if "logo" in request.files:
            logo_file = request.files["logo"]
            if logo_file and logo_file.filename:
                logo_b64 = base64.b64encode(logo_file.read()).decode("utf-8")

        # --- Collect line items ---
        names = request.form.getlist("item[]") or request.form.getlist("item_name[]")
        qtys = request.form.getlist("quantity[]") or request.form.getlist("qty[]")
        prices = request.form.getlist("price[]") or request.form.getlist("unit_price[]")

        items = []
        subtotal = 0.0
        for i in range(max(len(names), len(qtys), len(prices))):
            name = (names[i].strip() if i < len(names) else "")
            if not name:
                continue
            try:
                qty = float(qtys[i]) if i < len(qtys) else 0
                price = float(prices[i]) if i < len(prices) else 0
            except Exception:
                qty, price = 0, 0
            total = round(qty * price, 2)
            subtotal += total
            items.append({"name": name, "qty": qty, "price": price, "total": total})

        discount_amount = subtotal * (discount_pct / 100)
        subtotal_after_discount = subtotal - discount_amount
        tax_amount = subtotal_after_discount * (tax_rate / 100)
        grand_total = subtotal_after_discount + tax_amount

        # --- Prepare data dict ---
        data = {
            "invoice_number": invoice_number,
            "client_name": client_name,
            "client_email": client_email,
            "client_address": client_address,
            "invoice_date": datetime.now().strftime("%Y-%m-%d"),
            "tax_rate": tax_rate,
            "discount_pct": discount_pct,
            "discount_amount": round(discount_amount, 2),
            "items": items,
            "subtotal": round(subtotal, 2),
            "subtotal_after_discount": round(subtotal_after_discount, 2),
            "tax": round(tax_amount, 2),
            "total": round(grand_total, 2),
            "logo_b64": logo_b64
        }

        # --- Generate QR code (base64) ---
        qr_text = f"Invoice {invoice_number} for {client_name or 'Customer'}"
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(qr_text)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

        # Embed logo inside QR (if uploaded)
        if logo_b64:
            logo_bytes = base64.b64decode(logo_b64)
            logo_img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            qr_w, qr_h = img_qr.size
            logo_img.thumbnail((int(qr_w * 0.22), int(qr_h * 0.22)), Image.LANCZOS)
            pos = ((qr_w - logo_img.width) // 2, (qr_h - logo_img.height) // 2)
            img_qr.paste(logo_img, pos, logo_img)

        buf = io.BytesIO()
        img_qr.save(buf, format="PNG")
        qr_b64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

        # --- Render preview page with Download button ---
        return render_template("invoice.html", data=data, preview=True, qr_b64=qr_b64)

    except Exception as e:
        app.logger.error(f"Preview failed: {e}", exc_info=True)
        return f"Error generating preview: {e}", 500


# -----------------------------------------------
# Download PDF (from preview)
# -----------------------------------------------
@app.route("/download", methods=["POST"])
def download_invoice():
    try:
        data = json.loads(request.form.get("data"))
        html = render_template("invoice.html", data=data, preview=False, qr_b64=data.get("qr_b64"))
        pdf_bytes = HTML(string=html, base_url=str(Path(__file__).parent.resolve())).write_pdf()
        return send_file(io.BytesIO(pdf_bytes),
                         mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"{data.get('invoice_number','invoice')}.pdf")
    except Exception as e:
        app.logger.error(f"Download failed: {e}", exc_info=True)
        return f"Error generating PDF: {e}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
