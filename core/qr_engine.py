import qrcode
from PIL import Image

def make_qr_with_logo(data_text, logo_path, output_path):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    try:
        logo = Image.open(logo_path)
        box_size = int(img.size[0] * 0.25)
        logo = logo.resize((box_size, box_size))
        pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
        img.paste(logo, pos)
    except Exception:
        pass

    img.save(output_path)

def generate_simple_qr(data):
    """Generate black/white QR without logo"""
    return make_qr_with_logo(data, logo_b64=None)  # Reuse logic, no logo
