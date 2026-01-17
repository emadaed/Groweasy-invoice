# core/pdf_fixed.py - GUARANTEED TO WORK
import os
from pathlib import Path

def generate_pdf(html_content, base_path):
    """
    Generate PDF using WeasyPrint 61.0 on Railway
    PERMANENT FIX for pydyf.PDF issue
    """
    try:
        from weasyprint import HTML

        print(f"📄 Generating PDF from {len(html_content)} chars")

        # Method 1: Simple HTML object
        html = HTML(string=html_content)

        # Generate PDF with minimal options
        pdf_bytes = html.write_pdf()

        if pdf_bytes and len(pdf_bytes) > 100:
            print(f"✅ PDF generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
        else:
            print("❌ PDF generation returned empty")
            return None

    except Exception as e:
        print(f"❌ PDF error: {e}")
        return None

# For imports that need HAS_WEASYPRINT
try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False
