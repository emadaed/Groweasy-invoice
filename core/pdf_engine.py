"""
PDF Generation Engine - Fixed Version
Uses xhtml2pdf for proper HTML/CSS rendering
"""
import io
import logging
import tempfile
import base64
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to use xhtml2pdf (better HTML/CSS support)
try:
    from xhtml2pdf import pisa
    HAS_XHTML2PDF = True
    logger.info("✅ xhtml2pdf available")
except ImportError:
    HAS_XHTML2PDF = False
    logger.warning("⚠️ xhtml2pdf not available")

# Fallback to ReportLab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

HAS_WEASYPRINT = False  # We're not using WeasyPrint anymore

def generate_pdf(html_content, root_path=None, title="Invoice", doc_type="invoice"):
    """
    Generate PDF using xhtml2pdf (preserves HTML/CSS styling)
    """
    try:
        if HAS_XHTML2PDF:
            return generate_with_xhtml2pdf(html_content, root_path)
        elif HAS_REPORTLAB:
            return generate_fallback_pdf(f"Using fallback PDF. Install xhtml2pdf for better results.")
        else:
            return b"PDF generation not available. Install xhtml2pdf."
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return generate_error_pdf(str(e))

def generate_with_xhtml2pdf(html_content, root_path=None):
    """Generate PDF using xhtml2pdf (preserves HTML/CSS)"""
    buffer = io.BytesIO()

    # Fix CSS paths and add base styling
    html_content = fix_html_for_pdf(html_content)

    # Create PDF
    pisa_status = pisa.CreatePDF(
        src=io.StringIO(html_content),
        dest=buffer,
        encoding='UTF-8',
        link_callback=link_callback  # Handle images/links
    )

    if pisa_status.err:
        logger.error(f"xhtml2pdf error: {pisa_status.err}")
        return generate_fallback_pdf("PDF generation error")

    buffer.seek(0)
    return buffer.getvalue()

def fix_html_for_pdf(html_content):
    """Fix HTML/CSS for PDF generation"""
    import re

    # Add base64 encoded logo if exists
    logo_data = get_logo_base64()
    if logo_data:
        # Replace logo placeholder with actual logo
        html_content = re.sub(r'<img[^>]*logo[^>]*>',
                            f'<img src="{logo_data}" style="max-height: 80px;">',
                            html_content, flags=re.IGNORECASE)

    # Ensure CSS is inline (xhtml2pdf works better with inline styles)
    # Convert external styles to inline
    html_content = convert_css_to_inline(html_content)

    # Fix table borders
    html_content = re.sub(r'border:\s*none', 'border: 1px solid #ddd', html_content)

    # Add print-specific CSS
    print_css = """
    <style>
        @media print {
            body { margin: 0; padding: 0; }
            .no-print { display: none !important; }
            .page-break { page-break-after: always; }
            table { page-break-inside: avoid; }
            /* Ensure all content is visible */
            .container { width: 100% !important; margin: 0 !important; }
            /* Force visibility of all sections */
            .section, .row, [class*="col-"] {
                display: block !important;
                visibility: visible !important;
                opacity: 1 !important;
            }
        }
        /* Force show all elements in PDF */
        body * {
            visibility: visible !important;
        }
        /* Ensure tables are fully visible */
        table, th, td {
            border: 1px solid #ddd !important;
            border-collapse: collapse !important;
        }
        th, td {
            padding: 8px !important;
            text-align: left !important;
        }
        /* Make sure totals are visible */
        .totals-section {
            background-color: #f8f9fa !important;
            padding: 15px !important;
            border: 2px solid #0d6efd !important;
            margin-top: 20px !important;
        }
    </style>
    """

    # Insert CSS into head
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', print_css + '</head>')
    else:
        html_content = print_css + html_content

    return html_content

def convert_css_to_inline(html_content):
    """Convert external/internal CSS to inline styles (simplified)"""
    # This is a simplified version - in production, use a library like premailer
    import re

    # Extract style tags
    style_pattern = r'<style[^>]*>(.*?)</style>'
    styles = re.findall(style_pattern, html_content, re.DOTALL | re.IGNORECASE)

    # Simple CSS to inline conversion for common rules
    css_rules = {}
    for style in styles:
        # Extract rules
        rules = re.findall(r'([^{]+)\{([^}]+)\}', style)
        for selector, properties in rules:
            selector = selector.strip()
            if selector.startswith('.'):
                css_rules[selector[1:]] = properties.strip()

    # Apply inline styles (simplified - for critical elements)
    for class_name, properties in css_rules.items():
        if class_name in ['totals-section', 'table', 'table-bordered']:
            # Add style attribute to elements with this class
            pattern = f'class="[^"]*{class_name}[^"]*"'
            def add_style(match):
                return match.group(0)[:-1] + f' style="{properties}"' + '"'
            html_content = re.sub(pattern, add_style, html_content)

    return html_content

def link_callback(uri, rel):
    """
    Convert URIs to absolute paths for images
    """
    import os
    from urllib.parse import urlparse

    # Handle data URIs (base64 images)
    if uri.startswith("data:"):
        return uri

    # Handle local file paths
    if uri.startswith("file://"):
        return uri

    # Handle relative paths
    if not urlparse(uri).scheme:
        # Assume it's a relative path
        base_path = Path(__file__).parent.parent
        full_path = base_path / uri

        if full_path.exists():
            return str(full_path.absolute())

    return uri

def get_logo_base64():
    """Get company logo as base64"""
    try:
        logo_paths = [
            Path('static/images/logo.png'),
            Path('static/logo.png'),
            Path('static/images/company_logo.png'),
        ]

        for logo_path in logo_paths:
            if logo_path.exists():
                import base64
                with open(logo_path, 'rb') as f:
                    logo_data = base64.b64encode(f.read()).decode('utf-8')
                return f"data:image/png;base64,{logo_data}"

        # Create a simple logo placeholder
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (200, 80), color='#0d6efd')
        d = ImageDraw.Draw(img)

        # Try to add text
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()

        d.text((10, 10), "Company Logo", fill='white', font=font)

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        logo_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{logo_data}"

    except Exception as e:
        logger.warning(f"Could not load logo: {e}")
        return None

def generate_fallback_pdf(message):
    """Fallback PDF generation"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Invoice System")

    c.setFont("Helvetica", 12)
    c.drawString(100, 700, message)

    c.setFont("Helvetica", 10)
    c.drawString(100, 650, "Install xhtml2pdf for proper PDF generation:")
    c.drawString(100, 630, "pip install xhtml2pdf reportlab pillow")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def generate_error_pdf(error_msg):
    """Error PDF"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "PDF Generation Error")

    c.setFont("Helvetica", 12)
    y = 700
    for line in error_msg.split('\n'):
        if y < 100:
            c.showPage()
            y = 750
        c.drawString(100, y, line[:80])
        y -= 20

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
