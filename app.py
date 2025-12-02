# app.py 30 Nov 2025 11:30 PM PKST
# Standard library
import io
import json
import base64
import os
import sqlite3
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
app.secret_key = os.getenv('SECRET_KEY')

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

# ===== NEW STOCK VALIDATION FUNCTIONS =====
def validate_stock_availability(user_id, invoice_items):
    """Validate stock availability BEFORE invoice processing"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        for item in invoice_items:
            if item.get('product_id'):
                product_id = item['product_id']
                requested_qty = int(item.get('qty', 1))

                # Get current stock
                c.execute('SELECT name, current_stock FROM inventory_items WHERE id = ? AND user_id = ?',
                         (product_id, user_id))
                result = c.fetchone()

                if not result:
                    return {'success': False, 'message': f"Product not found in inventory"}

                product_name, current_stock = result
                if current_stock < requested_qty:
                    return {
                        'success': False,
                        'message': f"Only {current_stock} units available for '{product_name}'"
                    }

        conn.close()
        return {'success': True, 'message': 'Stock available'}

    except Exception as e:
        print(f"Stock validation error: {e}")
        return {'success': False, 'message': 'Stock validation failed'}

def update_stock_on_invoice(user_id, invoice_items, invoice_type='S'):
    """Update stock based on invoice type: Sale (decrease) or Purchase (increase)"""
    try:
        from core.inventory import InventoryManager

        for item in invoice_items:
            if item.get('product_id'):
                product_id = item['product_id']
                quantity = int(item.get('qty', 1))

                # Get current stock
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute('SELECT current_stock FROM inventory_items WHERE id = ? AND user_id = ?',
                         (product_id, user_id))
                result = c.fetchone()
                conn.close()

                if result:
                    current_stock = result[0]

                    # 🆕 CALCULATE NEW STOCK BASED ON INVOICE TYPE
                    if invoice_type == 'P':
                        # Purchase Invoice: INCREASE stock
                        new_stock = current_stock + quantity
                        movement_type = 'purchase'
                        notes = f"Purchased {quantity} units via invoice"
                        print(f"📦 Stock increased: {item.get('name')} +{quantity} units")
                    else:
                        # Sale/Export Invoice: DECREASE stock
                        new_stock = current_stock - quantity
                        movement_type = 'sale'
                        notes = f"Sold {quantity} units via invoice"
                        print(f"✅ Stock deducted: {item.get('name')} -{quantity} units")

                    # Use existing inventory manager
                    success = InventoryManager.update_stock(
                        user_id, product_id, new_stock, movement_type, None, notes
                    )

                    if not success:
                        print(f"⚠️ Stock update failed for {item.get('name')}")

    except Exception as e:
        print(f"Error in update_stock_on_invoice: {e}")

def generate_unique_invoice_number(user_id):
    """Generate guaranteed unique invoice number per user"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        # Get the last invoice number for this user
        c.execute('''
            SELECT invoice_number FROM user_invoices
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        ''', (user_id,))

        result = c.fetchone()
        conn.close()

        if result:
            last_number = result[0]
            # Extract number from "INV-00123" format
            if last_number.startswith('INV-'):
                try:
                    last_num = int(last_number.split('-')[1])
                    return f"INV-{last_num + 1:05d}"
                except (ValueError, IndexError):
                    pass

        # Start from INV-00001 for new users
        return "INV-00001"

    except Exception as e:
        print(f"Invoice number generation error: {e}")
        return f"INV-{int(__import__('time').time())}"  # Fallback

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

@app.route("/forgot_password", methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Simple password reset request with email simulation"""
    if request.method == 'POST':
        email = request.form.get('email')

        # Check if email exists in database
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()

        if user:
            # In production: Send actual email with reset link
            # For now: Show reset instructions on screen
            flash('📧 Password reset instructions have been sent to your email.', 'success')
            flash('🔐 Development Note: In production, you would receive an email with reset link.', 'info')
            return render_template('reset_instructions.html', email=email, nonce=g.nonce)
        else:
            flash('❌ No account found with this email address.', 'error')

    return render_template('forgot_password.html', nonce=g.nonce)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    """Password reset page (placeholder)"""
    # In production, you'd verify the token
    flash('Password reset functionality coming soon!', 'info')
    return redirect(url_for('login'))

@app.route('/')
def home():
    """Home page - redirect to login or dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/create_invoice')
def create_invoice():
    """Direct invoice creation page for logged-in users"""
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

# NEW ROUTES INVENTORY AND USER SETTINGS

@app.route("/inventory")
def inventory():
    """Inventory management dashboard - FIXED VERSION"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.inventory import InventoryManager

    # Get inventory items
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, name, sku, category, current_stock, min_stock_level,
               cost_price, selling_price, supplier, location
        FROM inventory_items
        WHERE user_id = ? AND is_active = TRUE
        ORDER BY name
    ''', (session['user_id'],))

    # Convert tuples to dictionaries for template
    raw_items = c.fetchall()
    conn.close()

    inventory_items = []
    for item in raw_items:
        inventory_items.append({
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
        })

    # Get low stock alerts
    low_stock_alerts = InventoryManager.get_low_stock_alerts(session['user_id'])

    return render_template("inventory.html",
                         inventory_items=inventory_items,
                         low_stock_alerts=low_stock_alerts,
                         nonce=g.nonce)

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
        flash('Product added successfully!', 'success')
    else:
        flash('Error adding product. SKU might already exist.', 'error')

    return redirect(url_for('inventory'))

# stock adjustment and auto popualate routes
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

# stock adjustment
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
        flash('Stock updated successfully!', 'success')
    else:
        flash('Error updating stock', 'error')

    return redirect(url_for('inventory'))

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

    user_profile = get_user_profile(session['user_id'])

    if request.method == 'POST':
        # Handle profile update
        if 'update_profile' in request.form:
            company_name = request.form.get('company_name')
            company_address = request.form.get('company_address')
            company_phone = request.form.get('company_phone')
            company_tax_id = request.form.get('company_tax_id')
            seller_ntn = request.form.get('seller_ntn')  # 🆕 FBR field
            seller_strn = request.form.get('seller_strn')  # 🆕 FBR fie

            update_user_profile(
                session['user_id'],
                company_name=company_name,
                company_address=company_address,
                company_phone=company_phone,
                company_tax_id=company_tax_id,
                seller_ntn=seller_ntn,  # 🆕 Pass to function
                seller_strn=seller_strn  # 🆕 Pass to function
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

    from core.auth import get_business_summary, get_client_analytics

    # Get inventory stats
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Total products
    c.execute('SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND is_active = TRUE',
              (session['user_id'],))
    total_products = c.fetchone()[0]

    # Low stock items
    c.execute('''SELECT COUNT(*) FROM inventory_items
                 WHERE user_id = ? AND current_stock <= min_stock_level AND current_stock > 0''',
              (session['user_id'],))
    low_stock_items = c.fetchone()[0]

    # Out of stock items
    c.execute('SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND current_stock = 0',
              (session['user_id'],))
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

@app.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))  # Changed from 'home' to 'login'

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

        # 🛡️ STRICT STOCK VALIDATION - BLOCK PREVIEW IF INSUFFICIENT STOCK
        stock_warnings = []
        if 'user_id' in session and 'items' in invoice_data:
            stock_validation = validate_stock_availability(session['user_id'], invoice_data['items'])
            if not stock_validation['success']:
                flash(f'❌ Cannot create invoice: {stock_validation["message"]}', 'error')
                return redirect(url_for('create_invoice'))

        # Ensure unique invoice number
        if 'user_id' in session:
            invoice_data['invoice_number'] = generate_unique_invoice_number(session['user_id'])

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
                             stock_warnings=stock_warnings,  # 🆕 PASS WARNINGS TO TEMPLATE
                             nonce=g.nonce)

    except Exception as e:
        flash(f'Error generating preview: {str(e)}', 'error')
        return redirect(url_for('home'))

#download route

@app.route('/download_invoice', methods=['POST'])
def download_invoice():
    try:
        import json
        from core.pdf_engine import generate_pdf

        data = json.loads(request.form['data'])

        # 🛡️ STEP 1: VALIDATE STOCK AVAILABILITY BEFORE ANY PROCESSING
        if 'user_id' in session and 'items' in data:
            stock_validation = validate_stock_availability(session['user_id'], data['items'])
            if not stock_validation['success']:
                flash(f'❌ Cannot download: {stock_validation["message"]}', 'error')
                # Return to preview with error
                return redirect(url_for('preview_invoice'))

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

        # 🛡️ STEP 4: DEDUCT STOCK ONLY AFTER SUCCESSFUL PDF GENERATION
        if 'user_id' in session and 'items' in data:
            invoice_type = data.get('invoice_type', 'S')
            update_stock_on_invoice(session['user_id'], data['items'], invoice_type)

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

# invoice history

@app.route("/invoice_history")
def invoice_history():
    """Invoice history and management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_user_invoices, get_invoice_count

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    limit = 10  # Invoices per page
    offset = (page - 1) * limit

    # Get invoices
    invoices = get_user_invoices(session['user_id'], limit=limit, offset=offset, search=search)
    total_invoices = get_invoice_count(session['user_id'], search=search)
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

# ===== CUSTOMER MANAGEMENT ROUTES =====
@app.route("/customers")
def customers():
    """Customer management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from core.auth import get_customers
    customer_list = get_customers(session['user_id'])

    return render_template("customers.html", customers=customer_list, nonce=g.nonce)

# ===== EXPENSE TRACKING ROUTES =====
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

    import sqlite3

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Get all invoices for this user
    c.execute('SELECT invoice_number, client_name, grand_total FROM user_invoices WHERE user_id = ?', (session['user_id'],))
    invoices = c.fetchall()

    results = []
    for invoice in invoices:
        invoice_number, client_name, grand_total = invoice

        # Insert customer if not exists
        c.execute('''
            INSERT OR IGNORE INTO customers
            (user_id, name, total_spent, invoice_count)
            VALUES (?, ?, ?, 1)
        ''', (session['user_id'], client_name, grand_total))

        results.append(f"Added: {client_name} (Invoice: {invoice_number})")

    conn.commit()
    conn.close()
    return "<br>".join(results)
#debug invnetory

@app.route("/debug_inventory")
def debug_inventory():
    """Debug inventory state"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'})

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Get all inventory data
    c.execute('''
        SELECT id, name, current_stock, min_stock_level, selling_price
        FROM inventory_items WHERE user_id = ?
    ''', (session['user_id'],))

    items = c.fetchall()

    # Get stock movements
    c.execute('''
        SELECT product_id, movement_type, quantity, created_at
        FROM stock_movements WHERE user_id = ? ORDER BY created_at DESC LIMIT 10
    ''', (session['user_id'],))

    movements = c.fetchall()

    conn.close()

    return jsonify({
        'inventory_items': [{
            'id': item[0],
            'name': item[1],
            'current_stock': item[2],
            'min_stock': item[3],
            'price': item[4]
        } for item in items],
        'recent_movements': [{
            'product_id': mov[0],
            'type': mov[1],
            'quantity': mov[2],
            'time': mov[3]
        } for mov in movements]
    })

#debug stock

@app.route("/debug_stock")
def debug_stock():
    """Debug stock update issues"""
    if 'user_id' not in session:
        return "Not logged in"

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Check inventory items
    c.execute('SELECT id, name, current_stock FROM inventory_items WHERE user_id = ?', (session['user_id'],))
    items = c.fetchall()

    result = "<h3>Current Inventory:</h3>"
    for item in items:
        result += f"<p>ID: {item[0]}, Name: {item[1]}, Stock: {item[2]}</p>"

    conn.close()
    return result

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
