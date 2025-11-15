from pathlib import Path
import os

# Global flag to track WeasyPrint availability
try:
    from weasyprint import HTML, CSS
    HAS_WEAZYPRINT = True
except ImportError:
    HAS_WEAZYPRINT = False
    print("⚠️  WeasyPrint not available - using fpdf fallback for local development")

def generate_pdf(html_content: str) -> bytes:
    """Render HTML → PDF with proper fallback."""

    if HAS_WEAZYPRINT:
        # Production - use WeasyPrint
        return _generate_weasyprint_pdf(html_content)
    else:
        # Local development - use content-based fallback
        return _generate_content_fallback(html_content)

def _generate_weasyprint_pdf(html_content: str) -> bytes:
    """Generate PDF using WeasyPrint (production)."""
    base_url = str(Path(__file__).resolve().parent.parent)

    pdf_css = CSS(string='''
        @page {
            size: A4;
            margin: 15mm;
        }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 12px;
            line-height: 1.4;
            color: #212529;
            margin: 0;
            padding: 0;
        }
        /* HIDE navigation and PWA elements in PDF */
        .user-nav, .pwa-install-btn, .user-nav * {
            display: none !important;
        }
        .invoice-container {
            width: 180mm;
            margin: 0 auto;
        }
        table {
            border-collapse: collapse;
            width: 100%;
        }
        th, td {
            border: 1px solid #dee2e6;
            padding: 8px;
            text-align: left;
        }
        .company-logo {
            width: 60px;
            height: 60px;
        }
        .qr-code {
            width: 60px;
            height: 60px;
        }
    ''')

    html = HTML(string=html_content, base_url=base_url)
    return html.write_pdf(stylesheets=[pdf_css])

def _generate_content_fallback(html_content: str) -> bytes:
    """Fallback that creates a simple PDF with basic content."""
    try:
        from fpdf import FPDF
        import re

        # Extract text from HTML
        def extract_text(html):
            clean = re.compile('<.*?>')
            return re.sub(clean, '', html)

        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "INVOICE - DEVELOPMENT PREVIEW", 0, 1, 'C')
        pdf.ln(10)

        # Content preview
        pdf.set_font("Arial", '', 10)
        clean_text = extract_text(html_content)
        preview = clean_text[:300] + "..." if len(clean_text) > 300 else clean_text
        pdf.multi_cell(0, 6, preview)

        # Footer
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 8)
        pdf.cell(0, 6, "GrowEasy Invoice - Local Development - Deploy for full PDF", 0, 1)

        return pdf.output(dest='S').encode('latin1')

    except ImportError:
        return _generate_minimal_pdf()

def _generate_minimal_pdf() -> bytes:
    """Generate a minimal valid PDF."""
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 100 >>
stream
BT /F1 12 Tf 50 750 Td (GrowEasy Invoice - Development Preview) Tj
/F1 10 Tf 50 730 Td (PDF generation works! Deploy to production for professional formatting.) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000233 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""
