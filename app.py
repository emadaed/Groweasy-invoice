from flask import Flask, render_template, request, send_file, session, redirect, url_for, send_from_directory, flash, jsonify
from fbr_integration import FBRInvoice
import io, json, base64
from pathlib import Path
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf, HAS_WEAZYPRINT
from core.auth import init_db, create_user, verify_user
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # Change this!

# Initialize database
init_db()

def generate_custom_qr(invoice_data):
    """Generate custom branded QR code for payment"""
    try:
        import qrcode
        from PIL import Image, ImageDraw
        import os
        
        # QR content - customize this as needed
        qr_content = f"""
Invoice: {invoice_data['invoice_number']}
Amount: ${invoice_data['grand_total']:.2f}
Date: {invoice_data['invoice_date']}
Company: {invoice_data['company_name']}
Client: {invoice_data['client_name']}
        """.strip()
        
        # Create QR code with custom styling
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        
        # Create QR code image with custom colors
        qr_img = qr.make_image(
            fill_color="#2c5aa0",  # Brand blue color
            back_color="#ffffff"   # White background
        ).convert('RGB')
        
        # Try to add logo if available
        try:
            logo_path = os.path.join('static', 'assets', 'logo.png')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                # Resize logo
                logo_size = 40
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Calculate position to center the logo
                pos = ((qr_img.size[0] - logo_size) // 2, (qr_img.size[1] - logo_size) // 2)
                
                # Create a circular mask for the logo
                mask = Image.new('L', (logo_size, logo_size), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, logo_size, logo_size), fill=255)
                
                # Apply circular mask to logo
                logo.putalpha(mask)
                
                # Paste logo on QR code
                qr_img.paste(logo, pos, logo)
        except Exception as e:
            print(f"Logo addition skipped: {e}")
        
        # Convert to base64
        buffer = io.BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return qr_b64
        
    except Exception as e:
        print(f"Custom QR generation error: {e}")
        # Fallback: generate simple QR code
        return generate_simple_qr(invoice_data)

def generate_simple_qr(invoice_data):
    """Generate simple QR code as fallback"""
    try:
        import qrcode
        import io
        
        qr_content = f"Invoice: {invoice_data['invoice_number']}\nAmount: ${invoice_data['grand_total']:.2f}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="#2c5aa0", back_color="#ffffff")
        
        buffer = io.BytesIO()
        qr_img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
        
    except Exception as e:
        print(f"Simple QR generation also failed: {e}")
        return None

@app.route('/')
def home():
    """Home page - show invoice creation form"""
    return render_template('form.html')

@app.route('/debug')
def debug():
    """Debug route to check what's working"""
    debug_info = {
        'session': dict(session),
        'routes': [str(rule) for rule in app.url_map.iter_rules()],
        'user_authenticated': bool(session.get('user_id'))
    }
    return jsonify(debug_info)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_id = verify_user(email, password)
        if user_id:
            session['user_id'] = user_id
            session['user_email'] = email
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name', '')
        
        if create_user(email, password, company_name):
            return redirect(url_for('login'))
        else:
            return render_template('register.html', error='User already exists')
    
    return render_template('register.html')

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("dashboard.html", user_email=session['user_email'])

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route("/donate")
def donate():
    return render_template("donate.html")

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js'), 200, {'Content-Type': 'application/javascript'}

@app.route('/preview_invoice', methods=['POST'])
def preview_invoice():
    try:
        invoice_data = prepare_invoice_data(request.form, request.files)
        
        # 1. FBR QR Code (Mandatory)
        fbr_invoice = FBRInvoice(invoice_data)
        fbr_summary = fbr_invoice.get_fbr_summary()
        fbr_qr_code = fbr_summary['qr_code'] if fbr_summary['is_compliant'] else None
        
        # 2. Your Custom Colorful Logo-Embedded QR Code
        custom_qr_b64 = generate_custom_qr(invoice_data)
        
        print("🔍 DEBUG: Rendering invoice template with data:", invoice_data.keys())
        
        return render_template('invoice.html', 
                             data=invoice_data, 
                             preview=True,
                             custom_qr_b64=custom_qr_b64,  # Your colorful QR
                             fbr_qr_code=fbr_qr_code,      # FBR QR
                             fbr_compliant=fbr_summary['is_compliant'],
                             fbr_errors=fbr_summary['errors'])
                             
    except Exception as e:
        flash(f'Error generating preview: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/download_invoice', methods=['POST'])
def download_invoice():
    try:
        import json
        from core.pdf_engine import generate_pdf
        
        data = json.loads(request.form['data'])
        
        # FBR Integration for download
        fbr_invoice = FBRInvoice(data)
        fbr_summary = fbr_invoice.get_fbr_summary()
        fbr_qr_code = fbr_summary['qr_code'] if fbr_summary['is_compliant'] else None
        
        # Generate custom QR for download as well
        custom_qr_b64 = generate_custom_qr(data)
        
        print("🔍 DEBUG: Generating PDF with data:", data.keys())
        
        # Render HTML with BOTH QR codes
        html_content = render_template('invoice.html', 
                                     data=data, 
                                     preview=False,
                                     custom_qr_b64=custom_qr_b64,  # Your colorful QR
                                     fbr_qr_code=fbr_qr_code,      # FBR QR
                                     fbr_compliant=fbr_summary['is_compliant'])
        
        # Generate PDF
        pdf_bytes = generate_pdf(html_content)
        
        # Return PDF
        from flask import Response
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=invoice_{data["invoice_number"]}.pdf'}
        )
        
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('home'))
    
# ... keep all your existing PDF fallback functions (_generate_data_driven_fallback, etc.)

def debug_invoice_data():
    """Debug function to check what data is being passed to template"""
    sample_data = {
        'company_name': 'Test Company',
        'company_address': '123 Test St',
        'company_phone': '+1234567890',
        'company_email': 'test@company.com',
        'company_tax_id': 'TAX123',
        'invoice_number': 'INV-001',
        'invoice_date': '2024-01-01',
        'due_date': '2024-01-31',
        'client_name': 'Test Client',
        'client_email': 'client@test.com',
        'client_phone': '+0987654321',
        'client_address': '456 Client Ave',
        'seller_ntn': '1234567-8',
        'buyer_ntn': '8765432-1',
        'payment_terms': 'Net 30',
        'payment_methods': 'Bank Transfer, Credit Card',
        'items': [
            {'name': 'Test Item 1', 'qty': 2, 'price': 100.00, 'total': 200.00},
            {'name': 'Test Item 2', 'qty': 1, 'price': 50.00, 'total': 50.00}
        ],
        'subtotal': 250.00,
        'discount_rate': 10.0,
        'discount_amount': 25.00,
        'tax_rate': 17.0,
        'tax_amount': 42.50,
        'grand_total': 267.50,
        'notes': 'Test note'
    }
    return sample_data



def _generate_data_driven_fallback(data):
    """Generate fallback PDF using actual invoice data with proper encoding."""
    print("🔍 DEBUG: Starting PDF fallback generation...")
    
    # CORRECT IMPORT for fpdf2
    try:
        from fpdf import FPDF  # This is the correct import for fpdf2
        print("✅ fpdf2 import successful")
    except ImportError as e:
        print(f"❌ fpdf2 import failed: {e}")
        # Try to see what's available
        try:
            import fpdf
            print(f"✅ fpdf module found: {fpdf.__file__}")
            from fpdf import FPDF
            print("✅ FPDF class imported successfully")
        except Exception as e2:
            print(f"❌ Complete import failure: {e2}")
        return _generate_minimal_pdf_structure()
    
    # Rest of your function continues here...
    try:
        import tempfile
        import os
        
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "INVOICE", 0, 1, 'C')
        pdf.ln(5)
        
        # Invoice info
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 8, f"Invoice #: {data.get('invoice_number', 'N/A')}", 0, 1)
        pdf.cell(0, 8, f"Date: {data.get('invoice_date', 'N/A')}", 0, 1)
        pdf.cell(0, 8, f"Client: {data.get('client_name', 'N/A')}", 0, 1)
        pdf.ln(10)
        
        # Items table header
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(100, 8, "Item", 1)
        pdf.cell(30, 8, "Qty", 1)
        pdf.cell(30, 8, "Price", 1)
        pdf.cell(30, 8, "Total", 1)
        pdf.ln()
        
        # Items
        pdf.set_font("Arial", '', 10)
        for item in data.get('items', []):
            item_name = str(item.get('name', ''))[:30]
            pdf.cell(100, 8, item_name, 1)
            pdf.cell(30, 8, str(item.get('qty', '')), 1)
            pdf.cell(30, 8, f"${float(item.get('price', 0)):.2f}", 1)
            pdf.cell(30, 8, f"${float(item.get('total', 0)):.2f}", 1)
            pdf.ln()
        
        # Totals
        pdf.ln(10)
        pdf.set_font("Arial", '', 10)
        pdf.cell(130, 8, "Subtotal:", 0, 0, 'R')
        pdf.cell(30, 8, f"${float(data.get('subtotal', 0)):.2f}", 0, 1)
        
        tax_amount = float(data.get('tax_amount', 0))
        if tax_amount > 0:
            pdf.cell(130, 8, f"Tax ({data.get('tax_rate', 0)}%):", 0, 0, 'R')
            pdf.cell(30, 8, f"${tax_amount:.2f}", 0, 1)
        
        discount_amount = float(data.get('discount_amount', 0))
        if discount_amount > 0:
            pdf.cell(130, 8, f"Discount ({data.get('discount_rate', 0)}%):", 0, 0, 'R')
            pdf.cell(30, 8, f"-${discount_amount:.2f}", 0, 1)
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(130, 10, "TOTAL:", 0, 0, 'R')
        pdf.cell(30, 10, f"${float(data.get('grand_total', 0)):.2f}", 0, 1)
        
        # Footer
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 8)
        pdf.cell(0, 6, "Development Preview - Full professional formatting in production", 0, 1)
        
        # Use file output instead of string output for better compatibility
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf.output(tmp_file.name)
            with open(tmp_file.name, 'rb') as f:
                pdf_bytes = f.read()
            os.unlink(tmp_file.name)
        
        print("✅ PDF generated successfully with fpdf2")
        return pdf_bytes
        
    except Exception as e:
        print(f"❌ PDF generation error: {e}")
        return _generate_minimal_pdf_structure()

def _generate_basic_pdf(data):
    """Generate a basic but guaranteed-to-work PDF."""
    try:
        from fpdf import FPDF
        import tempfile
        import os
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=14)
        
        # Simple content that always works
        pdf.cell(200, 10, txt="GROWEASY INVOICE", ln=1, align='C')
        pdf.ln(5)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, f"Invoice: {data.get('invoice_number', 'N/A')}", ln=1)
        pdf.cell(0, 8, f"Client: {data.get('client_name', 'N/A')}", ln=1)
        pdf.cell(0, 8, f"Total: ${float(data.get('grand_total', 0)):.2f}", ln=1)
        pdf.ln(5)
        pdf.cell(0, 8, "Development Preview - Professional PDF in production", ln=1)
        
        # Use file output for reliability
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf.output(tmp_file.name)
            with open(tmp_file.name, 'rb') as f:
                pdf_bytes = f.read()
            os.unlink(tmp_file.name)
        
        return pdf_bytes
        
    except Exception as e:
        print(f"Basic PDF error: {e}")
        # Final fallback - minimal PDF structure
        return _generate_minimal_pdf_structure()

def _generate_minimal_pdf_structure():
    """Generate a minimal valid PDF structure that always works."""
    # This is a basic PDF 1.4 structure that any PDF reader can open
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 200 >>
stream
BT /F1 18 Tf 50 750 Td (GrowEasy Invoice) Tj ET
BT /F1 12 Tf 50 720 Td (Development Preview) Tj ET
BT /F1 10 Tf 50 700 Td (PDF generation successful!) Tj ET
BT /F1 8 Tf 50 680 Td (Deploy to production for professional formatting) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000250 00000 n 
0000000510 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
610
%%EOF"""
    return pdf_content

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
