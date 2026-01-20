# core/invoice_service.py - FINAL FIXED VERSION

import logging
from datetime import datetime
from sqlalchemy import text
from core.db import DB_ENGINE
from core.number_generator import NumberGenerator
from core.auth import save_user_invoice
from core.inventory import InventoryManager
from core.invoice_logic import prepare_invoice_data  # ← Use the perfect logic

logger = logging.getLogger(__name__)

class InvoiceService:
    """Service layer for invoice operations"""

    def __init__(self, user_id):
        self.user_id = user_id
        self.errors = []
        self.warnings = []

    def create_invoice(self, form_data, files=None):
        """Create invoice using prepare_invoice_data - supports user logo"""
        try:
            # Use the robust prepare_invoice_data from invoice_logic.py
            invoice_data = prepare_invoice_data(form_data, files=files)

            # Generate invoice number if not present
            if 'invoice_number' not in invoice_data:
                invoice_data['invoice_number'] = NumberGenerator.generate_invoice_number(self.user_id)

            # Save to DB
            save_user_invoice(self.user_id, invoice_data)

            # Update stock for sales
            if invoice_data.get('invoice_type', 'S') != 'P':  # Not purchase
                self._update_stock(invoice_data['items'], 'sale', invoice_data['invoice_number'])

            logger.info(f"Invoice {invoice_data['invoice_number']} created for user {self.user_id}")
            return invoice_data, None

        except ValueError as e:
            self.errors.append(str(e))
            return None, self.errors
        except Exception as e:
            logger.error(f"Invoice creation failed: {e}", exc_info=True)
            self.errors.append("An unexpected error occurred")
            return None, self.errors

    def create_purchase_order(self, form_data, files=None):
        """Create purchase order"""
        try:
            # For PO, we can reuse prepare_invoice_data or customize
            po_data = prepare_invoice_data(form_data, files=files)

            # Generate PO number
            po_data['po_number'] = NumberGenerator.generate_po_number(self.user_id)
            po_data['invoice_type'] = 'P'

            # Save to purchases table (your existing function)
            from core.purchases import save_purchase_order
            save_purchase_order(self.user_id, po_data)

            logger.info(f"PO {po_data['po_number']} created for user {self.user_id}")
            return po_data, None

        except ValueError as e:
            self.errors.append(str(e))
            return None, self.errors
        except Exception as e:
            logger.error(f"PO creation failed: {e}", exc_info=True)
            self.errors.append("An unexpected error occurred")
            return None, self.errors

    def _update_stock(self, items, movement_type, reference_number):
        """Update inventory stock"""
        for item in items:
            if item.get('product_id'):
                try:
                    InventoryManager.update_stock(
                        self.user_id,
                        item['product_id'],
                        item['qty'],
                        movement_type,
                        reference_number,
                        f"{movement_type.title()} {reference_number}"
                    )
                except Exception as e:
                    self.warnings.append(f"Stock update failed for {item['name']}: {e}")

    def get_invoice(self, invoice_number):
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT invoice_data FROM user_invoices
                    WHERE user_id = :user_id AND invoice_number = :invoice_number
                """), {"user_id": self.user_id, "invoice_number": invoice_number}).fetchone()
                if result:
                    return json.loads(result[0])
        except Exception as e:
            logger.error(f"Error fetching invoice: {e}")
        return None

    def get_purchase_order(self, po_number):
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT order_data FROM purchase_orders
                    WHERE user_id = :user_id AND po_number = :po_number
                """), {"user_id": self.user_id, "po_number": po_number}).fetchone()
                if result:
                    return json.loads(result[0])
        except Exception as e:
            logger.error(f"Error fetching PO: {e}")
        return None
