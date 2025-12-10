import os
from weasyprint import HTML, CSS

HAS_WEAZYPRINT = True

def generate_pdf(html_content, app_root_path=None):
    """Generate PDF from HTML with proper CSS loading"""
    try:
        # Get static directory path
        if app_root_path:
            static_dir = os.path.join(app_root_path, 'static')
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            static_dir = os.path.join(os.path.dirname(current_dir), 'static')

        if not os.path.exists(static_dir):
            print(f"⚠️ Static directory not found at {static_dir}")
            return HTML(string=html_content).write_pdf()

        # Create base_url for WeasyPrint
        base_url = f'file://{os.path.abspath(static_dir)}/'
        print(f"📂 Using base_url: {base_url}")

        # Load CSS files
        css_stylesheets = []
        bootstrap_path = os.path.join(static_dir, 'css', 'bootstrap.min.css')
        invoice_path = os.path.join(static_dir, 'css', 'invoice.min.css')

        if os.path.exists(bootstrap_path):
            try:
                css_stylesheets.append(CSS(filename=bootstrap_path))
                print(f"✅ Loaded Bootstrap CSS")
            except Exception as e:
                print(f"⚠️ Error loading bootstrap CSS: {e}")
        else:
            print(f"⚠️ Bootstrap CSS not found at {bootstrap_path}")

        if os.path.exists(invoice_path):
            try:
                css_stylesheets.append(CSS(filename=invoice_path))
                print(f"✅ Loaded Invoice CSS")
            except Exception as e:
                print(f"⚠️ Error loading invoice CSS: {e}")
        else:
            print(f"⚠️ Invoice CSS not found at {invoice_path}")

        # Generate PDF with stylesheets
        print(f"📄 Generating PDF with {len(css_stylesheets)} stylesheets...")
        pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf(
            stylesheets=css_stylesheets if css_stylesheets else None
        )

        print(f"✅ PDF generated successfully ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    except Exception as e:
        print(f"❌ PDF generation error: {e}")
        import traceback
        traceback.print_exc()

        # Log to Sentry if available
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except:
            pass

        # Fallback: Generate basic PDF without external CSS
        print("⚠️ Falling back to basic PDF generation without external CSS")
        try:
            return HTML(string=html_content).write_pdf()
        except Exception as fallback_error:
            print(f"❌ Even fallback PDF generation failed: {fallback_error}")
            raise
