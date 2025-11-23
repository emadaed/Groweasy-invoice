# app.py 18 Nov 2025 4:3 PM PKST
# Standard library
import io
import json
import base64
import os
from pathlib import Path

# Third-party
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, render_template, request, send_file, session, redirect, url_for, send_from_directory, flash, jsonify, g, Response
from flask_compress import Compress
from dotenv import load_dotenv

# Local application
from fbr_integration import FBRInvoice
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf, HAS_WEAZYPRINT
from core.auth import init_db, create_user, verify_user, get_user_profile, update_user_profile, change_user_password, save_user_invoice
from core.middleware import security_headers

# Environment setup
load_dotenv()

# App creation
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-dev-key-railway-2025-safe')

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Middleware
Compress(app)
security_headers(app)

# Database
init_db()


def generate_custom_qr(invoice_data):
    """Generate custom branded QR code for payment using uploaded logo"""
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

        # Try to add logo - PRIORITY: Use uploaded logo first
        logo_added = False
        try:
            # 1. FIRST TRY: Use uploaded logo from invoice_data
            if invoice_data.get('logo_b64'):
                # Remove data URL prefix if present
                logo_b64 = invoice_data['logo_b64']
                if 'base64,' in logo_b64:
                    logo_b64 = logo_b64.split('base64,')[1]

                logo_data = base64.b64decode(logo_b64)
                logo = Image.open(io.BytesIO(logo_data))
                logo_added = True

            # 2. FALLBACK: Use static logo if no uploaded logo
            elif os.path.exists(os.path.join('static', 'assets', 'logo.png')):
                logo_path = os.path.join('static', 'assets', 'logo.png')
                logo = Image.open(logo_path)
                logo_added = True

            if logo_added:
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
    """Home page - show invoice creation form with pre-filled data"""
    prefill_data = {}

    if 'user_id' in session:
        user_profile = get_user_profile(session['user_id'])
        if user_profile:
            prefill_data = {
                'company_name': user_profile.get('company_name', ''),
                'company_address': user_profile.get('company_address', ''),
                'company_phone': user_profile.get('company_phone', ''),
                'company_email': user_profile.get('email', ''),
                'company_tax_id': user_profile.get('company_tax_id', '')
            }

    return render_template('form.html', prefill_data=prefill_data, nonce=g.nonce)


@app.route('/debug')
def debug():
    """Debug route to check what's working"""
    debug_info = {
        'session': dict(session),
        'routes': [str(rule) for rule in app.url_map.iter_rules()],
        'user_authenticated': bool(session.get('user_id'))
    }
    return jsonify(debug_info)

# NEW ROUTES USER SETTINGS

@app.route("/settings", methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_user_profile, update_user_profile, change_user_password, verify_user

    user_profile = get_user_profile(session['user_id'])

    if request.method == 'POST':
        # Handle profile update
        if 'update_profile' in request.form:
            company_name = request.form.get('company_name')
            company_address = request.form.get('company_address')
            company_phone = request.form.get('company_phone')
            company_tax_id = request.form.get('company_tax_id')

            update_user_profile(
                session['user_id'],
                company_name=company_name,
                company_address=company_address,
                company_phone=company_phone,
                company_tax_id=company_tax_id
            )
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('settings'))

        # Handle password change
        elif 'change_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            # Verify current password
            if not verify_user(user_profile['email'], current_password):
                flash('Current password is incorrect', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'error')
            elif len(new_password) < 6:
                flash('New password must be at least 6 characters', 'error')
            else:
                change_user_password(session['user_id'], new_password)
                flash('Password changed successfully!', 'success')

            return redirect(url_for('settings'))

    return render_template("settings.html", user_profile=user_profile, nonce=g.nonce)


# ADD RATE LIMITS TO ROUTES:
@app.route("/login", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
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
            return render_template('login.html', error='Invalid credentials', nonce=g.nonce)

    return render_template('login.html', nonce=g.nonce)


@app.route("/register", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name', '')

        if create_user(email, password, company_name):
            return redirect(url_for('login'))
        else:
            return render_template('register.html', error='User already exists', nonce=g.nonce)

    return render_template('register.html', nonce=g.nonce)


@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("dashboard.html", user_email=session['user_email'], nonce=g.nonce)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route("/donate")
def donate():
    return render_template("donate.html", nonce=g.nonce)


@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js'), 200, {'Content-Type': 'application/javascript'}


@app.route('/preview_invoice', methods=['POST'])
@limiter.limit("5 per minute")
def preview_invoice():
    try:
        invoice_data = prepare_invoice_data(request.form, request.files)

        # 1. FBR QR Code (Mandatory)
        fbr_invoice = FBRInvoice(invoice_data)
        fbr_summary = fbr_invoice.get_fbr_summary()
        fbr_qr_code = fbr_summary['qr_code'] if fbr_summary['is_compliant'] else None

        # 2. Custom Colorful Logo-Embedded QR Code
        custom_qr_b64 = generate_custom_qr(invoice_data)

        print("DEBUG: Rendering invoice template with data:", invoice_data.keys())

        return render_template('invoice.html',
                             data=invoice_data,
                             preview=True,
                             custom_qr_b64=custom_qr_b64,
                             fbr_qr_code=fbr_qr_code,
                             fbr_compliant=fbr_summary['is_compliant'],
                             fbr_errors=fbr_summary['errors'],
                             nonce=g.nonce)

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

        print("DEBUG: Generating PDF with data:", data.keys())

        # Render HTML with BOTH QR codes
        html_content = render_template('invoice.html',
                                     data=data,
                                     preview=False,
                                     custom_qr_b64=custom_qr_b64,
                                     fbr_qr_code=fbr_qr_code,
                                     fbr_compliant=fbr_summary['is_compliant'],
                                     nonce=g.nonce)

        # Generate PDF using WeasyPrint only
        pdf_bytes = generate_pdf(html_content)

        # SAVE INVOICE TO USER HISTORY
        if 'user_id' in session:
            save_user_invoice(session['user_id'], data)

        # Return PDF
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=invoice_{data["invoice_number"]}.pdf'}
        )

    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('home'))

# debug invoice data

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
