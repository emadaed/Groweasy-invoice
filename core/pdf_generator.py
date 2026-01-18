# core/pdf_generator.py - SIMPLIFIED RELIABLE VERSION
import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

logger = logging.getLogger(__name__)

def generate_invoice_pdf(data):
    """Generate invoice PDF directly from data"""
    buffer = io.BytesIO()

    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Company Header
    story.append(Paragraph(f"<b>{data.get('company_name', 'Your Company')}</b>",
                          styles['Title']))
    story.append(Paragraph(data.get('company_address', ''), styles['Normal']))
    story.append(Paragraph(f"Phone: {data.get('company_phone', '')} | Email: {data.get('company_email', '')}",
                          styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Document Title
    story.append(Paragraph("<b>TAX INVOICE</b>",
                          styles['Heading1']))
    story.append(Paragraph(f"Invoice #: {data.get('invoice_number', '')}",
                          styles['Heading2']))
    story.append(Spacer(1, 0.2*inch))

    # Seller/Buyer Info
    buyer_info = [
        ["<b>Bill To:</b>", f"<b>Invoice Date:</b> {data.get('invoice_date', '')}"],
        [data.get('client_name', ''), f"<b>Due Date:</b> {data.get('due_date', '')}"],
        [data.get('client_address', ''), f"<b>Status:</b> {data.get('status', 'Pending')}"],
        [f"Phone: {data.get('client_phone', '')}", ""],
        [f"Email: {data.get('client_email', '')}", ""]
    ]

    buyer_table = Table(buyer_info, colWidths=[3.5*inch, 3.5*inch])
    buyer_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
        ('BACKGROUND', (1, 0), (1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(buyer_table)
    story.append(Spacer(1, 0.3*inch))

    # Items Table
    items = data.get('items', [])
    if items:
        table_data = [['#', 'Description', 'Qty', 'Unit Price', 'Total']]

        for idx, item in enumerate(items, 1):
            table_data.append([
                str(idx),
                item.get('name', ''),
                str(item.get('qty', 1)),
                f"Rs. {float(item.get('price', 0)):.2f}",
                f"Rs. {float(item.get('total', 0)):.2f}"
            ])

        # Add totals
        subtotal = data.get('subtotal', 0)
        tax = data.get('tax_amount', 0)
        discount = data.get('discount', 0)
        shipping = data.get('shipping', 0)
        grand_total = data.get('grand_total', 0)

        table_data.append(['', '', '', '<b>Subtotal:</b>', f"<b>Rs. {float(subtotal):.2f}</b>"])
        if tax and float(tax) > 0:
            table_data.append(['', '', '', f'<b>Tax ({data.get("sales_tax", 0)}%):</b>', f"<b>Rs. {float(tax):.2f}</b>"])
        if discount and float(discount) > 0:
            table_data.append(['', '', '', '<b>Discount:</b>', f"<b>-Rs. {float(discount):.2f}</b>"])
        if shipping and float(shipping) > 0:
            table_data.append(['', '', '', '<b>Shipping:</b>', f"<b>Rs. {float(shipping):.2f}</b>"])
        table_data.append(['', '', '', '<b>GRAND TOTAL:</b>', f"<b>Rs. {float(grand_total):.2f}</b>"])

        items_table = Table(table_data, colWidths=[0.5*inch, 3*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, len(items) + 1), 1, colors.grey),
            ('ALIGN', (2, 1), (4, len(items) + 1), 'RIGHT'),
            ('BACKGROUND', (0, -5), (-1, -1), colors.lightgrey),
            ('LINEABOVE', (0, -5), (-1, -5), 2, colors.black),
            ('FONTNAME', (3, -5), (4, -1), 'Helvetica-Bold'),
        ]))

        story.append(items_table)
        story.append(Spacer(1, 0.3*inch))

    # Notes
    if data.get('notes'):
        story.append(Paragraph("<b>Notes:</b>", styles['Heading2']))
        story.append(Paragraph(data['notes'], styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

    # Footer
    story.append(Paragraph("Thank you for your business!",
                          styles['Italic']))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                          styles['Italic']))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def generate_purchase_order_pdf(data):
    """Generate purchase order PDF"""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Company Header
    story.append(Paragraph(f"<b>{data.get('company_name', 'Your Company')}</b>",
                          styles['Title']))
    story.append(Paragraph(data.get('company_address', ''), styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Document Title
    story.append(Paragraph("<b>PURCHASE ORDER</b>", styles['Heading1']))
    story.append(Paragraph(f"PO #: {data.get('po_number', '')}", styles['Heading2']))
    story.append(Spacer(1, 0.2*inch))

    # Supplier Info
    supplier_info = [
        ["<b>Supplier:</b>", f"<b>PO Date:</b> {data.get('po_date', '')}"],
        [data.get('supplier_name', ''), f"<b>Delivery Date:</b> {data.get('delivery_date', '')}"],
        [data.get('supplier_address', ''), f"<b>Status:</b> {data.get('status', 'Pending')}"],
        [f"Phone: {data.get('supplier_phone', '')}", ""],
        [f"Email: {data.get('supplier_email', '')}", ""]
    ]

    supplier_table = Table(supplier_info, colWidths=[3.5*inch, 3.5*inch])
    supplier_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
        ('BACKGROUND', (1, 0), (1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(supplier_table)
    story.append(Spacer(1, 0.3*inch))

    # Items Table
    items = data.get('items', [])
    if items:
        table_data = [['#', 'Description', 'SKU', 'Qty', 'Unit Price', 'Total']]

        for idx, item in enumerate(items, 1):
            table_data.append([
                str(idx),
                item.get('name', ''),
                item.get('sku', ''),
                str(item.get('qty', 1)),
                f"Rs. {float(item.get('price', 0)):.2f}",
                f"Rs. {float(item.get('total', 0)):.2f}"
            ])

        # Add totals
        subtotal = data.get('subtotal', 0)
        tax = data.get('tax_amount', 0)
        shipping = data.get('shipping_cost', 0)
        grand_total = data.get('grand_total', 0)

        table_data.append(['', '', '', '', '<b>Subtotal:</b>', f"<b>Rs. {float(subtotal):.2f}</b>"])
        if tax and float(tax) > 0:
            table_data.append(['', '', '', '', f'<b>Tax ({data.get("sales_tax", 0)}%):</b>', f"<b>Rs. {float(tax):.2f}</b>"])
        if shipping and float(shipping) > 0:
            table_data.append(['', '', '', '', '<b>Shipping:</b>', f"<b>Rs. {float(shipping):.2f}</b>"])
        table_data.append(['', '', '', '', '<b>GRAND TOTAL:</b>', f"<b>Rs. {float(grand_total):.2f}</b>"])

        items_table = Table(table_data, colWidths=[0.5*inch, 2*inch, 1*inch, 0.6*inch, 1*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, len(items) + 1), 1, colors.grey),
            ('ALIGN', (3, 1), (5, len(items) + 1), 'RIGHT'),
            ('BACKGROUND', (0, -4), (-1, -1), colors.lightgrey),
            ('LINEABOVE', (0, -4), (-1, -4), 2, colors.black),
            ('FONTNAME', (4, -4), (5, -1), 'Helvetica-Bold'),
        ]))

        story.append(items_table)
        story.append(Spacer(1, 0.3*inch))

    # Terms
    if data.get('payment_terms') or data.get('shipping_terms'):
        story.append(Paragraph("<b>Terms & Conditions:</b>", styles['Heading2']))
        terms = []
        if data.get('payment_terms'):
            terms.append(f"Payment Terms: {data['payment_terms']}")
        if data.get('shipping_terms'):
            terms.append(f"Shipping Terms: {data['shipping_terms']}")
        if data.get('delivery_method'):
            terms.append(f"Delivery Method: {data['delivery_method']}")

        for term in terms:
            story.append(Paragraph(term, styles['Normal']))

    # Footer
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                          styles['Italic']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
