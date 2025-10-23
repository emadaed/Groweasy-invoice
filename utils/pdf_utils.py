from flask import render_template
from weasyprint import HTML
import io, base64, qrcode
from PIL import Image

def render_invoice_pdf(data):
    """Render invoice PDF with colored QR and embedded logo (if provided)."""
    # --- Build QR ---
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=3
    )
    qr.add_data(f"Invoice:{data.get('invoice_number','')}|Total:{data.get('total',0)}")
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#007bff", back_color="white").convert("RGB")

    # embed uploaded logo in the center of QR if present
    logo_b64 = data.get("logo_b64")
    if logo_b64:
        try:
            logo_bytes = io.BytesIO(base64.b64decode(logo_b64))
            logo = Image.open(logo_bytes).convert("RGBA")
            qr_w, qr_h = qr_img.size
            logo_size = int(qr_w * 0.25)
            logo = logo.resize((logo_size, logo_size), Image.ANTIALIAS)
            pos = ((qr_w - logo_size) // 2, (qr_h - logo_size) // 2)
            qr_img.paste(logo, pos, logo)
        except Exception as e:
            print("Warning: could not embed logo into QR:", e)

    # convert to base64
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Render HTML -> PDF
    html = render_template("invoice.html", data=data, preview=False, qr_b64=qr_b64, logo_b64=data.get("logo_b64"))
    pdf_bytes = HTML(string=html).write_pdf()
    return pdf_bytes
