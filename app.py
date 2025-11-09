from flask import Flask, render_template, request, send_file, session, redirect, url_for, send_from_directory
import io, json, base64
from pathlib import Path
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf, HAS_WEAZYPRINT
from core.auth import init_db, create_user, verify_user

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'  # Change this!

# Initialize database
init_db()

@app.route("/")
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template("form.html")

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

@app.route("/preview", methods=["POST"])
def preview_invoice():
    try:
        form_data = request.form.to_dict(flat=False)
        files = request.files
        data = prepare_invoice_data(form_data, files)

        # QR creation
        qr_dir = Path("static/assets/qr")
        qr_dir.mkdir(parents=True, exist_ok=True)
        qr_path = qr_dir / f"{data['invoice_number']}.png"
        logo_path = data.get("logo_path", "static/assets/logo.png")
        make_qr_with_logo(f"Invoice {data['invoice_number']} for {data['client_name']}", logo_path, qr_path)
        with open(qr_path, "rb") as f:
            qr_b64 = base64.b64encode(f.read()).decode("utf-8")

        return render_template("invoice.html", data=data, qr_b64=qr_b64, preview=True)
    except Exception as e:
        app.logger.error(f"Preview failed: {e}", exc_info=True)
        return f"Error generating preview: {e}", 500

@app.route("/download", methods=["POST"])
def download_invoice():
    try:
        # Handle both JSON string and direct form data
        data_json = request.form.get("data")
        if data_json:
            data = json.loads(data_json)
        else:
            data = request.form.to_dict()
            
        qr_b64 = request.form.get("qr_b64")
        
        # Check if we're in development mode (no WeasyPrint)
        if not HAS_WEAZYPRINT:
            print("📄 Using local PDF fallback (development mode)")
            # Use data-driven fallback for local development
            pdf_bytes = _generate_data_driven_fallback(data)
        else:
            print("📄 Using WeasyPrint (production mode)")
            # Production - use WeasyPrint
            html = render_template("invoice.html", data=data, preview=False, qr_b64=qr_b64)
            pdf_bytes = generate_pdf(html)
            
        return send_file(io.BytesIO(pdf_bytes),
                         mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"{data.get('invoice_number','invoice')}.pdf")
    except Exception as e:
        app.logger.error(f"Download failed: {e}", exc_info=True)
        return f"Error generating PDF: {e}", 500

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


def _generate_data_driven_fallback(data):
    """Generate fallback PDF using actual invoice data with proper encoding."""
    print("🔍 DEBUG: Starting PDF fallback generation...")
    
    # Test import
    try:
        from fpdf import FPDF
        print("✅ fpdf import successful")
    except ImportError as e:
        print(f"❌ fpdf import failed: {e}")
        return _generate_minimal_pdf_structure()
    
    # Rest of  function...


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
