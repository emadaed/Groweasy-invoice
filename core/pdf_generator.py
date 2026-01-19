# core/pdf_generator.py - Final Working Version (WeasyPrint + Colored QR)

import logging
from datetime import datetime
from flask import render_template, request
from core.pdf_engine import generate_pdf
from core.qr_engine import generate_qr_base64
from pathlib import Path

logger = logging.getLogger(__name__)

def generate_invoice_pdf(service_data):
    """Generate sales invoice PDF"""
    return _generate_document_pdf(service_data, template="invoice_pdf.html")

def generate_purchase_order_pdf(service_data):
    """Generate purchase order PDF"""
    return _generate_document_pdf(service_data, template="purchase_order_pdf.html")

def _generate_document_pdf(service_data, template):
    """
    Shared logic for both invoice and PO PDFs using WeasyPrint
    """
    try:
        # Generate colored QR with logo
        doc_number = service_data.get('invoice_number') or service_data.get('po_number', 'DOC')
        payment_data = f"GrowEasy Payment - {doc_number}"

        logo_path = "static/images/logo.png"
        logo_exists = Path(logo_path).exists()

        custom_qr_b64 = generate_qr_base64(
            data=payment_data,
            logo_path=logo_path if logo_exists else None,
            fill_color="#0d6efd",    # Beautiful blue
            back_color="white"
        )

        # Context for template
        context = {
            "data": service_data,
            "custom_qr_b64": custom_qr_b64,
            "fbr_qr_code": None,  # Add your FBR QR logic here if needed later
            "fbr_compliant": bool(service_data.get('seller_ntn')),
            "currency_symbol": service_data.get('currency_symbol', 'Rs.'),
            "preview": False,
        }

        # Render HTML template
        rendered_html = render_template(template, **context)

        # Critical: base_url for static files and images
        base_url = request.url_root if hasattr(request, 'url_root') else "https://your-app.up.railway.app/"

        # Generate PDF with WeasyPrint
        pdf_bytes = generate_pdf(rendered_html, base_url=base_url)

        if len(pdf_bytes) < 5000:
            logger.warning("PDF generated but very small — possible rendering issue")

        logger.info(f"PDF generated successfully: {len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        # Return simple error PDF
        error_html = f"""
        <html><body style="font-family:Arial;padding:50px;text-align:center;">
            <h2>PDF Generation Error</h2>
            <p>{str(e)}</p>
            <p>Please try again later.</p>
        </body></html>
        """
        return generate_pdf(error_html, base_url="http://localhost/")
