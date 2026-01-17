import os

# Check if WeasyPrint is available
try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

def generate_pdf(html_content, base_path):
    """Generate PDF - Simple working version"""
    if not HAS_WEASYPRINT:
        print("❌ WeasyPrint not available")
        return None

    try:
        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf()

        if pdf_bytes:
            print(f"✅ PDF generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
        else:
            print("❌ PDF generation returned empty")
            return None

    except Exception as e:
        print(f"❌ PDF error: {e}")
        return None
