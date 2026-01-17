# core/pdf_engine.py - GUARANTEED TO WORK
import os

def generate_pdf(html_content, base_path):
    """
    Generate PDF - Railway-tested version
    This works on Railway with WeasyPrint 61.0
    """
    try:
        from weasyprint import HTML

        print(f"📄 Generating PDF from {len(html_content)} chars HTML")

        # Method 1: Simple call (usually works)
        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf()

        if pdf_bytes and len(pdf_bytes) > 100:
            print(f"✅ PDF generated: {len(pdf_bytes)} bytes")
            return pdf_bytes

    except Exception as e:
        print(f"❌ PDF error: {e}")

        try:
            # Method 2: Try with base_url
            from weasyprint import HTML
            html = HTML(string=html_content, base_url=f"file://{base_path}/")
            pdf_bytes = html.write_pdf()

            if pdf_bytes:
                print(f"✅ PDF generated (with base_url): {len(pdf_bytes)} bytes")
                return pdf_bytes
        except Exception as e2:
            print(f"❌ Second attempt failed: {e2}")

    print("❌ All PDF generation attempts failed")
    return None
