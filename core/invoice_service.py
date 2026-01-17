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
        """Extract items from form data - FIXED VERSION"""
        items = []

        # Check if form_data is dict or werkzeug ImmutableMultiDict
        if hasattr(form_data, 'to_dict'):
            form_data = form_data.to_dict()

        # Debug: print form data keys
        print(f"DEBUG: Form keys: {list(form_data.keys())[:20]}...")

        # Method 1: Try structured form data (items[0][name])
        index = 0
        while True:
            # Try multiple key formats
            name_keys = [
                f'items[{index}][name]',
                f'{prefix}items[{index}][name]',
                f'item_{index}_name'
            ]

            name = None
            for key in name_keys:
                name = form_data.get(key)
                if name:
                    break

            if not name or name.strip() == '':
                # Check if we have any items at all
                if index == 0:
                    # Try alternative format: item_names[] array
                    item_names = form_data.get('item_names[]')
                    if isinstance(item_names, list):
                        # Handle array format
                        item_prices = form_data.get('item_prices[]', [])
                        item_qtys = form_data.get('item_qtys[]', [])

                        for i, item_name in enumerate(item_names):
                            if item_name and item_name.strip():
                                try:
                                    price = float(item_prices[i] if i < len(item_prices) else 0)
                                    qty = int(item_qtys[i] if i < len(item_qtys) else 1)
                                    items.append({
                                        'name': item_name,
                                        'price': price,
                                        'qty': qty,
                                        'total': price * qty
                                    })
                                except (ValueError, IndexError):
                                    pass
                        return items
                break

            # Get other fields
            price_key = f'items[{index}][price]'
            qty_key = f'items[{index}][qty]'

            price = 0
            qty = 1

            # Try multiple formats for price
            for key in [f'items[{index}][price]', f'{prefix}items[{index}][price]', f'item_{index}_price']:
                price_str = form_data.get(key)
                if price_str:
                    try:
                        price = float(price_str)
                        break
                    except:
                        pass

            # Try multiple formats for quantity
            for key in [f'items[{index}][qty]', f'{prefix}items[{index}][qty]', f'item_{index}_qty']:
                qty_str = form_data.get(key)
                if qty_str:
                    try:
                        qty = int(qty_str)
                        break
                    except:
                        pass

            items.append({
                'name': name.strip(),
                'price': price,
                'qty': qty,
                'total': price * qty,
                'description': form_data.get(f'items[{index}][description]', ''),
                'sku': form_data.get(f'items[{index}][sku]', ''),
                'product_id': form_data.get(f'items[{index}][product_id]')
            })

            index += 1

        # If no items found, check for single item format
        if not items:
            single_name = form_data.get('item_name')
            if single_name and single_name.strip():
                try:
                    price = float(form_data.get('item_price', 0))
                    qty = int(form_data.get('item_qty', 1))
                    items.append({
                        'name': single_name.strip(),
                        'price': price,
                        'qty': qty,
                        'total': price * qty
                    })
                except ValueError:
                    pass

        print(f"DEBUG: Extracted {len(items)} items")
        for i, item in enumerate(items):
            print(f"  Item {i}: {item['name']} - {item['qty']} x {item['price']} = {item['total']}")

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
