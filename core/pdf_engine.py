# core/pdf_engine.py - EMERGENCY FIX
import os
import tempfile

# Try multiple PDF libraries
def generate_pdf(html_content, base_path):
    """Generate PDF using available library"""
    print(f"📄 PDF Generation - HTML length: {len(html_content)} chars")

    # Try WeasyPrint first
    try:
        from weasyprint import HTML
        print("✅ Using WeasyPrint")
        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf()
        if pdf_bytes and len(pdf_bytes) > 1000:
            print(f"✅ WeasyPrint PDF: {len(pdf_bytes)} bytes")
            return pdf_bytes
    except Exception as e:
        print(f"⚠️ WeasyPrint failed: {e}")

    # Try xhtml2pdf (wkhtmltopdf alternative)
    try:
        from xhtml2pdf import pisa
        import io
        print("✅ Using xhtml2pdf")
        result = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=result)
        if not pisa_status.err:
            pdf_bytes = result.getvalue()
            if pdf_bytes and len(pdf_bytes) > 1000:
                print(f"✅ xhtml2pdf PDF: {len(pdf_bytes)} bytes")
                return pdf_bytes
    except ImportError:
        print("⚠️ xhtml2pdf not available")

    # Fallback: Create HTML file for manual conversion
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = f.name
            print(f"📄 HTML saved to: {html_file} (fallback)")

        # Return minimal PDF with error message
        pdf_fallback = create_minimal_pdf(f"PDF generation failed. HTML saved to: {html_file}")
        return pdf_fallback
    except Exception as e:
        print(f"❌ All PDF methods failed: {e}")
        return None

def create_minimal_pdf(message):
    """Create minimal PDF with error message"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from io import BytesIO

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(100, 750, "PDF Generation Failed")
        c.drawString(100, 730, message)
        c.drawString(100, 710, "Please check server logs.")
        c.save()

        pdf_bytes = buffer.getvalue()
        print(f"⚠️ Created fallback PDF: {len(pdf_bytes)} bytes")
        return pdf_bytes
    except:
        return None

# For compatibility
try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except:
    HAS_WEASYPRINT = False
