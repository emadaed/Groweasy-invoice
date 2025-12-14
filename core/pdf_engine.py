# core/pdf_engine.py

import os
from pathlib import Path

# Check if WeasyPrint is available
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False
    print("⚠️ WeasyPrint not installed. PDF generation will be disabled.")


def generate_pdf(html_content, app_root_path=None):
    """
    Generate PDF from HTML with proper CSS loading.

    Args:
        html_content: Rendered HTML string
        app_root_path: Flask app.root_path for locating static files

    Returns:
        PDF bytes
    """
    if not HAS_WEASYPRINT:
        raise RuntimeError("WeasyPrint is not installed")

    try:
        # Determine static directory path
        if app_root_path:
            static_dir = os.path.join(app_root_path, 'static')
        else:
            # Fallback: Try to find static relative to this file
            current_dir = Path(__file__).parent.absolute()
            static_dir = current_dir.parent / 'static'
            static_dir = str(static_dir)

        # Verify static directory exists
        if not os.path.exists(static_dir):
            print(f"⚠️ Static directory not found at {static_dir}")
            print("⚠️ Generating PDF without external CSS")
            return HTML(string=html_content).write_pdf()

        # Define CSS file paths
        css_dir = os.path.join(static_dir, 'css')
        bootstrap_path = os.path.join(css_dir, 'bootstrap.min.css')
        invoice_path = os.path.join(css_dir, 'invoice.min.css')

        # Font configuration for WeasyPrint
        font_config = FontConfiguration()

        # Load CSS stylesheets
        css_stylesheets = []

        # Add inline CSS for PDF-specific styling
        pdf_css = CSS(string='''
            @page {
                size: A4;
                margin: 1cm;
            }

            body {
                font-family: Arial, Helvetica, sans-serif;
                font-size: 10pt;
                line-height: 1.4;
                color: #333;
            }

            /* Hide preview-only elements */
            .btn, button, .alert, form, .preview-only {
                display: none !important;
            }

            /* Ensure tables render properly */
            table {
                border-collapse: collapse;
                width: 100%;
            }

            /* Print-friendly colors */
            .bg-primary, .bg-success, .bg-info {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }

            /* Prevent page breaks inside elements */
            .invoice-container, table, tr {
                page-break-inside: avoid;
            }

            /* QR codes should maintain size */
            img[alt*="QR"] {
                width: 70px !important;
                height: 70px !important;
            }
        ''', font_config=font_config)
        css_stylesheets.append(pdf_css)

        # Load Bootstrap CSS if available
        if os.path.exists(bootstrap_path):
            try:
                css_stylesheets.append(CSS(filename=bootstrap_path, font_config=font_config))
                print(f"✅ Loaded Bootstrap CSS from {bootstrap_path}")
            except Exception as e:
                print(f"⚠️ Error loading Bootstrap CSS: {e}")
        else:
            print(f"⚠️ Bootstrap CSS not found at {bootstrap_path}")

        # Load Invoice CSS if available
        if os.path.exists(invoice_path):
            try:
                css_stylesheets.append(CSS(filename=invoice_path, font_config=font_config))
                print(f"✅ Loaded Invoice CSS from {invoice_path}")
            except Exception as e:
                print(f"⚠️ Error loading Invoice CSS: {e}")
        else:
            print(f"⚠️ Invoice CSS not found at {invoice_path}")

        # Create base_url for resolving relative paths in HTML
        # Use file:// protocol with the static directory
        base_url = f'file://{os.path.abspath(static_dir)}/'
        print(f"📂 Using base_url: {base_url}")

        # Generate PDF
        print(f"📄 Generating PDF with {len(css_stylesheets)} stylesheets...")

        html_doc = HTML(
            string=html_content,
            base_url=base_url
        )

        pdf_bytes = html_doc.write_pdf(
            stylesheets=css_stylesheets if css_stylesheets else None,
            font_config=font_config
        )

        print(f"✅ PDF generated successfully ({len(pdf_bytes):,} bytes)")
        return pdf_bytes

    except Exception as e:
        print(f"❌ PDF generation error: {e}")

        # Log to Sentry if available
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except ImportError:
            pass

        # Attempt fallback generation
        print("⚠️ Attempting fallback PDF generation without external CSS...")
        try:
            # Add minimal inline CSS for fallback
            fallback_css = CSS(string='''
                @page { size: A4; margin: 1cm; }
                body { font-family: Arial, sans-serif; font-size: 10pt; }
                table { border-collapse: collapse; width: 100%; }
                td, th { padding: 4px; border: 1px solid #ddd; }
                .btn, button, form { display: none; }
            ''')
            print(f"DEBUG: Final PDF size: {len(pdf_bytes)} bytes")
            if len(pdf_bytes) < 5000:
                print("WARNING: PDF suspiciously small — possible blank!")

            return HTML(string=html_content).write_pdf(stylesheets=[fallback_css])
        except Exception as fallback_error:
            print(f"❌ Fallback PDF generation also failed: {fallback_error}")
            raise


def generate_pdf_from_url(url, app_root_path=None):
    """
    Generate PDF from a URL (alternative method).

    Args:
        url: URL to render as PDF
        app_root_path: Flask app.root_path for locating static files

    Returns:
        PDF bytes
    """
    if not HAS_WEASYPRINT:
        raise RuntimeError("WeasyPrint is not installed")

    try:
        font_config = FontConfiguration()
        return HTML(url=url).write_pdf(font_config=font_config)
    except Exception as e:
        print(f"❌ PDF generation from URL failed: {e}")
        raise
