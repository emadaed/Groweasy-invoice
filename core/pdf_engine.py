"""
PDF Generation Engine for Purchase Orders and Invoices
Uses ReportLab with proper HTML/CSS parsing
"""
import io
import re
import logging
from datetime import datetime
from html import unescape
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import base64

logger = logging.getLogger(__name__)

# Register default fonts (optional - for better typography)
try:
    pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
except:
    pass  # Use default fonts if custom not available

def generate_pdf(html_content, root_path=None, title="Document", doc_type="invoice"):
    """
    Generate properly formatted PDF for invoices/purchase orders
    """
    try:
        # Parse HTML to extract structured data
        parsed_data = parse_html_for_pdf(html_content)

        # Create PDF based on document type
        if doc_type == "purchase_order":
            return create_purchase_order_pdf(parsed_data)
        else:
            return create_invoice_pdf(parsed_data)

    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return create_error_pdf(str(e))

def parse_html_for_pdf(html_content):
    """
    Extract structured data from HTML for PDF generation
    """
    # Remove CSS styles and scripts
    html_content = re.sub(r'<style.*?>.*?</style>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<script.*?>.*?</script>', '', html_content, flags=re.DOTALL)

    # Extract title
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "Document"

    # Extract PO number
    po_match = re.search(r'PURCHASE ORDER PO #\s*([^<]+)', html_content)
    po_number = po_match.group(1).strip() if po_match else ""

    # Extract supplier info
    supplier_info = {}
    to_match = re.search(r'TO:\s*([^<]+)<br[^>]*>([^<]+)<br[^>]*>([^<]+)<br[^>]*>Phone:\s*([^<]+)<br[^>]*>Email:\s*([^<]+)', html_content)
    if to_match:
        supplier_info = {
            'name': to_match.group(1).strip(),
            'address': f"{to_match.group(2).strip()}, {to_match.group(3).strip()}",
            'phone': to_match.group(4).strip(),
            'email': to_match.group(5).strip()
        }

    # Extract dates
    po_date_match = re.search(r'PO Date:\s*([^<]+)', html_content)
    delivery_date_match = re.search(r'Delivery Date:\s*([^<]+)', html_content)

    # Extract table data
    items = []
    # Look for table rows with item data
    table_match = re.search(r'<tbody>(.*?)</tbody>', html_content, re.DOTALL)
    if table_match:
        rows = re.findall(r'<tr>(.*?)</tr>', table_match.group(1), re.DOTALL)
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cols) >= 5:
                items.append({
                    'sr': unescape(cols[0]).strip(),
                    'description': unescape(cols[1]).strip(),
                    'sku': unescape(cols[2]).strip(),
                    'supplier': unescape(cols[3]).strip(),
                    'qty': unescape(cols[4]).strip(),
                    'unit_price': unescape(cols[5]).strip(),
                    'total': unescape(cols[6]).strip()
                })

    # Extract totals
    subtotal_match = re.search(r'Subtotal:\s*([^<]+)', html_content)
    tax_match = re.search(r'Tax\s*\([^)]+\):\s*([^<]+)', html_content)
    total_match = re.search(r'GRAND TOTAL:\s*([^<]+)', html_content)

    # Extract terms
    payment_terms_match = re.search(r'Payment Terms:\s*([^<]+)', html_content)
    shipping_terms_match = re.search(r'Shipping Terms:\s*([^<]+)', html_content)

    return {
        'title': title,
        'po_number': po_number,
        'supplier': supplier_info,
        'po_date': po_date_match.group(1).strip() if po_date_match else datetime.now().strftime('%Y-%m-%d'),
        'delivery_date': delivery_date_match.group(1).strip() if delivery_date_match else '',
        'items': items,
        'subtotal': subtotal_match.group(1).strip() if subtotal_match else '0.00',
        'tax': tax_match.group(1).strip() if tax_match else '0.00',
        'grand_total': total_match.group(1).strip() if total_match else '0.00',
        'payment_terms': payment_terms_match.group(1).strip() if payment_terms_match else 'Net 30',
        'shipping_terms': shipping_terms_match.group(1).strip() if shipping_terms_match else 'FOB Destination'
    }

def create_purchase_order_pdf(data):
    """Create formatted purchase order PDF"""
    buffer = io.BytesIO()

    # Create document with margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0d6efd'),
        spaceAfter=12
    )

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0d6efd'),
        spaceAfter=6
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )

    # Title
    story.append(Paragraph("PURCHASE ORDER", title_style))
    story.append(Paragraph(f"PO #: {data['po_number']}", header_style))
    story.append(Spacer(1, 0.2*inch))

    # Two-column layout for header
    header_data = [
        [
            Paragraph("<b>TO:</b>", normal_style),
            Paragraph(f"<b>PO Date:</b> {data['po_date']}", normal_style)
        ],
        [
            Paragraph(f"{data['supplier'].get('name', '')}<br/>{data['supplier'].get('address', '')}<br/>Phone: {data['supplier'].get('phone', '')}<br/>Email: {data['supplier'].get('email', '')}", normal_style),
            Paragraph(f"<b>Delivery Date:</b> {data['delivery_date']}<br/><b>Status:</b> PENDING", normal_style)
        ]
    ]

    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#e8f4fd')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f8f9fa')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # Items table
    if data['items']:
        table_data = [['#', 'Description', 'SKU', 'Supplier', 'Qty', 'Unit Price', 'Total']]

        for item in data['items']:
            table_data.append([
                item.get('sr', ''),
                item.get('description', ''),
                item.get('sku', ''),
                item.get('supplier', ''),
                item.get('qty', ''),
                item.get('unit_price', ''),
                item.get('total', '')
            ])

        # Add totals row
        table_data.append(['', '', '', '', '', '<b>Subtotal:</b>', f"<b>{data['subtotal']}</b>"])
        table_data.append(['', '', '', '', '', '<b>Tax:</b>', f"<b>{data['tax']}</b>"])
        table_data.append(['', '', '', '', '', '<b>GRAND TOTAL:</b>', f"<b>{data['grand_total']}</b>"])

        items_table = Table(table_data, colWidths=[0.3*inch, 2*inch, 1*inch, 1.2*inch, 0.5*inch, 1*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -4), 0.5, colors.grey),
            ('ALIGN', (4, 1), (6, -4), 'RIGHT'),
            ('FONTNAME', (5, -3), (6, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#f8f9fa')),
            ('LINEABOVE', (0, -3), (-1, -3), 1, colors.black),
        ]))

        story.append(items_table)
        story.append(Spacer(1, 0.3*inch))

    # Terms and conditions
    story.append(Paragraph("TERMS & CONDITIONS", header_style))

    terms_data = [
        [Paragraph(f"<b>Payment Terms:</b> {data['payment_terms']}", normal_style)],
        [Paragraph(f"<b>Shipping Terms:</b> {data['shipping_terms']}", normal_style)],
        [Paragraph("<b>Delivery Method:</b> Pickup", normal_style)]
    ]

    terms_table = Table(terms_data, colWidths=[7*inch])
    terms_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#6c757d')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))

    story.append(terms_table)
    story.append(Spacer(1, 0.5*inch))

    # Signatures
    sig_data = [
        [
            Paragraph("_________________________<br/><b>Authorized Signature</b>", normal_style),
            Paragraph("_________________________<br/><b>Supplier Acknowledgment</b>", normal_style)
        ]
    ]

    sig_table = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
    story.append(sig_table)

    # Footer with QR code space
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"Scan to verify PO #: {data['po_number']}",
                          ParagraphStyle('Footer', parent=styles['Italic'], fontSize=9, alignment=TA_CENTER)))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def create_invoice_pdf(data):
    """Create formatted invoice PDF (similar structure)"""
    # Similar to purchase order but with invoice-specific formatting
    return create_purchase_order_pdf(data)  # For now, reuse same format

def create_error_pdf(error_msg):
    """Create error PDF"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, "PDF Generation Error")

    c.setFont("Helvetica", 12)
    c.drawString(2*cm, 25*cm, "Failed to generate properly formatted PDF.")

    # Wrap error message
    c.setFont("Helvetica", 10)
    y = 23*cm
    for line in wrap_text(error_msg, 80):
        c.drawString(2*cm, y, line)
        y -= 0.6*cm

    c.setFont("Helvetica", 9)
    c.drawString(2*cm, 2*cm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def wrap_text(text, width):
    """Wrap text to specified width"""
    import textwrap
    return textwrap.wrap(text, width)

# Backward compatibility
HAS_WEASYPRINT = False
