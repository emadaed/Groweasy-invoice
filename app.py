# app.py 20 Dec 2025 04:44 AM PKST
# Standard library
import io
import time
import json
import base64
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import secrets

# Third-party
from sqlalchemy import text
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, render_template, request, send_file, session, redirect, url_for, send_from_directory, flash, jsonify, g, Response, make_response
from flask_compress import Compress
from dotenv import load_dotenv
# Local application
from fbr_integration import FBRInvoice
from core.inventory import InventoryManager
from core.invoice_logic import prepare_invoice_data
from core.qr_engine import make_qr_with_logo
from core.pdf_engine import generate_pdf, HAS_WEASYPRINT
from core.auth import create_user, verify_user, get_user_profile, update_user_profile, change_user_password, save_user_invoice
from core.purchases import save_purchase_order, get_purchase_orders, get_suppliers
from core.middleware import security_headers
from core.db import DB_ENGINE
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
# Environment setup
load_dotenv()
# Initialize Sentry for error monitoring
if os.getenv('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,  # Capture all for MVP monitoring
        environment='production' if os.getenv('RAILWAY_ENVIRONMENT') else 'development',
        send_default_pii=True
    )
    # Breadcrumbs for invoices (example — add more as needed)
    sentry_sdk.add_breadcrumb(category="invoice", message="app_started", level="info")
    print("✅ Sentry monitoring enabled")

# Fun success messages
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

def random_success_message(category='default'):
    import random
    messages = SUCCESS_MESSAGES.get(category, SUCCESS_MESSAGES['invoice_created'])
    return random.choice(messages)

# App creation
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
# Fix template/static path for Railway
app_root = Path(__file__).parent
app.template_folder = str(app_root / "templates")
app.static_folder = str(app_root / "static")
print(f"✅ Templates folder: {app.template_folder}")
print(f"✅ Static folder: {app.static_folder}")

##from tasks import celery
##celery.conf.update(app.config)
from core.cache import init_cache, get_user_profile_cached
init_cache(app)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Rate Limiting
REDIS_URL = os.getenv('REDIS_URL', 'memory://')
app.config['REDIS_URL'] = REDIS_URL
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=REDIS_URL
)

# Middleware
Compress(app)
# Exclude PDFs from compression to prevent corruption
app.config['COMPRESS_MIMETYPES'] = [
    'text/html',
    'text/css',
    'text/xml',
    'application/json',
    'application/javascript'
]
security_headers(app)

# === REDUCE LOG NOISE (fixes Railway rate-limit warning) ===
import logging
# Set root logger to INFO (your own prints stay)
logging.getLogger().setLevel(logging.WARNING)
# Silence the very noisy third-party libraries
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('weasyprint').setLevel(logging.ERROR)
logging.getLogger('fontTools').setLevel(logging.ERROR)
logging.getLogger('PIL').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

# Initialize purchase tables
from core.purchases import init_purchase_tables
try:
    init_purchase_tables()
    print("✅ Purchase tables initialized successfully")
except Exception as e:
    print(f"⚠️ Warning: Could not initialize purchase tables: {e}")
    if os.getenv('SENTRY_DSN'):
        sentry_sdk.capture_exception(e)

# Currency symbols
CURRENCY_SYMBOLS = {
    'PKR': 'Rs.',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'AED': 'د.إ',
    'SAR': '﷼'
}

#context processor
@app.context_processor
def inject_currency():
    """Make currency available in all templates"""
    currency = 'PKR'
    symbol = 'Rs.'

    if 'user_id' in session:
        profile = get_user_profile_cached(session['user_id'])
        if profile:
            currency = profile.get('preferred_currency', 'PKR')
            symbol = CURRENCY_SYMBOLS.get(currency, 'Rs.')

    return dict(currency=currency, currency_symbol=symbol)

# STOCK VALIDATION
def validate_stock_availability(user_id, invoice_items):
    """Validate stock availability BEFORE invoice processing"""
    if invoice_type == 'P':  # Purchase order - NO validation needed
        return {'success': True, 'message': 'Purchase order - no stock check needed'}
    try:
        with DB_ENGINE.begin() as conn:
            for item in invoice_items:
                if item.get('product_id'):
                    product_id = item['product_id']
                    requested_qty = int(item.get('qty', 1))

                    result = conn.execute(text("""
                        SELECT name, current_stock
                        FROM inventory_items
                        WHERE id = :product_id AND user_id = :user_id
                    """), {"product_id": product_id, "user_id": user_id}).fetchone()

                    if not result:
                        return {'success': False, 'message': "Product not found in inventory"}

                    product_name, current_stock = result
                    if current_stock < requested_qty:
                        return {
                            'success': False,
                            'message': f"Only {current_stock} units available for '{product_name}'"
                        }

            return {'success': True, 'message': 'Stock available'}

    except Exception as e:
        print(f"Stock validation error: {e}")
        return {'success': False, 'message': 'Stock validation failed'}

# update stock
def update_stock_on_invoice(user_id, invoice_items, invoice_type='S', invoice_number=None):
    """Update stock with invoice reference number"""
    try:

        for item in invoice_items:
            if item.get('product_id'):
                product_id = item['product_id']
                quantity = int(item.get('qty', 1))

                with DB_ENGINE.begin() as conn:
                    result = conn.execute(text("""
                        SELECT current_stock FROM inventory_items
                        WHERE id = :product_id AND user_id = :user_id
                    """), {"product_id": product_id, "user_id": user_id}).fetchone()

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

# save pending invoice
def save_pending_invoice(user_id, invoice_data):
    with DB_ENGINE.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pending_invoices (
                user_id INTEGER PRIMARY KEY,
                invoice_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("DELETE FROM pending_invoices WHERE user_id = :user_id"), {"user_id": user_id})
        conn.execute(text("""
            INSERT INTO pending_invoices (user_id, invoice_data)
            VALUES (:user_id, :invoice_data)
        """), {"user_id": user_id, "invoice_data": json.dumps(invoice_data)})

def get_pending_invoice(user_id):
    with DB_ENGINE.connect() as conn:  # Read-only, no begin()
        result = conn.execute(text("""
            SELECT invoice_data FROM pending_invoices WHERE user_id = :user_id
        """), {"user_id": user_id}).fetchone()
        return json.loads(result[0]) if result else None

def clear_pending_invoice(user_id):
    with DB_ENGINE.begin() as conn:
        conn.execute(text("DELETE FROM pending_invoices WHERE user_id = :user_id"), {"user_id": user_id})

#custom QR
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

# password reset
@app.route("/forgot_password", methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Simple password reset request with email simulation"""
    if request.method == 'POST':
        email = request.form.get('email')
        # Check if email exists in database
        with DB_ENGINE.connect() as conn:  # Read-only
            result = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()

        if result:
            flash('📧 Password reset instructions have been sent to your email.', 'success')
            flash('🔐 Development Note: In production, you would receive an email with reset link.', 'info')
            return render_template('reset_instructions.html', email=email, nonce=g.nonce)
        else:
            flash('❌ No account found with this email address.', 'error')
    return render_template('forgot_password.html', nonce=g.nonce)

#PW token
@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    """Password reset page (placeholder)"""
    # In production, you'd verify the token
    flash('Password reset functionality coming soon!', 'info')
    return redirect(url_for('login'))

# home
@app.route('/')
def home():
    """Home page - redirect to login or dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# create invoice
@app.route('/create_invoice')
def create_invoice():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    prefill_data = {}
    user_profile = get_user_profile_cached(session['user_id'])
    if user_profile:
        prefill_data = {
            'company_name': user_profile.get('company_name', ''),
            'company_address': user_profile.get('company_address', ''),
            'company_phone': user_profile.get('company_phone', ''),
            'company_email': user_profile.get('email', ''),
            'company_tax_id': user_profile.get('company_tax_id', ''),
            'seller_ntn': user_profile.get('seller_ntn', ''),  # 🆕
            'seller_strn': user_profile.get('seller_strn', '')  # 🆕
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

# INVENTORY
@app.route("/inventory")
def inventory():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with DB_ENGINE.connect() as conn:
        items = conn.execute(text("""
            SELECT id, name, sku, category, current_stock, min_stock_level,
                   cost_price, selling_price, supplier, location
            FROM inventory_items
            WHERE user_id = :user_id AND is_active = TRUE
            ORDER BY name
        """), {"user_id": session['user_id']}).fetchall()

    # Convert to dicts
    inventory_items = [dict(row._mapping) for row in items]


    from core.inventory import InventoryManager
    low_stock_alerts = InventoryManager.get_low_stock_alerts(session['user_id'])

    return render_template("inventory.html", inventory_items=inventory_items, low_stock_alerts=low_stock_alerts, nonce=g.nonce)

# inventory reports
@app.route("/inventory_reports")
def inventory_reports():
    """Inventory analytics and reports dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.reports import InventoryReports

    # Get all reports
    bcg_matrix = InventoryReports.get_bcg_matrix(session['user_id'])
    turnover = InventoryReports.get_stock_turnover(session['user_id'], days=30)
    profitability = InventoryReports.get_profitability_analysis(session['user_id'])
    slow_movers = InventoryReports.get_slow_movers(session['user_id'], days_threshold=90)

    return render_template("inventory_reports.html",
                         bcg_matrix=bcg_matrix,
                         turnover=turnover[:10],  # Top 10
                         profitability=profitability[:10],  # Top 10
                         slow_movers=slow_movers,
                         nonce=g.nonce)

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
        # 🆕 CREATE AUDIT TRAIL - Initial stock entry
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

#delete
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

# API inventory items
@app.route("/api/inventory_items")
def get_inventory_items_api():
    """API endpoint for inventory items (for invoice form)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    with DB_ENGINE.connect() as conn:
        items = conn.execute(text("""
            SELECT id, name, selling_price, current_stock
            FROM inventory_items
            WHERE user_id = :user_id AND is_active = TRUE AND current_stock > 0
            ORDER BY name
        """), {"user_id": session['user_id']}).fetchall()

    inventory_data = [{
        'id': item[0],
        'name': item[1],
        'price': float(item[2]) if item[2] else 0,
        'stock': item[3]
    } for item in items]

    return jsonify(inventory_data)

# stock adjustment
@app.route("/adjust_stock_audit", methods=['POST'])
@limiter.limit("10 per minute")
def adjust_stock_audit():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    product_id = request.form.get('product_id')
    adjustment_type = request.form.get('adjustment_type')
    quantity = int(request.form.get('quantity', 0))
    new_cost_price = request.form.get('new_cost_price')
    new_selling_price = request.form.get('new_selling_price')
    reason = request.form.get('reason', '')
    notes = request.form.get('notes', '')

    try:
        from core.inventory import InventoryManager
        from core.db import DB_ENGINE
        from sqlalchemy import text
        from core.auth import get_user_profile  # FIXED: remove "_cached"

        # Get user's currency
        user_profile = get_user_profile(user_id)
        currency_code = user_profile.get('preferred_currency', 'PKR') if user_profile else 'PKR'
        currency_symbol = CURRENCY_SYMBOLS.get(currency_code, 'Rs.')

        # Get product info
        product = InventoryManager.get_product_details(product_id, user_id)
        if not product:
            flash('Product not found', 'error')
            return redirect(url_for('inventory'))

        # Calculate new stock
        current_stock = product['current_stock']
        if adjustment_type == 'add_stock':
            new_stock = current_stock + quantity
            movement_type = 'stock_adjustment_add'
        elif adjustment_type == 'remove_stock':
            new_stock = current_stock - quantity
            movement_type = 'stock_adjustment_remove'
        elif adjustment_type == 'set_stock':
            new_stock = quantity
            movement_type = 'stock_adjustment_set'
        elif adjustment_type == 'damaged':
            new_stock = current_stock - quantity
            movement_type = 'damaged_goods'
        elif adjustment_type == 'found_stock':
            new_stock = current_stock + quantity
            movement_type = 'found_stock'
        else:
            flash('Invalid adjustment type', 'error')
            return redirect(url_for('inventory'))

        # Update stock
        success = InventoryManager.update_stock(
            user_id=user_id,
            product_id=product_id,
            new_quantity=new_stock,
            movement_type=movement_type,
            reference_id=f"ADJ-{int(time.time())}",
            notes=f"{reason}. {notes}"
        )

        # Update prices
        if success and (new_cost_price or new_selling_price):
            with DB_ENGINE.begin() as conn:
                updates = []
                params = {"product_id": product_id, "user_id": user_id}

                if new_cost_price and new_cost_price.strip():
                    updates.append("cost_price = :cost_price")
                    params["cost_price"] = float(new_cost_price)

                if new_selling_price and new_selling_price.strip():
                    updates.append("selling_price = :selling_price")
                    params["selling_price"] = float(new_selling_price)

                if updates:
                    sql = f"UPDATE inventory_items SET {', '.join(updates)} WHERE id = :product_id AND user_id = :user_id"
                    conn.execute(text(sql), params)

        if success:
            flash(f'✅ {product["name"]} updated! Stock: {current_stock}→{new_stock}', 'success')
        else:
            flash('Error updating product', 'error')

        return redirect(url_for('inventory'))

    except Exception as e:
        print(f"Stock adjustment error: {e}")
        flash('Error updating product', 'error')
        return redirect(url_for('inventory'))

# inventory report
@app.route("/download_inventory_report")
def download_inventory_report():
    """Download inventory as CSV"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager
    import csv
    import io

    inventory_data = InventoryManager.get_inventory_report(session['user_id'])

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Product Name', 'SKU', 'Category', 'Current Stock', 'Min Stock',
                    'Cost Price', 'Selling Price', 'Supplier', 'Location'])

    # Write data
    for item in inventory_data:
        writer.writerow([
            item['name'], item['sku'], item['category'], item['current_stock'],
            item['min_stock'], item['cost_price'], item['selling_price'],
            item['supplier'], item['location']
        ])

    # Return CSV file
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=inventory_report.csv"}
    )

#SETTINGS
@app.route("/settings", methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_user_profile, update_user_profile, change_user_password, verify_user

    user_profile = get_user_profile_cached(session['user_id'])

    if request.method == 'POST':
        # Handle profile update
        if 'update_profile' in request.form:
            company_name = request.form.get('company_name')
            company_address = request.form.get('company_address')
            company_phone = request.form.get('company_phone')
            company_tax_id = request.form.get('company_tax_id')
            seller_ntn = request.form.get('seller_ntn')  # 🆕 FBR field
            seller_strn = request.form.get('seller_strn')  # 🆕 FBR field
            preferred_currency = request.form.get('preferred_currency')

            update_user_profile(
                session['user_id'],
                company_name=company_name,
                company_address=company_address,
                company_phone=company_phone,
                company_tax_id=company_tax_id,
                seller_ntn=seller_ntn,  # 🆕 Pass to function
                seller_strn=seller_strn,  # 🆕 Pass to function
                preferred_currency=preferred_currency
            )

            flash('Settings updated successfully!', 'success')
            response = make_response(redirect(url_for('settings')))
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

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
#device management
@app.route("/devices")
def devices():
    """Manage active devices"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.session_manager import SessionManager
    active_sessions = SessionManager.get_active_sessions(session['user_id'])

    return render_template("devices.html",
                         sessions=active_sessions,
                         current_token=session.get('session_token'),
                         nonce=g.nonce)
# revoke tokens
@app.route("/revoke_device/<token>")
def revoke_device(token):
    """Revoke specific device session"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.session_manager import SessionManager

    # Don't allow revoking current session
    if token == session.get('session_token'):
        flash('❌ Cannot revoke current session', 'error')
    else:
        SessionManager.revoke_session(token)
        flash('✅ Device session revoked', 'success')

    return redirect(url_for('devices'))

# revoke devices
@app.route("/revoke_all_devices")
def revoke_all_devices():
    """Revoke all other sessions"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.session_manager import SessionManager
    SessionManager.revoke_all_sessions(session['user_id'], except_token=session.get('session_token'))

    flash('✅ All other devices logged out', 'success')
    return redirect(url_for('devices'))

# Login
@app.route("/login", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user_id = verify_user(email, password)
        if user_id:
            from core.session_manager import SessionManager

            # Check location restrictions
            if not SessionManager.check_location_restrictions(user_id, request.remote_addr):
                flash('❌ Login not allowed from this location', 'error')
                return render_template('login.html', nonce=g.nonce)

            # Create secure session
            session_token = SessionManager.create_session(user_id, request)

            session['user_id'] = user_id
            session['user_email'] = email
            session['session_token'] = session_token

            flash(random_success_message('login'), 'success')
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials', nonce=g.nonce)

    # GET request - show login form
    return render_template('login.html', nonce=g.nonce)

# leagal pages
@app.route("/terms")
def terms():
    return render_template("terms.html", nonce=g.nonce)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", nonce=g.nonce)

@app.route("/about")
def about():
    return render_template("about.html", nonce=g.nonce)

# register
@app.route("/register", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        # Validate terms acceptance
        if not request.form.get('agree_terms'):
            flash('❌ You must agree to Terms of Service to register', 'error')
            return render_template('register.html', nonce=g.nonce)

        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name', '')

        # 🆕 ADD DEBUG LOGGING
        print(f"📝 Attempting to register user: {email}")
        print(f"🔑 Password length: {len(password) if password else 0}")

        user_created = create_user(email, password, company_name)
        print(f"✅ User creation result: {user_created}")

        if user_created:
            flash('✅ Account created! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('❌ User already exists or registration failed', 'error')
            return render_template('register.html', nonce=g.nonce)

    # GET request - show form
    return render_template('register.html', nonce=g.nonce)

# dashboard
@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_business_summary, get_client_analytics

    with DB_ENGINE.connect() as conn:
        total_products = conn.execute(text("""
            SELECT COUNT(*) FROM inventory_items
            WHERE user_id = :user_id AND is_active = TRUE
        """), {"user_id": session['user_id']}).scalar()

        low_stock_items = conn.execute(text("""
            SELECT COUNT(*) FROM inventory_items
            WHERE user_id = :user_id AND current_stock <= min_stock_level AND current_stock > 0
        """), {"user_id": session['user_id']}).scalar()

        out_of_stock_items = conn.execute(text("""
            SELECT COUNT(*) FROM inventory_items
            WHERE user_id = :user_id AND current_stock = 0
        """), {"user_id": session['user_id']}).scalar()

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

# logout
@app.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))  # Changed from 'home' to 'login'

# donate
@app.route("/donate")
def donate():
    return render_template("donate.html", nonce=g.nonce)

# preview and download
from flask.views import MethodView
from core.services import InvoiceService
from core.number_generator import NumberGenerator
from core.purchases import save_purchase_order    # ADD
from flask import send_file, current_app
import io
import json  # ADD
from sqlalchemy import text  # ADD
from core.db import DB_ENGINE  # ADD

class InvoiceView(MethodView):
    def get(self):
        """Handle GET requests for download"""
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_id = session['user_id']
        invoice_number = request.args.get('invoice_number')
        invoice_type = request.args.get('invoice_type', 'S')

        if not invoice_number:
            flash("No document specified.", "error")
            return redirect(url_for('create_invoice'))

        return self._download_document(user_id, invoice_number, invoice_type)

    def post(self):
        """Handle POST requests for preview"""
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_id = session['user_id']
        service = InvoiceService(user_id)
        form_data = request.form
        files = request.files
        action = request.args.get('action', 'preview')

        try:
            if action == 'preview':
                service.process(form_data, files, action)

                # Generate proper invoice/PO numbers
                invoice_type = service.data.get('invoice_type', 'S')

                if invoice_type == 'P':
                    po_number = NumberGenerator.generate_po_number(user_id)
                    service.data['invoice_number'] = po_number
                    session['last_invoice_data'] = service.data

                    save_purchase_order(user_id, service.data)
                    update_stock_on_invoice(user_id, service.data['items'], invoice_type='P', invoice_number=po_number)
                    flash(f"✅ Purchase Order {po_number} created! Stock added.", "success")
                else:
                    inv_number = NumberGenerator.generate_invoice_number(user_id)
                    service.data['invoice_number'] = inv_number
                    session['last_invoice_data'] = service.data

                    save_user_invoice(user_id, service.data)
                    update_stock_on_invoice(user_id, service.data['items'], invoice_type='S', invoice_number=inv_number)
                    flash(f"✅ Invoice {inv_number} created! Stock deducted.", "success")

                qr_b64 = generate_simple_qr(service.data)
                html = render_template('invoice_pdf.html', data=service.data, preview=True, custom_qr_b64=qr_b64)
                session['last_invoice_data'] = service.data
                return render_template('invoice_preview.html', html=html, data=service.data, nonce=g.nonce)

        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('create_invoice'))
        except Exception as e:
            current_app.logger.error(f"Invoice processing error: {str(e)}")
            flash("An unexpected error occurred. Please try again.", 'error')
            return redirect(url_for('create_invoice'))

    def _download_document(self, user_id, invoice_number, invoice_type):
        """Shared download logic"""
        try:
            if invoice_type == 'P':
                with DB_ENGINE.connect() as conn:
                    result = conn.execute(text("""
                        SELECT order_data FROM purchase_orders
                        WHERE user_id = :user_id AND po_number = :invoice_number
                        ORDER BY id DESC LIMIT 1
                    """), {"user_id": user_id, "invoice_number": invoice_number}).fetchone()
            else:
                with DB_ENGINE.connect() as conn:
                    result = conn.execute(text("""
                        SELECT invoice_data FROM user_invoices
                        WHERE user_id = :user_id AND invoice_number = :invoice_number
                        ORDER BY id DESC LIMIT 1
                    """), {"user_id": user_id, "invoice_number": invoice_number}).fetchone()

            if not result:
                flash("Document not found.", "error")
                return redirect(url_for('create_invoice'))

            service_data = json.loads(result[0])
            qr_b64 = generate_simple_qr(service_data)
            html = render_template('invoice_pdf.html', data=service_data, preview=False, custom_qr_b64=qr_b64)
            pdf_bytes = generate_pdf(html, current_app.root_path)

            if invoice_type == 'P':
                filename = f"purchase_order_{invoice_number}.pdf"
                flash("Purchase Order downloaded successfully!", "success")
            else:
                filename = f"invoice_{invoice_number}.pdf"
                flash("Invoice downloaded successfully!", "success")

            return send_file(
                io.BytesIO(pdf_bytes),
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )

        except Exception as e:
            current_app.logger.error(f"Download error: {str(e)}")
            flash("Download failed. Please try again.", 'error')
            return redirect(url_for('create_invoice'))
# Register route
app.add_url_rule('/invoice/process', view_func=InvoiceView.as_view('invoice_process'), methods=['GET', 'POST'])

# poll route
@app.route('/invoice/status/<user_id>')
def status(user_id):
    service = InvoiceService(int(user_id))
    result = service.redis_client.get(f"preview:{user_id}")
    if result:
        return jsonify({'ready': True, 'data': json.loads(result)})
    return jsonify({'ready': False})

#clean up
@app.route('/cancel_invoice')
def cancel_invoice():
    """Cancel pending invoice"""
    if 'user_id' in session:
        clear_pending_invoice(session['user_id'])
        session.pop('invoice_finalized', None)
        flash('Invoice cancelled', 'info')
    return redirect(url_for('create_invoice'))

# invoice history
@app.route("/invoice_history")
def invoice_history():
    """Invoice history and management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    limit = 20  # Invoices per page
    offset = (page - 1) * limit

    user_id = session['user_id']

    with DB_ENGINE.connect() as conn:
        # Base query
        base_sql = '''
            SELECT id, invoice_number, client_name, invoice_date, due_date, grand_total, status, created_at
            FROM user_invoices
            WHERE user_id = :user_id
        '''
        params = {"user_id": user_id}

        # Add search if provided
        if search:
            base_sql += ' AND (invoice_number ILIKE :search OR client_name ILIKE :search)'
            params["search"] = f"%{search}%"

        # Get total count for pagination
        count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS count_query"
        total_invoices = conn.execute(text(count_sql), params).scalar()

        # Get paginated invoices
        invoices_sql = base_sql + '''
            ORDER BY invoice_date DESC, created_at DESC
            LIMIT :limit OFFSET :offset
        '''
        params.update({"limit": limit, "offset": offset})
        invoices_result = conn.execute(text(invoices_sql), params).fetchall()

    # Convert to list of dicts for template
    invoices = []
    for row in invoices_result:
        invoices.append({
            'id': row[0],
            'invoice_number': row[1],
            'client_name': row[2],
            'invoice_date': row[3],
            'due_date': row[4],
            'grand_total': float(row[5]) if row[5] else 0.0,
            'status': row[6],
            'created_at': row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else ''
        })

    total_pages = (total_invoices + limit - 1) // limit  # Ceiling division

    return render_template(
        "invoice_history.html",
        invoices=invoices,
        current_page=page,
        total_pages=total_pages,
        search_query=search,
        total_invoices=total_invoices,
        nonce=g.nonce
    )

# purchase order
@app.route("/purchase_orders")
def purchase_orders():
    """Purchase order history"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.purchases import get_purchase_orders

    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    orders = get_purchase_orders(session['user_id'], limit=limit, offset=offset)

    return render_template("purchase_orders.html",
                         orders=orders,
                         current_page=page,
                         nonce=g.nonce)


# supplier management
@app.route("/suppliers")
def suppliers():
    """Supplier management"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.purchases import get_suppliers
    supplier_list = get_suppliers(session['user_id'])

    return render_template("suppliers.html",
                         suppliers=supplier_list,
                         nonce=g.nonce)

# CUSTOMER MANAGEMENT ROUTES
@app.route("/customers")
def customers():
    """Customer management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_customers
    customer_list = get_customers(session['user_id'])

    return render_template("customers.html", customers=customer_list, nonce=g.nonce)

# EXPENSE TRACKING ROUTES
@app.route("/expenses")
def expenses():
    """Expense tracking page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_expenses, get_expense_summary
    from datetime import datetime

    expense_list = get_expenses(session['user_id'])
    expense_summary = get_expense_summary(session['user_id'])
    today_date = datetime.now().strftime('%Y-%m-%d')

    return render_template("expenses.html",
                         expenses=expense_list,
                         expense_summary=expense_summary,
                         today_date=today_date,
                         nonce=g.nonce)

#add expense
@app.route("/add_expense", methods=['POST'])
def add_expense():
    """Add new expense"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import save_expense

    expense_data = {
        'description': request.form.get('description'),
        'amount': float(request.form.get('amount', 0)),
        'category': request.form.get('category'),
        'expense_date': request.form.get('expense_date'),
        'notes': request.form.get('notes', '')
    }

    if save_expense(session['user_id'], expense_data):
        flash('Expense added successfully!', 'success')
    else:
        flash('Error adding expense', 'error')

    return redirect(url_for('expenses'))

#fix customer
@app.route("/fix_customers")
def fix_customers():
    """One-time fix to populate customers from existing invoices"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with DB_ENGINE.begin() as conn:
        invoices = conn.execute(text("""
            SELECT invoice_number, client_name, grand_total
            FROM user_invoices WHERE user_id = :user_id
        """), {"user_id": session['user_id']}).fetchall()

        results = []
        for invoice in invoices:
            invoice_number, client_name, grand_total = invoice
            conn.execute(text("""
                INSERT OR IGNORE INTO customers
                (user_id, name, total_spent, invoice_count)
                VALUES (:user_id, :name, :total, 1)
            """), {"user_id": session['user_id'], "name": client_name, "total": grand_total})
            results.append(f"Added: {client_name} (Invoice: {invoice_number})")

    return "<br>".join(results)

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

#Backup Route (Manual Trigger)
@app.route('/admin/backup')
def admin_backup():
    """Manual database backup trigger (admin only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    # Simple admin check (first user is admin)
    if session['user_id'] != 1:
        return jsonify({'error': 'Admin only'}), 403

    try:
        import subprocess
        result = subprocess.run(['python', 'backup_db.py'],
                              capture_output=True,
                              text=True,
                              timeout=30)

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

# Health status
@app.route('/health')
def health_check():
    try:
        with DB_ENGINE.connect() as conn:
            user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()

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


#API status
@app.route('/api/status')
def system_status():
    """Detailed system status"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        with DB_ENGINE.connect() as conn:  # Read-only → connect(), not begin()
            total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()

            total_invoices = conn.execute(text("SELECT COUNT(*) FROM user_invoices")).scalar()

            total_products = conn.execute(text("""
                SELECT COUNT(*) FROM inventory_items
                WHERE is_active = TRUE
            """)).scalar()

        return jsonify({
            'status': 'operational',
            'stats': {
                'total_users': total_users or 0,
                'total_invoices': total_invoices or 0,
                'total_products': total_products or 0
            },
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        print(f"System status error: {e}")
        return jsonify({'error': 'Database error'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
