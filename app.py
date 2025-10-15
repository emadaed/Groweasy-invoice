import os
from flask import Flask, request, jsonify, render_template, send_file
from datetime import datetime
import json
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import qrcode
from PIL import Image

# Initialize Flask app FIRST
app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-here"

# THEN configure upload settings
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB limit
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}

# Create uploads directory
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload-logo", methods=["POST"])
def upload_logo():
    if "logo" not in request.files:
        return jsonify({"error": "No file selected"}), 400

    file = request.files["logo"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(
            f"logo_{int(datetime.now().timestamp())}.{file.filename.rsplit('.', 1)[1].lower()}"
        )
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Convert to RGB and resize if needed
        try:
            img = Image.open(filepath)
            if img.mode != "RGB":
                img = img.convert("RGB")
            if img.size[0] > 500 or img.size[1] > 500:
                img.thumbnail((500, 500), Image.Resampling.LANCZOS)
            img.save(filepath, "JPEG", quality=85)
        except Exception as e:
            print(f"Image processing error: {e}")

        return jsonify({"filename": filename, "message": "Logo uploaded successfully"})

    return jsonify({"error": "Invalid file type"}), 400


@app.route("/api/generate-pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.get_json()

        # Get logo path if available
        logo_filename = data.get("logo_filename")
        logo_path = (
            os.path.join(app.config["UPLOAD_FOLDER"], logo_filename)
            if logo_filename
            else None
        )

        # Generate PDF
        pdf_buffer = create_pdf(data, logo_path)

        if pdf_buffer:
            return send_file(
                pdf_buffer,
                as_attachment=True,
                download_name=f"invoice_{data.get('invoice_number', '001')}.pdf",
                mimetype="application/pdf",
            )
        else:
            return jsonify({"error": "PDF generation failed"}), 500

    except Exception as e:
        print(f"PDF generation error: {e}")
        return jsonify({"error": str(e)}), 500


# Enhanced PDF generation with logo and QR
def create_pdf(invoice_data, logo_path=None):
    try:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 50

        # Logo Section
        if logo_path and os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                # Calculate proportional size
                max_logo_width = 60 * mm
                max_logo_height = 30 * mm

                img_width, img_height = img.size
                aspect_ratio = img_width / img_height

                if img_width > max_logo_width:
                    img_width = max_logo_width
                    img_height = img_width / aspect_ratio

                if img_height > max_logo_height:
                    img_height = max_logo_height
                    img_width = img_height * aspect_ratio

                pdf.drawInlineImage(
                    logo_path, 50, y - img_height, width=img_width, height=img_height
                )
                y -= img_height + 10
            except Exception as e:
                print(f"Logo error: {e}")
                # Continue without logo if there's an error

        # Header
        pdf.setFont("Helvetica-Bold", 18)
        pdf.setFillColorRGB(0.2, 0.4, 0.8)  # Professional blue
        pdf.drawString(50, y, "DIGIRECEIPT")
        pdf.setFont("Helvetica", 10)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.drawString(50, y - 15, "Professional Invoice Solution")
        pdf.drawString(50, y - 30, f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}")

        # Invoice Number
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(
            width - 150, y, f"INVOICE #: {invoice_data.get('invoice_number', '001')}"
        )

        y -= 60

        # Company & Customer Info with better styling
        pdf.setFillColorRGB(0.9, 0.95, 1.0)  # Light blue background
        pdf.rect(40, y - 40, width - 80, 80, fill=1, stroke=0)
        pdf.setFillColorRGB(0, 0, 0)

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, "FROM:")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            50, y - 15, invoice_data.get("vendor_name", "Your Business Name")
        )
        pdf.drawString(
            50, y - 30, invoice_data.get("vendor_address", "Business Address")
        )
        pdf.drawString(50, y - 45, invoice_data.get("vendor_phone", "Phone: N/A"))

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(300, y, "BILL TO:")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(300, y - 15, invoice_data.get("customer_name", "Customer Name"))
        pdf.drawString(
            300, y - 30, invoice_data.get("customer_address", "Customer Address")
        )
        pdf.drawString(300, y - 45, invoice_data.get("customer_phone", "Phone: N/A"))

        y -= 90

        # Items Table with professional styling
        pdf.setFillColorRGB(0.8, 0.85, 0.9)  # Header background
        pdf.rect(40, y - 15, width - 80, 15, fill=1, stroke=0)
        pdf.setFillColorRGB(0, 0, 0)

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(45, y - 10, "DESCRIPTION")
        pdf.drawString(320, y - 10, "QTY")
        pdf.drawString(370, y - 10, "PRICE")
        pdf.drawString(450, y - 10, "TOTAL")

        y -= 25
        pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
        pdf.line(40, y, width - 40, y)
        y -= 10

        # Items
        pdf.setFont("Helvetica", 9)
        items = invoice_data.get("items", [])
        subtotal = 0

        for i, item in enumerate(items):
            line_total = item["quantity"] * item["price"]
            subtotal += line_total

            # Alternate row colors for readability
            if i % 2 == 0:
                pdf.setFillColorRGB(0.98, 0.98, 0.98)
                pdf.rect(40, y - 12, width - 80, 15, fill=1, stroke=0)
                pdf.setFillColorRGB(0, 0, 0)

            # Truncate long descriptions
            item_name = (
                item["name"][:40] + "..." if len(item["name"]) > 40 else item["name"]
            )

            pdf.drawString(45, y, f"{i+1}. {item_name}")
            pdf.drawString(320, y, str(item["quantity"]))
            pdf.drawString(370, y, f"Rs.{item['price']:,.2f}")
            pdf.drawString(450, y, f"Rs.{line_total:,.2f}")
            y -= 15

        y -= 20

        # Totals Section
        tax_rate = invoice_data.get("tax_rate", 17)
        tax_amount = (subtotal * tax_rate) / 100
        grand_total = subtotal + tax_amount

        pdf.setStrokeColorRGB(0.3, 0.3, 0.3)
        pdf.line(300, y, 500, y)
        y -= 15

        pdf.setFont("Helvetica", 10)
        pdf.drawString(350, y, f"Subtotal: Rs.{subtotal:,.2f}")
        y -= 15
        pdf.drawString(350, y, f"Tax ({tax_rate}%): Rs.{tax_amount:,.2f}")
        y -= 15
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColorRGB(0.2, 0.6, 0.2)  # Green for total
        pdf.drawString(350, y, f"TOTAL: Rs.{grand_total:,.2f}")
        pdf.setFillColorRGB(0, 0, 0)

        y -= 40

        # Interactive QR Code
        qr_data = {
            "invoice_number": invoice_data.get("invoice_number", "001"),
            "vendor": invoice_data.get("vendor_name", ""),
            "customer": invoice_data.get("customer_name", ""),
            "amount": grand_total,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "items_count": len(items),
        }

        qr_buffer = create_interactive_qr(qr_data, logo_path)
        if qr_buffer:
            # pdf.drawInlineImage(qr_buffer, 400, y - 80, width=80, height=80)
            from PIL import Image as PILImage

            qr_image = PILImage.open(qr_buffer)
            pdf.drawInlineImage(qr_image, 400, y - 80, width=80, height=80)
            pdf.setFont("Helvetica", 8)
            pdf.drawString(400, y - 85, "Scan for details")

        # Footer
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(0.5, 0.5, 0.5)
        pdf.drawString(50, 40, "Thank you for your business!")
        pdf.drawString(
            50, 30, "Generated by DigiReceipt - Pakistan's Premier Invoice Solution"
        )
        pdf.drawString(50, 20, "For inquiries: contact@digireceipt.com")

        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"PDF generation error: {e}")
        return None


def create_interactive_qr(data, logo_path=None):
    """Create interactive QR code with optional logo embedding"""
    try:
        # Create QR code with error correction
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )

        # Create interactive data with more details
        interactive_data = {
            "type": "invoice",
            "invoice_id": data.get("invoice_number", "001"),
            "business": data.get("vendor", "Your Business"),
            "customer": data.get("customer", "Customer"),
            "amount": data.get("amount", 0),
            "date": data.get("date", ""),
            "items": data.get("items_count", 0),
            "timestamp": datetime.now().isoformat(),
        }

        qr.add_data(json.dumps(interactive_data, indent=2))
        qr.make(fit=True)

        # Create colored QR code
        qr_img = qr.make_image(
            fill_color=(30, 64, 175), back_color="white"  # Professional blue
        ).convert("RGB")

        # Add logo to QR code if available
        if logo_path and os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path)

                # Calculate logo size (20% of QR code)
                qr_width, qr_height = qr_img.size
                logo_size = qr_width // 5

                # Resize logo
                logo_img = logo_img.resize(
                    (logo_size, logo_size), Image.Resampling.LANCZOS
                )

                # Calculate position (center of QR code)
                pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)

                # Create a white background for logo
                background = Image.new("RGB", (logo_size + 8, logo_size + 8), "white")
                background.paste(logo_img, (4, 4))

                # Paste logo on QR code
                qr_img.paste(background, (pos[0] - 4, pos[1] - 4))

            except Exception as e:
                print(f"QR logo error: {e}")
                # Continue without logo if there's an error

        # Convert to bytes
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format="PNG", quality=95)
        qr_buffer.seek(0)

        return qr_buffer

    except Exception as e:
        print(f"QR generation error: {e}")
        return None


if __name__ == "__main__":
    app.run(debug=True)
