# core/pdf_engine.py - FIXED VERSION
import os
import sys
from pathlib import Path

# Try to import WeasyPrint
HAS_WEASYPRINT = False
try:
    from weasyprint import HTML, CSS
    HAS_WEASYPRINT = True
    print("✅ WeasyPrint available")
except ImportError as e:
    print(f"⚠️ WeasyPrint not available: {e}")

def generate_pdf(html_content, base_path):
    """
    Generate PDF from HTML content
    Returns: bytes or None on failure
    """
    try:
        if not HAS_WEASYPRINT:
            print("❌ WeasyPrint not installed")
            return None

        # Convert base_path to Path object
        base_path = Path(base_path)
        static_path = base_path / 'static'

        print(f"📂 Base path: {base_path}")
        print(f"📂 Static path: {static_path}")

        # Create HTML object
        html = HTML(string=html_content, base_url=f'file://{base_path}/')

        # Load CSS files with error handling
        stylesheets = []

        # 1. Bootstrap CSS
        bootstrap_css = static_path / 'css' / 'bootstrap.min.css'
        if bootstrap_css.exists():
            try:
                css = CSS(filename=str(bootstrap_css))
                stylesheets.append(css)
                print(f"✅ Loaded Bootstrap CSS: {bootstrap_css}")
            except Exception as e:
                print(f"⚠️ Failed to load Bootstrap CSS: {e}")
        else:
            print(f"⚠️ Bootstrap CSS not found: {bootstrap_css}")

        # 2. Invoice CSS
        invoice_css = static_path / 'css' / 'invoice.min.css'
        if invoice_css.exists():
            try:
                css = CSS(filename=str(invoice_css))
                stylesheets.append(css)
                print(f"✅ Loaded Invoice CSS: {invoice_css}")
            except Exception as e:
                print(f"⚠️ Failed to load Invoice CSS: {e}")
        else:
            print(f"⚠️ Invoice CSS not found: {invoice_css}")

        # 3. Custom CSS if exists
        custom_css = static_path / 'css' / 'custom.css'
        if custom_css.exists():
            try:
                css = CSS(filename=str(custom_css))
                stylesheets.append(css)
                print(f"✅ Loaded Custom CSS: {custom_css}")
            except Exception as e:
                print(f"⚠️ Failed to load Custom CSS: {e}")

        print(f"📄 Generating PDF with {len(stylesheets)} stylesheets...")

        # Generate PDF with error handling for pydyf compatibility
        try:
            # Method 1: Try with stylesheets
            pdf_bytes = html.write_pdf(stylesheets=stylesheets)
            print(f"✅ PDF generated successfully: {len(pdf_bytes)} bytes")
            return pdf_bytes
        except TypeError as e:
            if "PDF.__init__() takes 1 positional argument but" in str(e):
                print("⚠️ pydyf compatibility issue detected, trying without stylesheets...")
                # Method 2: Try without stylesheets
                try:
                    pdf_bytes = html.write_pdf()
                    print(f"✅ PDF generated without stylesheets: {len(pdf_bytes)} bytes")
                    return pdf_bytes
                except Exception as e2:
                    print(f"❌ PDF generation without stylesheets failed: {e2}")

                    # Method 3: Try with inline CSS
                    print("⚠️ Attempting fallback with basic styling...")
                    try:
                        # Add basic CSS inline
                        basic_css = """
                        <style>
                        body { font-family: Arial, sans-serif; margin: 20px; }
                        table { width: 100%; border-collapse: collapse; }
                        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                        th { background-color: #f2f2f2; }
                        .total-row { font-weight: bold; }
                        </style>
                        """
                        html_with_css = basic_css + html_content
                        html_fallback = HTML(string=html_with_css)
                        pdf_bytes = html_fallback.write_pdf()
                        print(f"✅ PDF generated with inline CSS: {len(pdf_bytes)} bytes")
                        return pdf_bytes
                    except Exception as e3:
                        print(f"❌ All PDF generation attempts failed: {e3}")
                        return None
            else:
                print(f"❌ PDF generation error: {e}")
                return None
        except Exception as e:
            print(f"❌ PDF generation error: {e}")
            return None

    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        return None

def generate_pdf_fallback(html_content):
    """
    Fallback PDF generation using fpdf2 if WeasyPrint fails
    """
    try:
        from fpdf import FPDF
        import tempfile

        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Add HTML content as text (very basic)
        lines = html_content.replace('<br>', '\n').replace('</p>', '\n')
        # Remove HTML tags (basic)
        import re
        lines = re.sub(r'<[^>]+>', '', lines)

        for line in lines.split('\n'):
            if line.strip():
                pdf.cell(200, 10, txt=line[:100], ln=1)

        # Save to bytes
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        print(f"✅ Fallback PDF generated: {len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        print(f"❌ Fallback PDF also failed: {e}")
        return None
