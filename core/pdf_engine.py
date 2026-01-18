"""
PDF Generation Engine with Multiple Fallbacks
"""
import os
import io
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Feature detection
HAS_WEASYPRINT = False
HAS_REPORTLAB = True  # Always available

try:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    HAS_WEASYPRINT = True
    logger.info("✅ WeasyPrint available")
except ImportError:
    logger.warning("⚠️ WeasyPrint not available")

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
    logger.info("✅ ReportLab available")
except ImportError:
    HAS_REPORTLAB = False
    logger.warning("⚠️ ReportLab not available")


def generate_pdf(html_content, root_path=None, title="Document"):
    """
    Generate PDF with multiple fallback strategies
    Returns: bytes of PDF file
    """
    # Strategy 1: Try WeasyPrint first (best quality)
    if HAS_WEASYPRINT:
        try:
            return generate_with_weasyprint(html_content)
        except Exception as e:
            logger.error(f"WeasyPrint failed: {e}")
            # Fall through to next strategy

    # Strategy 2: Try ReportLab (good quality)
    if HAS_REPORTLAB:
        try:
            return generate_with_reportlab(html_content, title)
        except Exception as e:
            logger.error(f"ReportLab failed: {e}")

    # Strategy 3: Generate error PDF
    return generate_error_pdf(f"Failed to generate PDF. {title}")


def generate_with_weasyprint(html_content):
    """Generate PDF using WeasyPrint"""
    font_config = FontConfiguration()
    html = HTML(string=html_content)
    pdf_bytes = html.write_pdf(font_config=font_config)
    logger.info("PDF generated with WeasyPrint")
    return pdf_bytes


def generate_with_reportlab(html_content, title="Invoice"):
    """Generate PDF using ReportLab (fallback)"""
    buffer = io.BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )

    # Prepare content
    styles = getSampleStyleSheet()
    story = []

    # Add title
    title_style = styles['Heading1']
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.25*inch))

    # Convert HTML to simple paragraphs
    import re
    from html import unescape

    # Clean HTML
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split('. ') if p.strip()]

    for para in paragraphs[:50]:  # Limit to 50 paragraphs
        story.append(Paragraph(para, styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

    # Add footer
    story.append(Spacer(1, 0.5*inch))
    footer = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    story.append(Paragraph(footer, styles['Italic']))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    logger.info("PDF generated with ReportLab (fallback)")
    return buffer.getvalue()


def generate_error_pdf(message):
    """Generate a simple error PDF"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 700, "PDF Generation Error")

    c.setFont("Helvetica", 12)
    c.drawString(100, 650, "The system encountered an error while generating the PDF.")

    c.setFont("Helvetica", 10)
    # Wrap long message
    y = 600
    for line in wrap_text(message, 80):
        c.drawString(100, y, line)
        y -= 20

    c.setFont("Helvetica", 10)
    c.drawString(100, 100, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def wrap_text(text, width):
    """Wrap text to specified width"""
    import textwrap
    return textwrap.wrap(text, width)


# Compatibility function for existing code
def generate_pdf_simple(html_content, root_path=None):
    """Simple wrapper for backward compatibility"""
    return generate_pdf(html_content, root_path, "Invoice")
