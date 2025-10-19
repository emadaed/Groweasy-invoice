import io
from weasyprint import HTML, CSS

def render_invoice_pdf(html_string_or_bytes):
    """Render given HTML string to PDF bytes using WeasyPrint.
    If system dependencies for WeasyPrint are missing, the call will raise.
    """
    if isinstance(html_string_or_bytes, bytes):
        html = HTML(string=html_string_or_bytes.decode('utf-8'))
    else:
        html = HTML(string=html_string_or_bytes)
    css = CSS(string='@page { size: A4; margin: 20mm }')
    pdf = html.write_pdf(stylesheets=[css])
    return pdf
