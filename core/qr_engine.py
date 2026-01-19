import qrcode
from io import BytesIO
import base64

def generate_qr_base64(data, logo_path=None, fill_color="black", back_color="white"):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGB")

    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path)
        logo_size = int(img.size[0] * 0.2)
        logo = logo.resize((logo_size, logo_size))
        pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
        img.paste(logo, pos, logo if logo.mode == 'RGBA' else None)

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')
