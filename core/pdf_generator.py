# core/pdf_generator.py - Final WeasyPrint Version (2026)

import logging
from datetime import datetime
from flask import render_template, request, url_for
from core.pdf_engine import generate_pdf
from core.qr_engine import generate_qr_base64  # Your updated base64 function
from pathlib import Path

logger = logging.getLogger(__name__)

def generate_invoice_pdf(service_data):
    return _generate_pdf(service_data, template_name="invoice_pdf.html", doc_type="invoice")

def generate_purchase_order_pdf(service_data):
    return _generate_pdf(service_data, template_name="purchase_order_pdf.html", doc_type="purchase_order")

def _generate_pdf(service_data, template_name, doc_type="invoice"):
    """
    Shared PDF generation using WeasyPrint
    """
    try:
        # Generate custom QR code (colored with logo)
        payment_data = f"Invoice {service_data.get('invoice_number', service_data.get('po_number', ''))}"
        logo_path = str(Path("static/images/logo.png"))  # Adjust if your logo is elsewhere
        if Path(logo_path).exists():
            custom_qr_b64 = generate_qr_base64(
                payment_data,
                logo_path=logo_path,
                fill_color="#0d6efd",      # Primary blue
                back_color="white"
            )
        else:
            custom_qr_b64 = generate_qr_base64(payment_data, fill_color="black", back_color="white")

        # Optional: FBR QR (if you generate it separately)
        fbr_qr_code = None  # Set this if you have FBR QR logic
        fbr_compliant = bool(service_data.get('seller_ntn'))

        # Full context for template
        context = {
            "data": service_data,
            "custom_qr_b64": custom_qr_b64,
            "fbr_qr_code": fbr_qr_code,
            "fbr_compliant": fbr_compliant,
            "currency_symbol": service_data.get('currency_symbol', '₹'),  # or PKR ₹
            "preview": False,  # Important: not preview mode
        }

        # Render the correct template
        rendered_html = render_template(template_name, **context)

        # Base URL is critical for static assets (logo, etc.)
        base_url = request.url_root if request else "http://localhost:5000/"

        # Generate PDF
        pdf_bytes = generate_pdf(rendered_html, base_url=base_url)

        logger.info(f"✅ {doc_type.capitalize()} PDF generated: {len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"PDF generation failed for {doc_type}: {e}", exc_info=True)
        # Fallback error PDF
        error_html = f"""
        <html><body style="font-family:Arial;padding:50px;text-align:center;">
        <h2>PDF Generation Error</h2>
        <p>{str(e)}</p>
        <p>Please contact support.</p>
        </body></html>
        """
        return generate_pdf(error_html, base_url="http://localhost:5000/")
