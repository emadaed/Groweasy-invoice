from weasyprint import HTML, CSS
from pathlib import Path
import os

def generate_pdf(html_content: str) -> bytes:
    """Render HTML → PDF (returns bytes)."""
    base_url = str(Path(__file__).resolve().parent.parent)
    
    # Create PDF-specific CSS
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
