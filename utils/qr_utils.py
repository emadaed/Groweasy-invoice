import qrcode
from PIL import Image
import os

def make_qr_with_logo(text, logo_path, out_path, qr_size=600, logo_scale=0.20):
    """
    Generate a QR code for `text`, and optionally embed `logo_path` centered.
    Saves PNG to out_path.
    """

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    img = img.resize((qr_size, qr_size))

    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")

        # --- Compute logo size ---
        logo_w = int(qr_size * logo_scale)
        logo_h = int((logo_w / logo.width) * logo.height)

        # --- Pillow ≥10 compatibility ---
        if hasattr(Image, "Resampling"):
            resample_method = Image.Resampling.LANCZOS
        else:
            resample_method = Image.ANTIALIAS  # backward fallback

        logo = logo.resize((logo_w, logo_h), resample=resample_method)

        # --- Paste logo centered ---
        pos = ((qr_size - logo_w) // 2, (qr_size - logo_h) // 2)
        img.paste(logo, pos, logo)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, format="PNG")