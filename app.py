# app.py - GrowEasy Invoice
# Last updated: December 2025
# Cloudflare Turnstile REMOVED - Clean version

# =============================================================================
# IMPORTS - Organized by category
# =============================================================================

# Standard library
import io
import json
import base64
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import secrets
import random

# Third-party
from flask import (
    Flask, render_template, request, send_file, session,
    redirect, url_for, send_from_directory, flash, jsonify, g, Response
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

# Local application
from fbr_integration import FBRInvoice
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf, HAS_WEASYPRINT
from core.auth import (
    init_db, create_user, verify_user, get_user_profile,
    update_user_profile, change_user_password, save_user_invoice
)
from core.purchases import save_purchase_order, get_purchase_orders, get_suppliers
from core.middleware import security_headers

# =============================================================================
# CONFIGURATION
# =============================================================================

load_dotenv()

# Initialize Sentry for error monitoring
if os.getenv('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,
        environment='production' if os.getenv('RAILWAY_ENVIRONMENT') else 'development'
    )
    print("✅ Sentry monitoring enabled")

# =============================================================================
# APP INITIALIZATION
# =============================================================================

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Proxy configuration for Railway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Session security
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# Rate Limiting
REDIS_URL = os.getenv('REDIS_URL', 'memory://')
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=REDIS_URL
)

# Middleware
Compress(app)
security_headers(app)

# Database initialization
init_db()

# Initialize purchase tables
from core.purchases import init_purchase_tables
try:
    init_purchase_tables()
    print("✅ Purchase tables initialized successfully")
except Exception as e:
    print(f"⚠️ Warning: Could not initialize purchase tables: {e}")
    if os.getenv('SENTRY_DSN'):
        sentry_sdk.capture_exception(e)

# =============================================================================
# CONSTANTS
# =============================================================================

CURRENCY_SYMBOLS = {
    'PKR': 'Rs.',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'AED': 'د.إ',
    'SAR': '﷼'
}

SUCCESS_MESSAGES = {
    'invoice_created': [
        "🎉 Invoice created! You're a billing boss!",
        "💰 Cha-ching! Another invoice done!",
        "✨ Invoice magic complete!",
        "🚀 Invoice sent to the moon!",
        "🎊 You're on fire! Invoice created!"
    ],
    'stock_updated': [
        "📦 Stock updated! Inventory ninja at work!",
        "✅ Stock levels looking good!",
        "🎯 Bullseye! Stock updated perfectly!",
        "💪 Stock management on point!"
    ],
    'login': [
        "🎉 Welcome back, superstar!",
        "👋 Great to see you again!",
        "✨ You're logged in! Let's make money!",
        "🚀 Ready to conquer the day?"
    ],
    'product_added': [
        "📦 Product added! Your inventory grows!",
        "✨ New product in the house!",
        "🎉 Inventory expanded successfully!",
        "💪 Another product conquered!"
    ]
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def random_success_message(category='invoice_created'):
    """Get a random success message for the given category"""
    messages = SUCCESS_MESSAGES.get(category, SUCCESS_MESSAGES['invoice_created'])
    return random.choice(messages)


def validate_stock_availability(user_id, invoice_items):
    """Validate stock availability BEFORE invoice processing"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        for item in invoice_items:
            if item.get('product_id'):
                product_id = item['product_id']
                requested_qty = int(item.get('qty', 1))

                c.execute(
                    'SELECT name, current_stock FROM inventory_items WHERE id = ? AND user_id = ?',
                    (product_id, user_id)
                )
                result = c.fetchone()

                if not result:
                    conn.close()
                    return {'success': False, 'message': "Product not found in inventory"}

                product_name, current_stock = result
                if current_stock < requested_qty:
                    conn.close()
                    return {
                        'success': False,
                        'message': f"Only {current_stock} units available for '{product_name}'"
                    }

        conn.close()
        return {'success': True, 'message': 'Stock available'}

    except Exception as e:
        print(f"Stock validation error: {e}")
        return {'success': False, 'message': 'Stock validation failed'}


def update_stock_on_invoice(user_id, invoice_items, invoice_type='S', invoice_number=None):
    """Update stock with invoice reference number"""
    try:
        from core.inventory import InventoryManager

        for item in invoice_items:
            if item.get('product_id'):
                product_id = item['product_id']
                quantity = int(item.get('qty', 1))

                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute(
                    'SELECT current_stock FROM inventory_items WHERE id = ? AND user_id = ?',
                    (product_id, user_id)
                )
                result = c.fetchone()
                conn.close()

                if result:
                    current_stock = result[0]

                    if invoice_type == 'P':
                        new_stock = current_stock + quantity
                        movement_type = 'purchase'
                        notes = f"Purchased {quantity} units via PO: {invoice_number}" if invoice_number else f"Purchased {quantity} units"
                    else:
                        new_stock = current_stock - quantity
                        movement_type = 'sale'
                        notes = f"Sold {quantity} units via Invoice: {invoice_number}" if invoice_number else f"Sold {quantity} units"

                    success = InventoryManager.update_stock(
                        user_id, product_id, new_stock, movement_type, invoice_number, notes
                    )

                    if success:
                        print(f"✅ Stock updated: {item.get('name')} ({movement_type})")
                    else:
                        print(f"⚠️ Stock update failed for {item.get('name')}")

    except Exception as e:
        print(f"Stock update error: {e}")


def generate_unique_invoice_number(user_id):
    """Generate guaranteed unique invoice number per user"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT invoice_number FROM user_invoices
            WHERE user_id = ? AND invoice_number LIKE 'INV-%'
            ORDER BY id DESC LIMIT 1
        ''', (user_id,))

        result = c.fetchone()
        conn.close()

        if result:
            last_number = result[0]
            if last_number.startswith('INV-'):
                try:
                    last_num = int(last_number.split('-')[1])
                    return f"INV-{last_num + 1:05d}"
                except (ValueError, IndexError):
                    return "INV-00001"

        return "INV-00001"

    except Exception as e:
        print(f"Invoice number generation error: {e}")
        import time
        return f"INV-{int(time.time())}"


def generate_unique_po_number(user_id):
    """Generate unique purchase order number"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                po_number TEXT,
                supplier_name TEXT,
                order_date DATE,
                delivery_date DATE,
                grand_total DECIMAL(10,2),
                status TEXT DEFAULT 'pending',
                order_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            SELECT po_number FROM purchase_orders
            WHERE user_id = ? AND po_number LIKE 'PO-%'
            ORDER BY id DESC LIMIT 1
        ''', (user_id,))

        result = c.fetchone()
        conn.close()

        if result:
            last_number = result[0]
            if last_number.startswith('PO-'):
                try:
                    last_num = int(last_number.split('-')[1])
                    return f"PO-{last_num + 1:05d}"
                except (ValueError, IndexError):
                    return "PO-00001"

        return "PO-00001"

    except Exception as e:
        print(f"PO number generation error: {e}")
        import time
        return f"PO-{int(time.time())}"


# =============================================================================
# PENDING INVOICE MANAGEMENT
# =============================================================================

def save_pending_invoice(user_id, invoice_data):
    """Save pending invoice to database temporarily"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_invoices (
            user_id INTEGER PRIMARY KEY,
            invoice_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('DELETE FROM pending_invoices WHERE user_id = ?', (user_id,))
    c.execute(
        'INSERT INTO pending_invoices (user_id, invoice_data) VALUES (?, ?)',
        (user_id, json.dumps(invoice_data))
    )

    conn.commit()
    conn.close()


def get_pending_invoice(user_id):
    """Retrieve pending invoice from database"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('SELECT invoice_data FROM pending_invoices WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        return json.loads(result[0])
    return None


def clear_pending_invoice(user_id):
    """Clear pending invoice after successful download"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM pending_invoices WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


# =============================================================================
# QR CODE GENERATION
# =============================================================================

def generate_custom_qr(invoice_data):
    """Generate custom branded QR code for payment using uploaded logo"""
    try:
        import qrcode
        from PIL import Image, ImageDraw

        qr_content = f"""
Invoice: {invoice_data['invoice_number']}
Amount: ${invoice_data['grand_total']:.2f}
Date: {invoice_data['invoice_date']}
Company: {invoice_data['company_name']}
Client: {invoice_data['client_name']}
        """.strip()

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)

        qr_img = qr.make_image(
            fill_color="#2c5aa0",
            back_color="#ffffff"
        ).convert('RGB')

        # Try to add logo
        logo_added = False
        try:
            if invoice_data.get('logo_b64'):
                logo_b64 = invoice_data['logo_b64']
                if 'base64,' in logo_b64:
                    logo_b64 = logo_b64.split('base64,')[1]

                logo_data = base64.b64decode(logo_b64)
                logo = Image.open(io.BytesIO(logo_data))
                logo_added = True

            elif os.path.exists(os.path.join('static', 'assets', 'logo.png')):
                logo_path = os.path.join('static', 'assets', 'logo.png')
                logo = Image.open(logo_path)
                logo_added = True

            if logo_added:
                logo_size = 40
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

                pos = ((qr_img.size[0] - logo_size) // 2, (qr_img.size[1] - logo_size) // 2)

                mask = Image.new('L', (logo_size, logo_size), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, logo_size, logo_size), fill=255)

                logo.putalpha(mask)
                qr_img.paste(logo, pos, logo)

        except Exception as e:
            print(f"Logo addition skipped: {e}")

        buffer = io.BytesIO()
        qr_img.save(buffer, format='PNG')
        qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return qr_b64

    except Exception as e:
        print(f"Custom QR generation error: {e}")
        return generate_simple_qr(invoice_data)


def generate_simple_qr(invoice_data):
    """Generate simple QR code as fallback"""
    try:
        import qrcode

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


# =============================================================================
# CONTEXT PROCESSORS
# =============================================================================

@app.context_processor
def inject_currency():
    """Make currency available in all templates"""
    currency = 'PKR'
    symbol = 'Rs.'

    if 'user_id' in session:
        profile = get_user_profile(session['user_id'])
        if profile:
            currency = profile.get('preferred_currency', 'PKR')
            symbol = CURRENCY_SYMBOLS.get(currency, 'Rs.')

    return dict(currency=currency, currency_symbol=symbol)


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@app.route("/login", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """User login - No Turnstile verification"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user_id = verify_user(email, password)
        if user_id:
            from core.session_manager import SessionManager

            if not SessionManager.check_location_restrictions(user_id, request.remote_addr):
                flash('❌ Login not allowed from this location', 'error')
                return render_template('login.html', nonce=g.nonce)

            session_token = SessionManager.create_session(user_id, request)

            session['user_id'] = user_id
            session['user_email'] = email
            session['session_token'] = session_token

            flash(random_success_message('login'), 'success')
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials', nonce=g.nonce)

    return render_template('login.html', nonce=g.nonce)


@app.route("/register", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    """User registration - No Turnstile verification"""
    if request.method == 'POST':
        if not request.form.get('agree_terms'):
            flash('❌ You must agree to Terms of Service to register', 'error')
            return render_template('register.html', nonce=g.nonce)

        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name', '')

        print(f"📝 Attempting to register user: {email}")

        user_created = create_user(email, password, company_name)

        if user_created:
            flash('✅ Account created! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('❌ User already exists or registration failed', 'error')
            return render_template('register.html', nonce=g.nonce)

    return render_template('register.html', nonce=g.nonce)


@app.route("/logout")
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route("/forgot_password", methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Password reset request"""
    if request.method == 'POST':
        email = request.form.get('email')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()

        if user:
            flash('📧 Password reset instructions have been sent to your email.', 'success')
            flash('🔐 Development Note: In production, you would receive an email with reset link.', 'info')
            return render_template('reset_instructions.html', email=email, nonce=g.nonce)
        else:
            flash('❌ No account found with this email address.', 'error')

    return render_template('forgot_password.html', nonce=g.nonce)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    """Password reset page"""
    flash('Password reset functionality coming soon!', 'info')
    return redirect(url_for('login'))


# =============================================================================
# MAIN ROUTES
# =============================================================================

@app.route('/')
def home():
    """Home page - redirect to login or dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/create_invoice')
def create_invoice():
    """Create new invoice form"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    prefill_data = {}
    user_profile = get_user_profile(session['user_id'])
    if user_profile:
        prefill_data = {
            'company_name': user_profile.get('company_name', ''),
            'company_address': user_profile.get('company_address', ''),
            'company_phone': user_profile.get('company_phone', ''),
            'company_email': user_profile.get('email', ''),
            'company_tax_id': user_profile.get('company_tax_id', ''),
            'seller_ntn': user_profile.get('seller_ntn', ''),
            'seller_strn': user_profile.get('seller_strn', '')
        }

    return render_template('form.html', prefill_data=prefill_data, nonce=g.nonce)


@app.route('/preview_invoice', methods=['POST'])
@limiter.limit("5 per minute")
def preview_invoice():
    """Preview invoice before download"""
    try:
        invoice_data = prepare_invoice_data(request.form, request.files)

        if 'user_id' in session and 'items' in invoice_data:
            invoice_type = invoice_data.get('invoice_type', 'S')
            if invoice_type in ['S', 'E']:
                stock_validation = validate_stock_availability(session['user_id'], invoice_data['items'])
                if not stock_validation['success']:
                    flash(f'❌ Cannot create invoice: {stock_validation["message"]}', 'error')
                    return redirect(url_for('create_invoice'))

        if 'user_id' in session:
            invoice_type = invoice_data.get('invoice_type', 'S')
            if invoice_type == 'P':
                invoice_data['invoice_number'] = generate_unique_po_number(session['user_id'])
            else:
                invoice_data['invoice_number'] = generate_unique_invoice_number(session['user_id'])

        fbr_invoice = FBRInvoice(invoice_data)
        fbr_summary = fbr_invoice.get_fbr_summary()
        fbr_qr_code = fbr_summary['qr_code'] if fbr_summary['is_compliant'] else None
        custom_qr_b64 = generate_custom_qr(invoice_data)

        save_pending_invoice(session['user_id'], invoice_data)
        session['invoice_finalized'] = False

        return render_template(
            'invoice.html',
            data=invoice_data,
            preview=True,
            custom_qr_b64=custom_qr_b64,
            fbr_qr_code=fbr_qr_code,
            fbr_compliant=fbr_summary['is_compliant'],
            fbr_errors=fbr_summary['errors'],
            nonce=g.nonce
        )

    except Exception as e:
        flash(f'Error generating preview: {str(e)}', 'error')
        return redirect(url_for('create_invoice'))


@app.route('/download_invoice', methods=['POST'])
def download_invoice():
    """Download invoice as PDF"""
    try:
        if session.get('invoice_finalized'):
            flash('⚠️ Invoice already downloaded. Create a new one.', 'warning')
            return redirect(url_for('create_invoice'))

        data = get_pending_invoice(session['user_id'])

        if not data:
            flash('❌ No invoice to download. Please create an invoice first.', 'error')
            return redirect(url_for('create_invoice'))

        if 'user_id' in session and 'items' in data:
            invoice_type = data.get('invoice_type', 'S')
            if invoice_type in ['S', 'E']:
                stock_validation = validate_stock_availability(session['user_id'], data['items'])
                if not stock_validation['success']:
                    flash(f'❌ Stock changed! {stock_validation["message"]}', 'error')
                    clear_pending_invoice(session['user_id'])
                    session.pop('invoice_finalized', None)
                    return redirect(url_for('create_invoice'))

        fbr_invoice = FBRInvoice(data)
        fbr_summary = fbr_invoice.get_fbr_summary()
        fbr_qr_code = fbr_summary['qr_code'] if fbr_summary['is_compliant'] else None
        custom_qr_b64 = generate_custom_qr(data)

        # Render HTML for PDF - use invoice_pdf.html template for PDF generation
        html_content = render_template(
            'invoice_pdf.html',
            data=data,
            preview=False,
            custom_qr_b64=custom_qr_b64,
            fbr_qr_code=fbr_qr_code,
            fbr_compliant=fbr_summary['is_compliant'],
            nonce=g.nonce
        )

        # Generate PDF
        pdf_bytes = generate_pdf(html_content, app.root_path)

        # Update stock & save invoice
        if 'user_id' in session and 'items' in data:
            invoice_type = data.get('invoice_type', 'S')

            try:
                update_stock_on_invoice(
                    session['user_id'],
                    data['items'],
                    invoice_type,
                    data.get('invoice_number')
                )

                if invoice_type == 'P':
                    from core.purchases import save_purchase_order
                    save_purchase_order(session['user_id'], data)
                else:
                    save_user_invoice(session['user_id'], data)

                session['invoice_finalized'] = True
                flash(random_success_message('invoice_created'), 'success')

            except Exception as e:
                print(f"❌ CRITICAL: Invoice save failed: {e}")
                flash('⚠️ Invoice generated but not saved. Contact support.', 'error')

        clear_pending_invoice(session['user_id'])

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=invoice_{data["invoice_number"]}.pdf'}
        )

    except Exception as e:
        print(f"❌ PDF generation error: {e}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('create_invoice'))


@app.route('/cancel_invoice')
def cancel_invoice():
    """Cancel pending invoice"""
    if 'user_id' in session:
        clear_pending_invoice(session['user_id'])
        session.pop('invoice_finalized', None)
        flash('Invoice cancelled', 'info')
    return redirect(url_for('create_invoice'))


# =============================================================================
# DASHBOARD & HISTORY
# =============================================================================

@app.route("/dashboard")
def dashboard():
    """Main dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_business_summary, get_client_analytics

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute(
        'SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND is_active = TRUE',
        (session['user_id'],)
    )
    total_products = c.fetchone()[0]

    c.execute('''
        SELECT COUNT(*) FROM inventory_items
        WHERE user_id = ? AND current_stock <= min_stock_level AND current_stock > 0
    ''', (session['user_id'],))
    low_stock_items = c.fetchone()[0]

    c.execute(
        'SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND current_stock = 0',
        (session['user_id'],)
    )
    out_of_stock_items = c.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        user_email=session['user_email'],
        get_business_summary=get_business_summary,
        get_client_analytics=get_client_analytics,
        total_products=total_products,
        low_stock_items=low_stock_items,
        out_of_stock_items=out_of_stock_items,
        nonce=g.nonce
    )


@app.route("/invoice_history")
def invoice_history():
    """Invoice history and management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_user_invoices, get_invoice_count

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    limit = 10
    offset = (page - 1) * limit

    invoices = get_user_invoices(session['user_id'], limit=limit, offset=offset, search=search)
    total_invoices = get_invoice_count(session['user_id'], search=search)
    total_pages = (total_invoices + limit - 1) // limit

    return render_template(
        "invoice_history.html",
        invoices=invoices,
        current_page=page,
        total_pages=total_pages,
        search=search,
        nonce=g.nonce
    )


# =============================================================================
# INVENTORY ROUTES
# =============================================================================

@app.route("/inventory")
def inventory():
    """Inventory management dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, name, sku, category, current_stock, min_stock_level,
               cost_price, selling_price, supplier, location
        FROM inventory_items
        WHERE user_id = ? AND is_active = TRUE
        ORDER BY name
    ''', (session['user_id'],))

    raw_items = c.fetchall()
    conn.close()

    inventory_items = [{
        'id': item[0],
        'name': item[1],
        'sku': item[2],
        'category': item[3],
        'current_stock': item[4],
        'min_stock_level': item[5],
        'cost_price': item[6],
        'selling_price': item[7],
        'supplier': item[8],
        'location': item[9]
    } for item in raw_items]

    low_stock_alerts = InventoryManager.get_low_stock_alerts(session['user_id'])

    return render_template(
        "inventory.html",
        inventory_items=inventory_items,
        low_stock_alerts=low_stock_alerts,
        nonce=g.nonce
    )


@app.route("/inventory_reports")
def inventory_reports():
    """Inventory analytics and reports dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.reports import InventoryReports

    bcg_matrix = InventoryReports.get_bcg_matrix(session['user_id'])
    turnover = InventoryReports.get_stock_turnover(session['user_id'], days=30)
    profitability = InventoryReports.get_profitability_analysis(session['user_id'])
    slow_movers = InventoryReports.get_slow_movers(session['user_id'], days_threshold=90)

    return render_template(
        "inventory_reports.html",
        bcg_matrix=bcg_matrix,
        turnover=turnover[:10],
        profitability=profitability[:10],
        slow_movers=slow_movers,
        nonce=g.nonce
    )


@app.route("/add_product", methods=['POST'])
def add_product():
    """Add new product to inventory"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager

    product_data = {
        'name': request.form.get('name'),
        'sku': request.form.get('sku'),
        'category': request.form.get('category'),
        'description': request.form.get('description'),
        'current_stock': int(request.form.get('current_stock', 0)),
        'min_stock_level': int(request.form.get('min_stock_level', 5)),
        'cost_price': float(request.form.get('cost_price', 0)),
        'selling_price': float(request.form.get('selling_price', 0)),
        'supplier': request.form.get('supplier'),
        'location': request.form.get('location')
    }

    product_id = InventoryManager.add_product(session['user_id'], product_data)

    if product_id:
        initial_stock = product_data['current_stock']
        if initial_stock > 0:
            InventoryManager.update_stock(
                session['user_id'],
                product_id,
                initial_stock,
                'initial_stock',
                None,
                f"Product created with initial stock: {initial_stock} units"
            )
        flash(random_success_message('product_added'), 'success')
    else:
        flash('Error adding product. SKU might already exist.', 'error')

    return redirect(url_for('inventory'))


@app.route("/delete_product", methods=['POST'])
def delete_product():
    """Remove product from inventory with audit trail"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager

    product_id = request.form.get('product_id')
    reason = request.form.get('reason')
    notes = request.form.get('notes', '')

    full_reason = f"{reason}. {notes}".strip()

    success = InventoryManager.delete_product(session['user_id'], product_id, full_reason)

    if success:
        flash('✅ Product removed successfully', 'success')
    else:
        flash('❌ Error removing product', 'error')

    return redirect(url_for('inventory'))


@app.route("/adjust_stock", methods=['POST'])
def adjust_stock():
    """Adjust product stock quantity"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager

    product_id = request.form.get('product_id')
    new_quantity = int(request.form.get('new_quantity'))
    notes = request.form.get('notes', 'Manual adjustment')

    success = InventoryManager.update_stock(
        session['user_id'],
        product_id,
        new_quantity,
        'adjustment',
        None,
        notes
    )

    if success:
        flash(random_success_message('stock_updated'), 'success')
    else:
        flash('Error updating stock', 'error')

    return redirect(url_for('inventory'))


@app.route("/api/inventory_items")
def get_inventory_items_api():
    """API endpoint for inventory items (for invoice form)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('''
        SELECT id, name, selling_price, current_stock
        FROM inventory_items
        WHERE user_id = ? AND is_active = TRUE AND current_stock > 0
        ORDER BY name
    ''', (session['user_id'],))

    items = c.fetchall()
    conn.close()

    inventory_data = [{
        'id': item[0],
        'name': item[1],
        'price': float(item[2]) if item[2] else 0,
        'stock': item[3]
    } for item in items]

    return jsonify(inventory_data)


@app.route("/download_inventory_report")
def download_inventory_report():
    """Download inventory as CSV"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager
    import csv

    inventory_data = InventoryManager.get_inventory_report(session['user_id'])

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Product Name', 'SKU', 'Category', 'Current Stock', 'Min Stock',
        'Cost Price', 'Selling Price', 'Supplier', 'Location'
    ])

    for item in inventory_data:
        writer.writerow([
            item['name'], item['sku'], item['category'], item['current_stock'],
            item['min_stock'], item['cost_price'], item['selling_price'],
            item['supplier'], item['location']
        ])

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventory_report.csv"}
    )


# =============================================================================
# SETTINGS & DEVICE MANAGEMENT
# =============================================================================

@app.route("/settings", methods=['GET', 'POST'])
def settings():
    """User settings page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_user_profile, update_user_profile, change_user_password, verify_user

    user_profile = get_user_profile(session['user_id'])

    if request.method == 'POST':
        if 'update_profile' in request.form:
            update_user_profile(
                session['user_id'],
                company_name=request.form.get('company_name'),
                company_address=request.form.get('company_address'),
                company_phone=request.form.get('company_phone'),
                company_tax_id=request.form.get('company_tax_id'),
                seller_ntn=request.form.get('seller_ntn'),
                seller_strn=request.form.get('seller_strn'),
                preferred_currency=request.form.get('preferred_currency')
            )
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('settings'))

        elif 'change_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

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


@app.route("/devices")
def devices():
    """Manage active devices"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.session_manager import SessionManager
    active_sessions = SessionManager.get_active_sessions(session['user_id'])

    return render_template(
        "devices.html",
        sessions=active_sessions,
        current_token=session.get('session_token'),
        nonce=g.nonce
    )


@app.route("/revoke_device/<token>")
def revoke_device(token):
    """Revoke specific device session"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.session_manager import SessionManager

    if token == session.get('session_token'):
        flash('❌ Cannot revoke current session', 'error')
    else:
        SessionManager.revoke_session(token)
        flash('✅ Device session revoked', 'success')

    return redirect(url_for('devices'))


@app.route("/revoke_all_devices")
def revoke_all_devices():
    """Revoke all other sessions"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.session_manager import SessionManager
    SessionManager.revoke_all_sessions(
        session['user_id'],
        except_token=session.get('session_token')
    )

    flash('✅ All other devices logged out', 'success')
    return redirect(url_for('devices'))


# =============================================================================
# STATIC PAGES
# =============================================================================

@app.route("/terms")
def terms():
    return render_template("terms.html", nonce=g.nonce)


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", nonce=g.nonce)


@app.route("/about")
def about():
    return render_template("about.html", nonce=g.nonce)


@app.route("/donate")
def donate():
    return render_template("donate.html", nonce=g.nonce)


# =============================================================================
# SERVICE WORKER & STATIC FILES
# =============================================================================

@app.route('/sw.js')
def service_worker():
    """Serve service worker"""
    return send_from_directory('static', 'sw.js'), 200, {'Content-Type': 'application/javascript'}


# =============================================================================
# HEALTH & MONITORING
# =============================================================================

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        user_count = c.fetchone()[0]
        conn.close()

        import shutil
        total, used, free = shutil.disk_usage(".")
        disk_free_gb = free // (2**30)

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'users': user_count,
            'disk_free_gb': disk_free_gb,
            'version': '1.0.0'
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/status')
def system_status():
    """Detailed system status"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM user_invoices')
        total_invoices = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM inventory_items WHERE is_active = TRUE')
        total_products = c.fetchone()[0]

        conn.close()

        return jsonify({
            'status': 'operational',
            'stats': {
                'total_users': total_users,
                'total_invoices': total_invoices,
                'total_products': total_products
            },
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/backup')
def admin_backup():
    """Manual database backup trigger (admin only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if session['user_id'] != 1:
        return jsonify({'error': 'Admin only'}), 403

    try:
        import subprocess
        result = subprocess.run(
            ['python', 'backup_db.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Backup created successfully',
                'output': result.stdout
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.stderr
            }), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# DEBUG ROUTES (Development only)
# =============================================================================

@app.route('/debug')
def debug():
    """Debug route to check what's working"""
    debug_info = {
        'session': dict(session),
        'routes': [str(rule) for rule in app.url_map.iter_rules()],
        'user_authenticated': bool(session.get('user_id'))
    }
    return jsonify(debug_info)


# =============================================================================
# PLACEHOLDER ROUTES (Add implementations from original app.py)
# =============================================================================

# These routes need to be copied from your original app.py:
# - /purchase_orders
# - /stock_transactions
# - /customers
# - /suppliers
# - /expenses
# - /add_expense
# - /fix_customers
# - /debug_inventory
# - /debug_stock

# Add them here following the same clean pattern


# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
