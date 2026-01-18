# core/pdf_engine.py - Simplified ReportLab-only version
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
import logging

logger = logging.getLogger(__name__)
HAS_WEASYPRINT = False  # Always False since we removed it

def generate_pdf(html_content, root_path=None, title="Invoice"):
    """Generate PDF using ReportLab"""
    try:
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

        # Simple HTML to text conversion
        import re
        from html import unescape

        # Basic HTML cleanup
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

        logger.info("PDF generated with ReportLab")
        return buffer.getvalue()

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        # Return minimal error PDF
        return generate_error_pdf(f"PDF Error: {str(e)}")

def generate_error_pdf(message):
    """Generate simple error PDF"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 700, "Invoice System")
    c.setFont("Helvetica", 12)
    c.drawString(100, 650, "PDF generation failed.")
    c.drawString(100, 625, "Please try again or contact support.")

    # Add timestamp
    c.setFont("Helvetica", 10)
    c.drawString(100, 100, f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
