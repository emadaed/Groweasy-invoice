from weasyprint import HTML
from pathlib import Path

def generate_pdf(html_content: str) -> bytes:
    """Render HTML → PDF (returns bytes)."""
    base_url = str(Path(__file__).resolve().parent.parent)
    return HTML(string=html_content, base_url=base_url).write_pdf()
