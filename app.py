# app.py 16 Jan 2026 05:44 AM PKST
# Standard library
import time
import json
import base64
import os
import io
from pathlib import Path
from datetime import datetime, timedelta
import secrets

# Third-party
from sqlalchemy import text
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, render_template, request, send_file, session, redirect, url_for, send_from_directory, flash, jsonify, g, Response, make_response, current_app
from flask_compress import Compress
from flask_session import Session
from dotenv import load_dotenv
import redis
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
app.secret_key = os.getenv('SECRET_KEY', 'your-development-secret-key-change-in-production')
# Fix template/static path for Railway
app_root = Path(__file__).parent
app.template_folder = str(app_root / "templates")
app.static_folder = str(app_root / "static")
print(f"✅ Templates folder: {app.template_folder}")
print(f"✅ Static folder: {app.static_folder}")

from core.cache import init_cache, get_user_profile_cached
init_cache(app)

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Redis session configuration
def setup_redis_sessions(app):
    """Configure Redis-based sessions with proper fallback"""
    REDIS_URL = os.getenv('REDIS_URL', '').strip()

    # Validate Redis URL
    if not REDIS_URL or REDIS_URL == 'memory://':
        print("⚠️ No Redis URL provided, using filesystem sessions")
        app.config.update(
            SESSION_TYPE='filesystem',
            SESSION_FILE_DIR='/tmp/flask_sessions',
            SESSION_FILE_THRESHOLD=100,
            SESSION_PERMANENT=True,
            PERMANENT_SESSION_LIFETIME=86400,
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax'
        )
        Session(app)
        return

    # Validate Redis URL format
    if not REDIS_URL.startswith(('redis://', 'rediss://', 'unix://')):
        print(f"⚠️ Invalid Redis URL format: {REDIS_URL[:50]}...")
        print("⚠️ Using filesystem sessions as fallback")
        app.config.update(
            SESSION_TYPE='filesystem',
            SESSION_FILE_DIR='/tmp/flask_sessions',
            SESSION_FILE_THRESHOLD=100
        )
        Session(app)
        return

    try:
        # Test Redis connection
        redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=5)
        redis_client.ping()
        print(f"✅ Redis connected: {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}")

        app.config.update(
            SESSION_TYPE='redis',
            SESSION_REDIS=redis_client,
            SESSION_PERMANENT=True,
            SESSION_USE_SIGNER=True,
            SESSION_KEY_PREFIX='invoice_sess:',
            PERMANENT_SESSION_LIFETIME=86400,
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax'
        )

        Session(app)
        print("✅ Redis sessions configured")

    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        app.config.update(
            SESSION_TYPE='filesystem',
            SESSION_FILE_DIR='/tmp/flask_sessions',
            SESSION_FILE_THRESHOLD=100
        )
        Session(app)
        print("✅ Fallback to filesystem sessions")
# Setup Redis sessions
setup_redis_sessions(app)

# Rate Limiting
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure rate limiting based on environment
REDIS_URL = os.getenv('REDIS_URL', 'memory://')

# In development, use memory storage to avoid Redis dependency
if os.getenv('FLASK_ENV') == 'development' or 'memory://' in REDIS_URL:
    storage_uri = 'memory://'
    print("⚠️ Development mode: Using memory storage for rate limiting")
else:
    storage_uri = REDIS_URL
    print(f"✅ Production: Using Redis for rate limiting: {REDIS_URL[:30]}...")

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window",  # More reliable than moving-window
    on_breach=lambda req_limit: print(f"Rate limit exceeded: {req_limit}")
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

# REDUCE LOG NOISE
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

# Helper functions
def generate_simple_qr(data):
    """Generate a simple QR code for document data"""
    try:
        import qrcode
        from io import BytesIO
        import base64

        # Create minimal data for QR
        qr_data = {
            'doc_number': data.get('invoice_number', ''),
            'date': data.get('invoice_date', ''),
            'total': data.get('grand_total', 0)
        }

        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")

        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"QR generation error: {e}")
        return None

def clear_pending_invoice(user_id):
    """Clear pending invoice data"""
    try:
        # This function should be in your services module
        # For now, implementing a simple version
        from core.session_storage import SessionStorage
        SessionStorage.clear_data(user_id, 'last_invoice')
        print(f"Cleared pending invoice for user {user_id}")
        return True
    except Exception as e:
        print(f"Error clearing pending invoice: {e}")
        return False

def template_exists(template_name):
    """Check if a template exists"""
    try:
        app.jinja_env.get_template(template_name)
        return True
    except Exception:
        return False

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

@app.context_processor
def utility_processor():
    """Add utility functions to all templates"""
    def now():
        return datetime.now()

    def today():
        return datetime.now().date()

    def month_equalto_filter(value, month):
        """Custom filter for month comparison"""
        try:
            if hasattr(value, 'month'):
                return value.month == month
            elif isinstance(value, str):
                # Try to parse date string
                from datetime import datetime as dt
                # Handle different date formats
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']:
                    try:
                        date_obj = dt.strptime(value, fmt)
                        return date_obj.month == month
                    except:
                        continue
                return False
            return False
        except:
            return False

    return {
        'now': now,
        'today': today,
        'month_equalto': month_equalto_filter
    }
# STOCK VALIDATION
def validate_stock_availability(user_id, invoice_items, invoice_type='S'):
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

                with DB_ENGINE.connect() as conn:  # Changed to connect for read-only
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
    """Dedicated route for creating sales invoices ONLY"""
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
            'seller_ntn': user_profile.get('seller_ntn', ''),
            'seller_strn': user_profile.get('seller_strn', ''),
        }

    return render_template('form.html',
                         prefill_data=prefill_data,
                         nonce=g.nonce)

#create po
@app.route('/create_purchase_order')
def create_purchase_order():
    """Dedicated route for creating purchase orders"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    prefill_data = {}
    user_profile = get_user_profile_cached(session['user_id'])

    # Get suppliers for dropdown
    from core.purchases import get_suppliers
    suppliers = get_suppliers(session['user_id'])

    if user_profile:
        prefill_data = {
            'company_name': user_profile.get('company_name', ''),
            'company_address': user_profile.get('company_address', ''),
            'company_phone': user_profile.get('company_phone', ''),
            'company_email': user_profile.get('email', ''),
            'company_tax_id': user_profile.get('company_tax_id', ''),
            'seller_ntn': user_profile.get('seller_ntn', ''),
            'seller_strn': user_profile.get('seller_strn', ''),
        }

    return render_template('create_po.html',
                         prefill_data=prefill_data,
                         suppliers=suppliers,
                         nonce=g.nonce)

# create po process
@app.route('/create_po_process', methods=['POST'])
@limiter.limit("10 per minute")
def create_po_process():
    """Process purchase order creation (separate from invoices)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    try:
        # Extract PO-specific data
        po_data = {
            'document_type': 'purchase_order',
            'supplier_name': request.form.get('supplier_name'),
            'contact_person': request.form.get('contact_person'),
            'supplier_phone': request.form.get('supplier_phone'),
            'supplier_email': request.form.get('supplier_email'),
            'supplier_address': request.form.get('supplier_address'),
            'supplier_tax_id': request.form.get('supplier_tax_id'),
            'supplier_payment_terms': request.form.get('supplier_payment_terms'),
            'po_date': request.form.get('po_date'),
            'delivery_date': request.form.get('delivery_date'),
            'delivery_method': request.form.get('delivery_method'),
            'shipping_terms': request.form.get('shipping_terms'),
            'po_status': request.form.get('po_status'),
            'po_notes': request.form.get('po_notes'),
            'buyer_ntn': request.form.get('buyer_ntn'),
            'seller_ntn': request.form.get('seller_ntn'),
            'withholding_tax': float(request.form.get('withholding_tax', 0)),
            'sales_tax': float(request.form.get('sales_tax', 17)),
            'shipping_address': request.form.get('shipping_address'),
            'shipping_cost': float(request.form.get('shipping_cost', 0)),
            'insurance_cost': float(request.form.get('insurance_cost', 0)),
            'approved_by': request.form.get('approved_by'),
            'department': request.form.get('department'),
            'internal_notes': request.form.get('internal_notes'),
            'action': request.form.get('action', 'submit')
        }

        # Process items
        items = []
        total_amount = 0

        # Extract items from form data
        for key in request.form.keys():
            if key.startswith('items[') and key.endswith('][name]'):
                item_id = key.split('[')[1].split(']')[0]
                items.append({
                    'name': request.form.get(f'items[{item_id}][name]'),
                    'sku': request.form.get(f'items[{item_id}][sku]'),
                    'qty': int(request.form.get(f'items[{item_id}][qty]', 1)),
                    'price': float(request.form.get(f'items[{item_id}][price]', 0)),
                    'total': float(request.form.get(f'items[{item_id}][total]', 0)),
                    'supplier': request.form.get(f'items[{item_id}][supplier]'),
                    'notes': request.form.get(f'items[{item_id}][notes]')
                })
                total_amount += float(request.form.get(f'items[{item_id}][total]', 0))

        po_data['items'] = items
        po_data['subtotal'] = total_amount

        # Calculate taxes
        tax_amount = total_amount * (po_data['sales_tax'] / 100)
        po_data['tax_amount'] = tax_amount

        # Calculate grand total
        po_data['grand_total'] = total_amount + tax_amount + po_data['shipping_cost'] + po_data['insurance_cost']

        # Generate PO number
        from core.number_generator import NumberGenerator
        po_number = NumberGenerator.generate_po_number(user_id)
        po_data['invoice_number'] = po_number

        # Save to database
        save_purchase_order(user_id, po_data)

        # If submitted (not draft), update stock
        if po_data['action'] == 'submit' and po_data['po_status'] in ['approved', 'ordered']:
            update_stock_on_invoice(user_id, items, invoice_type='P', invoice_number=po_number)

        # Store for preview
        from core.session_storage import SessionStorage
        session_ref = SessionStorage.store_large_data(session['user_id'], 'last_po', po_data)
        session['last_po_ref'] = session_ref

        # Redirect to PO preview
        return redirect(url_for('po_preview', po_number=po_number))

    except Exception as e:
        current_app.logger.error(f"PO creation error: {str(e)}", exc_info=True)
        flash(f"❌ Error creating purchase order: {str(e)}", 'error')
        return redirect(url_for('create_purchase_order'))

@app.route('/po/preview/<po_number>')
def po_preview(po_number):
    """Preview purchase order"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    try:
        # Fetch PO data
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text("""
                SELECT order_data FROM purchase_orders
                WHERE user_id = :user_id AND po_number = :po_number
                ORDER BY created_at DESC LIMIT 1
            """), {"user_id": user_id, "po_number": po_number}).fetchone()

        if not result:
            flash("Purchase order not found", "error")
            return redirect(url_for('purchase_orders'))

        po_data = json.loads(result[0])

        # Generate QR for PO
        qr_b64 = generate_simple_qr(po_data)

        # Render PO-specific template
        html = render_template('purchase_order_pdf.html',
                             data=po_data,
                             preview=True,
                             custom_qr_b64=qr_b64)

        return render_template('po_preview.html',
                             html=html,
                             data=po_data,
                             po_number=po_number,
                             nonce=g.nonce)

    except Exception as e:
        current_app.logger.error(f"PO preview error: {str(e)}")
        flash("Error loading purchase order", "error")
        return redirect(url_for('purchase_orders'))

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
        from core.auth import get_user_profile

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
from core.purchases import save_purchase_order

class InvoiceView(MethodView):
    """Handles invoice creation and preview - RESTful design"""

    def get(self):
        """
        GET /invoice/process - Show preview or redirect
        SAFE: No side effects, idempotent
        """
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # If coming from a successful creation, show preview
        if 'last_invoice_ref' in session and request.args.get('preview'):
            from core.session_storage import SessionStorage
            invoice_data = SessionStorage.get_data(session['user_id'], session['last_invoice_ref'])

            if not invoice_data:
                flash("Invoice preview expired or not found", "error")
                return redirect(url_for('create_invoice'))

            # Generate QR for preview
            qr_b64 = generate_simple_qr(invoice_data)
            html = render_template('invoice_pdf.html',
                                 data=invoice_data,
                                 preview=True,
                                 custom_qr_b64=qr_b64)

            return render_template('invoice_preview.html',
                                 html=html,
                                 data=invoice_data,
                                 nonce=g.nonce)

        # Otherwise redirect to create form
        return redirect(url_for('create_invoice'))

    def post(self):
        """
        POST /invoice/process - Create invoice or purchase order
        NON-IDEMPOTENT: Creates new resource
        """
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_id = session['user_id']
        service = InvoiceService(user_id)
        form_data = request.form
        files = request.files
        invoice_type = form_data.get('invoice_type', 'S')

        try:
            # Process the form data
            service.process(form_data, files, 'create')

            # Generate document number
            if invoice_type == 'P':
                doc_number = NumberGenerator.generate_po_number(user_id)
                service.data['invoice_number'] = doc_number

                # Save as Purchase Order
                save_purchase_order(user_id, service.data)

                # Update stock (POs add stock)
                update_stock_on_invoice(user_id, service.data['items'],
                                      invoice_type='P',
                                      invoice_number=doc_number)

                flash(f"✅ Purchase Order {doc_number} created successfully!", "success")

            else:  # Sales Invoice
                doc_number = NumberGenerator.generate_invoice_number(user_id)
                service.data['invoice_number'] = doc_number

                # Validate stock BEFORE saving
                stock_check = validate_stock_availability(user_id, service.data['items'], invoice_type='S')
                if not stock_check['success']:
                    flash(f"❌ Stock issue: {stock_check['message']}", "error")
                    return redirect(url_for('create_invoice'))

                # Save invoice
                save_user_invoice(user_id, service.data)

                # Update stock (Invoices deduct stock)
                update_stock_on_invoice(user_id, service.data['items'],
                                      invoice_type='S',
                                      invoice_number=doc_number)

                flash(f"✅ Invoice {doc_number} created successfully!", "success")

            # Store for preview
            from core.session_storage import SessionStorage
            session_ref = SessionStorage.store_large_data(session['user_id'], 'last_invoice', service.data)
            session['last_invoice_ref'] = session_ref

            # Redirect to preview page (GET request, safe)
            return redirect(url_for('invoice_process', preview='true'))

        except ValueError as e:
            flash(f"❌ Validation error: {str(e)}", 'error')
            return redirect(url_for('create_invoice'))

        except Exception as e:
            current_app.logger.error(f"Invoice creation error: {str(e)}",
                                   exc_info=True,
                                   extra={'user_id': user_id,
                                          'invoice_type': invoice_type})
            flash("⚠️ An unexpected error occurred. Please try again.", 'error')
            return redirect(url_for('create_invoice'))

#invoice/download/<document_number>')
@app.route('/invoice/download/<document_number>')
@limiter.limit("10 per minute")  # Rate limiting to prevent abuse
def download_document(document_number):
    """
    Dedicated endpoint for document downloads
    GET requests are idempotent but have side effects (download tracking)

    Security features:
    - Rate limiting
    - CSRF protection via session
    - Download tracking
    - Cache control headers
    - Content-Disposition with safe filename
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    document_type = request.args.get('type', 'invoice')  # 'invoice' or 'purchase_order'

    try:
        # Log download attempt for analytics
        current_app.logger.info(f"Download attempt: user={user_id}, "
                              f"doc={document_number}, type={document_type}")

        # Fetch document data
        if document_type == 'purchase_order':
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT order_data, created_at
                    FROM purchase_orders
                    WHERE user_id = :user_id AND po_number = :doc_number
                    ORDER BY created_at DESC LIMIT 1
                """), {"user_id": user_id, "doc_number": document_number}).fetchone()

            if not result:
                flash("❌ Purchase order not found or access denied.", "error")
                return redirect(url_for('purchase_orders'))

            service_data = json.loads(result[0])
            created_at = result[1]
            document_type_name = "Purchase Order"
            template = 'purchase_order_pdf.html' if template_exists('purchase_order_pdf.html') else 'invoice_pdf.html'

        else:  # Sales Invoice
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT invoice_data, created_at
                    FROM user_invoices
                    WHERE user_id = :user_id AND invoice_number = :doc_number
                    ORDER BY created_at DESC LIMIT 1
                """), {"user_id": user_id, "doc_number": document_number}).fetchone()

            if not result:
                flash("❌ Invoice not found or access denied.", "error")
                return redirect(url_for('invoice_history'))

            service_data = json.loads(result[0])
            created_at = result[1]
            document_type_name = "Invoice"
            template = 'invoice_pdf.html'

        # Generate QR code
        qr_b64 = generate_simple_qr(service_data)

        # Generate PDF with appropriate template
        try:
            html = render_template(template,
                                 data=service_data,
                                 preview=False,
                                 custom_qr_b64=qr_b64,
                                 currency_symbol=g.get('currency_symbol', 'Rs.'))
            pdf_bytes = generate_pdf(html, current_app.root_path)
        except Exception as template_error:
            # Fallback to generic template if specific one fails
            current_app.logger.warning(f"Template {template} failed, falling back: {template_error}")
            html = render_template('invoice_pdf.html',
                                 data=service_data,
                                 preview=False,
                                 custom_qr_b64=qr_b64,
                                 currency_symbol=g.get('currency_symbol', 'Rs.'))
            pdf_bytes = generate_pdf(html, current_app.root_path)

        # Sanitize filename
        import re
        safe_doc_number = re.sub(r'[^\w\-]', '_', document_number)

        # Create filename with timestamp
        timestamp = created_at.strftime('%Y%m%d_%H%M') if created_at else datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"{document_type_name.replace(' ', '_')}_{safe_doc_number}_{timestamp}.pdf"

        # Create response with security headers
        response = make_response(send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        ))

        # Security headers to prevent caching sensitive documents
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Download-Options'] = 'noopen'

        # Track download in database (optional but recommended)
        try:
            with DB_ENGINE.begin() as conn:
                conn.execute(text("""
                    INSERT INTO download_logs
                    (user_id, document_type, document_number, downloaded_at, ip_address, user_agent)
                    VALUES (:user_id, :doc_type, :doc_number, CURRENT_TIMESTAMP, :ip, :ua)
                """), {
                    "user_id": user_id,
                    "doc_type": document_type,
                    "doc_number": document_number,
                    "ip": request.remote_addr,
                    "ua": request.headers.get('User-Agent', '')
                })
        except Exception as e:
            current_app.logger.warning(f"Download tracking failed: {e}")

        # Don't flash here - it won't show since we're sending a file
        # Instead, log the success
        current_app.logger.info(f"✅ {document_type_name} {document_number} downloaded by user {user_id}")
        return response

    except Exception as e:
        current_app.logger.error(f"Download error: {str(e)}",
                               exc_info=True,
                               extra={'user_id': user_id,
                                      'document_number': document_number})
        flash("❌ Download failed. Please try again.", 'error')
        return redirect(url_for('invoice_history' if document_type != 'purchase_order' else 'purchase_orders'))

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
    """Purchase order history with download options"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.purchases import get_purchase_orders

    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    orders = get_purchase_orders(session['user_id'], limit=limit, offset=offset)

    # Get user's currency for display
    user_profile = get_user_profile_cached(session['user_id'])
    currency_code = user_profile.get('preferred_currency', 'PKR') if user_profile else 'PKR'
    currency_symbol = CURRENCY_SYMBOLS.get(currency_code, 'Rs.')

    return render_template("purchase_orders.html",
                         orders=orders,
                         current_page=page,
                         currency_symbol=currency_symbol,
                         nonce=g.nonce)

#API endpoints for better UX
@app.route("/api/purchase_order/<po_number>")
@limiter.limit("30 per minute")
def get_purchase_order_details(po_number):
    """API endpoint to get PO details"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text("""
                SELECT order_data, status, created_at
                FROM purchase_orders
                WHERE user_id = :user_id AND po_number = :po_number
                ORDER BY created_at DESC LIMIT 1
            """), {"user_id": session['user_id'], "po_number": po_number}).fetchone()

        if not result:
            return jsonify({'error': 'Purchase order not found'}), 404

        order_data = json.loads(result[0])
        order_data['status'] = result[1]
        order_data['created_at'] = result[2].isoformat() if result[2] else None

        return jsonify(order_data), 200

    except Exception as e:
        current_app.logger.error(f"PO details error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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
