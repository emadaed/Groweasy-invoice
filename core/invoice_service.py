# core/invoice_service.py - SAP-style service layer
import time
import json
from datetime import datetime
from sqlalchemy import text
from core.db import DB_ENGINE
from core.number_generator import NumberGenerator
from core.auth import save_user_invoice
from core.inventory import InventoryManager

class InvoiceService:
    """SAP-style service layer for invoice operations"""

    def __init__(self, user_id):
        self.user_id = user_id
        self.errors = []
        self.warnings = []

    def validate_invoice_data(self, form_data):
        """Validate invoice data before processing"""
        required_fields = ['client_name', 'invoice_date']
        for field in required_fields:
            if not form_data.get(field):
                self.errors.append(f"Missing required field: {field}")

        # Validate items
        items = self._extract_items(form_data)
        if not items:
            self.errors.append("At least one item is required")

        return len(self.errors) == 0, items

    def create_invoice(self, form_data):
        """Create a new invoice"""
        is_valid, items = self.validate_invoice_data(form_data)
        if not is_valid:
            return None, self.errors

        try:
            # Generate invoice number
            invoice_number = NumberGenerator.generate_invoice_number(self.user_id)

            # Calculate totals
            subtotal = sum(item['total'] for item in items)
            tax_rate = float(form_data.get('tax_rate', 17))
            tax_amount = subtotal * (tax_rate / 100)
            grand_total = subtotal + tax_amount

            # Build invoice data
            invoice_data = {
                'invoice_number': invoice_number,
                'invoice_date': form_data.get('invoice_date'),
                'client_name': form_data.get('client_name'),
                'client_address': form_data.get('client_address', ''),
                'client_phone': form_data.get('client_phone', ''),
                'client_email': form_data.get('client_email', ''),
                'notes': form_data.get('notes', ''),
                'items': items,
                'subtotal': subtotal,
                'tax_rate': tax_rate,
                'tax_amount': tax_amount,
                'grand_total': grand_total,
                'currency': form_data.get('currency', 'PKR'),
                'status': 'pending'
            }

            # Save to database
            save_user_invoice(self.user_id, invoice_data)

            # Update stock
            self._update_stock(items, 'sale', invoice_number)

            return invoice_data, None

        except Exception as e:
            self.errors.append(f"Error creating invoice: {str(e)}")
            return None, self.errors

    def create_purchase_order(self, form_data):
        """Create a purchase order"""
        try:
            # Generate PO number
            po_number = NumberGenerator.generate_po_number(self.user_id)

            # Extract items
            items = self._extract_items(form_data, prefix='po_')
            if not items:
                self.errors.append("At least one item is required for PO")
                return None, self.errors

            # Calculate totals
            subtotal = sum(item['total'] for item in items)
            tax_rate = float(form_data.get('tax_rate', 17))
            tax_amount = subtotal * (tax_rate / 100)
            shipping_cost = float(form_data.get('shipping_cost', 0))
            grand_total = subtotal + tax_amount + shipping_cost

            # Build PO data
            po_data = {
                'po_number': po_number,
                'document_type': 'purchase_order',
                'supplier_name': form_data.get('supplier_name'),
                'supplier_address': form_data.get('supplier_address', ''),
                'supplier_phone': form_data.get('supplier_phone', ''),
                'supplier_email': form_data.get('supplier_email', ''),
                'po_date': form_data.get('po_date'),
                'delivery_date': form_data.get('delivery_date'),
                'items': items,
                'subtotal': subtotal,
                'tax_rate': tax_rate,
                'tax_amount': tax_amount,
                'shipping_cost': shipping_cost,
                'grand_total': grand_total,
                'status': form_data.get('status', 'draft'),
                'notes': form_data.get('notes', '')
            }

            # Save to database
            from core.purchases import save_purchase_order
            save_purchase_order(self.user_id, po_data)

            # Update stock if PO is approved
            if po_data['status'] in ['approved', 'ordered']:
                self._update_stock(items, 'purchase', po_number)

            return po_data, None

        except Exception as e:
            self.errors.append(f"Error creating purchase order: {str(e)}")
            return None, self.errors

    def _extract_items(self, form_data, prefix=''):
        """Extract items from form data - PERMANENT FIX"""
        items = []

        # Convert to dict if MultiDict
        if hasattr(form_data, 'to_dict'):
            form_data = form_data.to_dict()

        print(f"🔍 DEBUG: Form keys: {list(form_data.keys())}")

        # Method 1: Handle array format (item_name[], item_qty[], item_price[])
        if 'item_name[]' in form_data:
            item_names = form_data['item_name[]']
            item_qtys = form_data.get('item_qty[]', [])
            item_prices = form_data.get('item_price[]', [])

            # Ensure lists
            if not isinstance(item_names, list):
                item_names = [item_names]
            if not isinstance(item_qtys, list):
                item_qtys = [item_qtys]
            if not isinstance(item_prices, list):
                item_prices = [item_prices]

            for i in range(len(item_names)):
                if item_names[i] and str(item_names[i]).strip():
                    try:
                        name = str(item_names[i]).strip()
                        qty = int(item_qtys[i]) if i < len(item_qtys) else 1
                        price = float(item_prices[i]) if i < len(item_prices) else 0

                        items.append({
                            'name': name,
                            'qty': qty,
                            'price': price,
                            'total': price * qty
                        })
                        print(f"✅ Extracted: {name} - {qty} x {price}")
                    except (ValueError, IndexError) as e:
                        print(f"⚠️ Skipping item {i}: {e}")

        # Method 2: Handle indexed format (items[0][name])
        if not items:
            i = 0
            while True:
                name_key = f'items[{i}][name]'
                name = form_data.get(name_key)

                if not name:
                    break

                try:
                    qty = int(form_data.get(f'items[{i}][qty]', 1))
                    price = float(form_data.get(f'items[{i}][price]', 0))

                    items.append({
                        'name': str(name).strip(),
                        'qty': qty,
                        'price': price,
                        'total': price * qty
                    })
                    print(f"✅ Extracted indexed: {name}")
                except ValueError as e:
                    print(f"⚠️ Skipping indexed item {i}: {e}")

                i += 1

        print(f"📊 Total items extracted: {len(items)}")
        return items


    def _update_stock(self, items, movement_type, reference_number):
        """Update stock levels"""
        for item in items:
            if item.get('product_id'):
                try:
                    success = InventoryManager.update_stock(
                        self.user_id,
                        item['product_id'],
                        item['qty'],
                        movement_type,
                        reference_number,
                        f"{movement_type.title()} via {reference_number}"
                    )

                    if not success:
                        self.warnings.append(f"Failed to update stock for {item['name']}")
                except Exception as e:
                    self.warnings.append(f"Stock update error for {item['name']}: {str(e)}")

    def get_invoice(self, invoice_number):
        """Get invoice by number"""
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT invoice_data FROM user_invoices
                    WHERE user_id = :user_id AND invoice_number = :invoice_number
                """), {
                    "user_id": self.user_id,
                    "invoice_number": invoice_number
                }).fetchone()

                if result:
                    return json.loads(result[0])
        except Exception as e:
            self.errors.append(f"Error fetching invoice: {str(e)}")

        return None

    def get_purchase_order(self, po_number):
        """Get purchase order by number"""
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT order_data FROM purchase_orders
                    WHERE user_id = :user_id AND po_number = :po_number
                """), {
                    "user_id": self.user_id,
                    "po_number": po_number
                }).fetchone()

                if result:
                    return json.loads(result[0])
        except Exception as e:
            self.errors.append(f"Error fetching purchase order: {str(e)}")

        return None
