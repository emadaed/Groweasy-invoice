# core/utils.py
from PIL import Image
import io
import base64

def process_uploaded_logo(logo_file, max_kb=300, max_width=200, max_height=200):
    """
    Process uploaded logo:
    - Limit size to max_kb
    - Resize to max dimensions
    - Convert to clean base64 string (NO data: prefix)
    - Return None if no file
    """
    if not logo_file or not logo_file.filename:
        return None

    # Reset file pointer and check size
    logo_file.seek(0, io.SEEK_END)
    size_kb = logo_file.tell() / 1024
    logo_file.seek(0)

    if size_kb > max_kb:
        raise ValueError(f"Logo too large: {size_kb:.1f}KB. Maximum allowed: {max_kb}KB")

    try:
        # Open and validate image
        img = Image.open(logo_file)
        img = img.convert("RGB")  # Remove alpha channel issues

        # Resize if needed
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Save optimized PNG to memory
        buffered = io.BytesIO()
        img.save(buffered, format="PNG", optimize=True)

        # Clean base64 (no prefix)
        logo_b64_clean = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return logo_b64_clean

    except Exception as e:
        raise ValueError(f"Invalid or corrupted image: {str(e)}")
