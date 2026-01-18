# core/pdf_engine.py - COMPATIBLE VERSION
import os
import tempfile

def generate_pdf(html_content, base_path):
    """Generate PDF - Compatible with WeasyPrint 61.0"""
    print(f"📄 PDF Generation Started")
    print(f"📄 HTML length: {len(html_content)} characters")

    try:
        from weasyprint import HTML, CSS
        HAS_WEASYPRINT = True
    except ImportError as e:
        print(f"❌ WeasyPrint import error: {e}")
        return None

    try:
        # Save HTML to temp file for debugging
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_file = f.name
            print(f"📄 HTML saved to: {temp_file}")

        # Check if HTML is valid
        if len(html_content) < 100:
            print("❌ HTML content too short (likely empty)")
            os.unlink(temp_file)
            return None

        # Create HTML object - SIMPLIFIED for compatibility
        html = HTML(string=html_content)

        # Generate PDF with minimal options
        print("🔄 Generating PDF...")
        pdf_bytes = html.write_pdf()

        # Clean up temp file
        os.unlink(temp_file)

        if pdf_bytes and len(pdf_bytes) > 100:
            print(f"✅ PDF generated successfully: {len(pdf_bytes)} bytes")
            return pdf_bytes
        else:
            print("❌ PDF generation returned empty or too small")
            return None

    except Exception as e:
        print(f"❌ PDF error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None

# For imports that need HAS_WEASYPRINT
try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
    print("✅ WeasyPrint imported successfully")
except ImportError:
    HAS_WEASYPRINT = False
    print("❌ WeasyPrint not available")
