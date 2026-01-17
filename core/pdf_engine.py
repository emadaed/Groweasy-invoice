# core/pdf_engine.py - FIXED VERSION WITH DEBUG
import os
import tempfile

# Check if WeasyPrint is available
try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
    print("✅ WeasyPrint imported successfully")
except ImportError as e:
    HAS_WEASYPRINT = False
    print(f"❌ WeasyPrint import error: {e}")

def generate_pdf(html_content, base_path):
    """Generate PDF - Debug version to find empty PDF issue"""
    print(f"📄 PDF Generation Started")
    print(f"📄 HTML length: {len(html_content)} characters")

    if not HAS_WEASYPRINT:
        print("❌ WeasyPrint not available")
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

        # Create HTML object
        html = HTML(string=html_content)

        # Generate PDF
        print("🔄 Generating PDF...")
        pdf_bytes = html.write_pdf()

        # Clean up temp file
        os.unlink(temp_file)

        if pdf_bytes:
            print(f"✅ PDF generated successfully: {len(pdf_bytes)} bytes")

            # Save PDF to temp file for inspection
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
                f.write(pdf_bytes)
                print(f"📄 PDF saved to: {f.name} for inspection")
                # Temp file will be cleaned up by OS

            return pdf_bytes
        else:
            print("❌ PDF generation returned empty bytes")
            return None

    except Exception as e:
        print(f"❌ PDF error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None
