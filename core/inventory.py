# core/inventory.py (FIXED VERSION)
from core.db import DB_ENGINE
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InventoryManager:

    @staticmethod
    def add_product(user_id, product_data):
        """Add new product to inventory"""
        try:
            with DB_ENGINE.begin() as conn:
                result = conn.execute(text('''
                    INSERT INTO inventory_items
                    (user_id, name, sku, category, description, current_stock,
                     min_stock_level, cost_price, selling_price, supplier, location)
                    VALUES (:user_id, :name, :sku, :category, :description, :current_stock,
                            :min_stock_level, :cost_price, :selling_price, :supplier, :location)
                    RETURNING id
                '''), {
                    "user_id": user_id,
                    "name": product_data['name'],
                    "sku": product_data.get('sku'),
                    "category": product_data.get('category'),
                    "description": product_data.get('description'),
                    "current_stock": product_data.get('current_stock', 0),
                    "min_stock_level": product_data.get('min_stock_level', 5),
                    "cost_price": product_data.get('cost_price', 0.0),
                    "selling_price": product_data.get('selling_price', 0.0),
                    "supplier": product_data.get('supplier'),
                    "location": product_data.get('location')
                }).fetchone()

                # Create initial stock movement
                if result and product_data.get('current_stock', 0) > 0:
                    product_id = result[0]
                    conn.execute(text('''
                        INSERT INTO stock_movements
                        (user_id, product_id, movement_type, quantity, notes)
                        VALUES (:user_id, :product_id, 'initial', :quantity, 'Initial stock')
                    '''), {
                        "user_id": user_id,
                        "product_id": product_id,
                        "quantity": product_data.get('current_stock', 0)
                    })

                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            return None

    @staticmethod
    def update_stock_for_document(user_id, document_type, document_number, items):
        """
        Update stock based on document (invoice or purchase order)
        Returns: (success, message)
        """
        try:
            if not items:
                return True, "No items to process"

            for item in items:
                product_id = item.get('product_id')
                if not product_id:
                    continue  # Skip items without product_id

                product_name = item.get('name', 'Unknown')
                quantity = int(item.get('qty', 1))

                # Get current stock
                with DB_ENGINE.connect() as conn:
                    result = conn.execute(text('''
                        SELECT current_stock, name FROM inventory_items
                        WHERE id = :product_id AND user_id = :user_id AND is_active = TRUE
                    '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                    if not result:
                        logger.warning(f"Product not found: {product_id}")
                        continue

                    current_stock = result[0]

                    # Determine stock change based on document type
                    if document_type == 'purchase_order':
                        new_stock = current_stock + quantity
                        movement_type = 'purchase'
                        notes = f"Purchased {quantity} units via PO: {document_number}"
                    elif document_type == 'invoice':
                        # Check stock availability for invoices
                        if current_stock < quantity:
                            return False, f"Insufficient stock for '{result[1]}'. Available: {current_stock}, Requested: {quantity}"
                        new_stock = current_stock - quantity
                        movement_type = 'sale'
                        notes = f"Sold {quantity} units via Invoice: {document_number}"
                    else:
                        continue

                    # Update stock
                    with DB_ENGINE.begin() as conn:
                        # Update inventory
                        conn.execute(text('''
                            UPDATE inventory_items
                            SET current_stock = :new_stock, updated_at = CURRENT_TIMESTAMP
                            WHERE id = :product_id AND user_id = :user_id
                        '''), {
                            "new_stock": new_stock,
                            "product_id": product_id,
                            "user_id": user_id
                        })

                        # Log movement
                        conn.execute(text('''
                            INSERT INTO stock_movements
                            (user_id, product_id, movement_type, quantity, reference_id, notes)
                            VALUES (:user_id, :product_id, :movement_type, :quantity, :reference_id, :notes)
                        '''), {
                            "user_id": user_id,
                            "product_id": product_id,
                            "movement_type": movement_type,
                            "quantity": quantity if movement_type == 'purchase' else -quantity,
                            "reference_id": document_number,
                            "notes": notes
                        })

                        logger.info(f"Stock updated for {product_name}: {current_stock} -> {new_stock}")

            return True, "Stock updated successfully"

        except Exception as e:
            logger.error(f"Stock update error: {e}")
            return False, f"Stock update failed: {str(e)}"

    @staticmethod
    def validate_stock_for_items(user_id, items, document_type='invoice'):
        """
        Validate stock availability before processing document
        """
        if document_type == 'purchase_order':
            return True, ""  # No validation needed for purchases

        try:
            with DB_ENGINE.connect() as conn:
                for item in items:
                    product_id = item.get('product_id')
                    if not product_id:
                        continue

                    quantity = int(item.get('qty', 1))

                    result = conn.execute(text('''
                        SELECT name, current_stock FROM inventory_items
                        WHERE id = :product_id AND user_id = :user_id AND is_active = TRUE
                    '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                    if not result:
                        return False, f"Product ID {product_id} not found in inventory"

                    product_name, current_stock = result
                    if current_stock < quantity:
                        return False, f"Insufficient stock for '{product_name}'. Available: {current_stock}, Required: {quantity}"

            return True, ""
        except Exception as e:
            logger.error(f"Stock validation error: {e}")
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def get_product_by_sku(user_id, sku):
        """Get product by SKU"""
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text('''
                    SELECT id, name, selling_price, current_stock
                    FROM inventory_items
                    WHERE user_id = :user_id AND sku = :sku AND is_active = TRUE
                '''), {"user_id": user_id, "sku": sku}).fetchone()

                if result:
                    return {
                        'id': result[0],
                        'name': result[1],
                        'selling_price': float(result[2]) if result[2] else 0.0,
                        'current_stock': result[3]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting product by SKU: {e}")
            return None

    # Keep existing methods but ensure they work properly
    @staticmethod
    def update_stock(user_id, product_id, new_quantity, movement_type='adjustment', reference_id=None, notes=None):
        """Update stock with detailed logging"""
        try:
            with DB_ENGINE.begin() as conn:
                # Get current stock
                result = conn.execute(text('''
                    SELECT name, current_stock FROM inventory_items
                    WHERE id = :product_id AND user_id = :user_id
                '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                if not result:
                    return False

                product_name, current_stock = result
                quantity_change = new_quantity - current_stock

                # Update inventory
                conn.execute(text('''
                    UPDATE inventory_items
                    SET current_stock = :new_quantity, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :product_id AND user_id = :user_id
                '''), {"new_quantity": new_quantity, "product_id": product_id, "user_id": user_id})

                # Log movement
                conn.execute(text('''
                    INSERT INTO stock_movements
                    (user_id, product_id, movement_type, quantity, reference_id, notes)
                    VALUES (:user_id, :product_id, :movement_type, :quantity, :reference_id, :notes)
                '''), {
                    "user_id": user_id,
                    "product_id": product_id,
                    "movement_type": movement_type,
                    "quantity": quantity_change,
                    "reference_id": reference_id,
                    "notes": notes
                })

                return True

        except Exception as e:
            logger.error(f"Stock update error: {e}")
            return False

    @staticmethod
    def get_inventory_items(user_id):
        """Get all active inventory items"""
        try:
            with DB_ENGINE.connect() as conn:
                items = conn.execute(text('''
                    SELECT id, name, sku, current_stock, selling_price
                    FROM inventory_items
                    WHERE user_id = :user_id AND is_active = TRUE
                    ORDER BY name
                '''), {"user_id": user_id}).fetchall()

                return [{
                    'id': item[0],
                    'name': item[1],
                    'sku': item[2],
                    'current_stock': item[3],
                    'selling_price': float(item[4]) if item[4] else 0.0
                } for item in items]
        except Exception as e:
            logger.error(f"Error getting inventory items: {e}")
            return []
