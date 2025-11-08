from flask import Flask, render_template, request, send_file, session, redirect, url_for
import io, json, base64
from pathlib import Path
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf
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

# Your existing routes below (preview_invoice, download_invoice)...

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
        
        html = render_template("invoice.html", data=data, preview=False, qr_b64=qr_b64)
        pdf_bytes = generate_pdf(html)
        return send_file(io.BytesIO(pdf_bytes),
                         mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"{data.get('invoice_number','invoice')}.pdf")
    except Exception as e:
        app.logger.error(f"Download failed: {e}", exc_info=True)
        return f"Error generating PDF: {e}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
