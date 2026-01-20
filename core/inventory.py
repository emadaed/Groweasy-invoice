# core/inventory.py - FINAL PROFESSIONAL VERSION (Scalable for Millions)

from core.db import DB_ENGINE
from sqlalchemy import text
from datetime import datetime
# core/inventory.py - FINAL PROFESSIONAL & COMPLETE VERSION

from core.db import DB_ENGINE
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InventoryManager:
    """
    Complete professional inventory manager
    - Add, update, soft-delete products
    - Stock delta updates with audit
    - Low stock alerts
    - Scalable for millions of items
    """

    @staticmethod
    def add_product(user_id, product_data):
        """Add new product to inventory - YOUR CODE IS PERFECT"""
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

                logger.info(f"Product added: {product_data['name']} (ID: {result[0] if result else 'None'})")
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            return None

    @staticmethod
    def update_product(user_id, product_id, product_data):
        """Update existing product"""
        try:
            with DB_ENGINE.begin() as conn:
                # Get current stock for delta calculation if changed
                current = conn.execute(text('''
                    SELECT current_stock FROM inventory_items
                    WHERE id = :product_id AND user_id = :user_id
                '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                if not current:
                    return False

                conn.execute(text('''
                    UPDATE inventory_items
                    SET name = :name, sku = :sku, category = :category, description = :description,
                        min_stock_level = :min_stock_level, cost_price = :cost_price,
                        selling_price = :selling_price, supplier = :supplier, location = :location,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :product_id AND user_id = :user_id
                '''), {
                    "name": product_data['name'],
                    "sku": product_data.get('sku'),
                    "category": product_data.get('category'),
                    "description": product_data.get('description'),
                    "min_stock_level": product_data.get('min_stock_level', 5),
                    "cost_price": product_data.get('cost_price', 0.0),
                    "selling_price": product_data.get('selling_price', 0.0),
                    "supplier": product_data.get('supplier'),
                    "location": product_data.get('location'),
                    "product_id": product_id,
                    "user_id": user_id
                })

                # If current_stock changed, log as adjustment
                new_stock = product_data.get('current_stock')
                if new_stock is not None and new_stock != current[0]:
                    quantity_delta = new_stock - current[0]
                    conn.execute(text('''
                        INSERT INTO stock_movements
                        (user_id, product_id, movement_type, quantity, notes)
                        VALUES (:user_id, :product_id, 'adjustment', :quantity, 'Manual stock adjustment')
                    '''), {
                        "user_id": user_id,
                        "product_id": product_id,
                        "quantity": quantity_delta
                    })
                    # Update current_stock
                    conn.execute(text('''
                        UPDATE inventory_items
                        SET current_stock = :new_stock
                        WHERE id = :product_id
                    '''), {"new_stock": new_stock, "product_id": product_id})

                logger.info(f"Product updated: ID {product_id}")
                return True
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            return False

    @staticmethod
    def delete_product(user_id, product_id):
        """Soft delete product (set is_active = FALSE)"""
        try:
            with DB_ENGINE.begin() as conn:
                result = conn.execute(text('''
                    UPDATE inventory_items
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :product_id AND user_id = :user_id AND is_active = TRUE
                    RETURNING id
                '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                if result:
                    logger.info(f"Product soft-deleted: ID {product_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            return False

    @staticmethod
    def get_product_by_id(user_id, product_id):
        """Get single product by ID"""
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text('''
                    SELECT id, name, sku, category, description, current_stock,
                           min_stock_level, cost_price, selling_price, supplier, location
                    FROM inventory_items
                    WHERE id = :product_id AND user_id = :user_id AND is_active = TRUE
                '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                if result:
                    return {
                        'id': result.id,
                        'name': result.name,
                        'sku': result.sku or '',
                        'category': result.category or '',
                        'description': result.description or '',
                        'current_stock': result.current_stock,
                        'min_stock_level': result.min_stock_level or 5,
                        'cost_price': float(result.cost_price) if result.cost_price else 0.0,
                        'selling_price': float(result.selling_price) if result.selling_price else 0.0,
                        'supplier': result.supplier or '',
                        'location': result.location or ''
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting product by ID: {e}")
            return None

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
                        'id': result.id,
                        'name': result.name,
                        'selling_price': float(result.selling_price) if result.selling_price else 0.0,
                        'current_stock': result.current_stock
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting product by SKU: {e}")
            return None


    @staticmethod
    def update_stock_delta(user_id, product_id, quantity_delta, movement_type, reference_id=None, notes=None):
        """
        Update stock by delta
        + quantity_delta = increase (purchase, return)
        - quantity_delta = decrease (sale, adjustment)
        Returns True on success
        """
        try:
            with DB_ENGINE.begin() as conn:  # Atomic transaction
                # Lock the row to prevent race conditions
                result = conn.execute(text('''
                    SELECT name, current_stock, min_stock_level
                    FROM inventory_items
                    WHERE id = :product_id AND user_id = :user_id AND is_active = TRUE
                    FOR UPDATE
                '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                if not result:
                    logger.warning(f"Product {product_id} not found or inactive for user {user_id}")
                    return False

                product_name, current_stock, min_stock_level = result
                new_stock = current_stock + quantity_delta

                # Prevent negative stock
                if new_stock < 0:
                    logger.warning(f"Negative stock prevented: {product_name} would be {new_stock}")
                    return False

                # Update current stock
                conn.execute(text('''
                    UPDATE inventory_items
                    SET current_stock = :new_stock, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :product_id AND user_id = :user_id
                '''), {"new_stock": new_stock, "product_id": product_id, "user_id": user_id})

                # Record movement for audit
                conn.execute(text('''
                    INSERT INTO stock_movements
                    (user_id, product_id, movement_type, quantity, reference_id, notes, created_at)
                    VALUES (:user_id, :product_id, :movement_type, :quantity, :reference_id, :notes, CURRENT_TIMESTAMP)
                '''), {
                    "user_id": user_id,
                    "product_id": product_id,
                    "movement_type": movement_type,
                    "quantity": quantity_delta,
                    "reference_id": reference_id,
                    "notes": notes or f"{movement_type.title()} via {reference_id or 'manual'}"
                })

                logger.info(f"Stock updated: {product_name} | {current_stock} → {new_stock} ({quantity_delta:+})")
                return True

        except Exception as e:
            logger.error(f"Inventory update failed: {e}", exc_info=True)
            return False

    @staticmethod
    def get_low_stock_alerts(user_id, threshold=None):
        """Get items below min_stock_level or fallback threshold"""
        try:
            with DB_ENGINE.connect() as conn:
                query = text('''
                    SELECT name, sku, current_stock, min_stock_level
                    FROM inventory_items
                    WHERE user_id = :user_id
                      AND is_active = TRUE
                      AND current_stock <= COALESCE(min_stock_level, :threshold)
                    ORDER BY current_stock ASC
                ''')
                result = conn.execute(query, {"user_id": user_id, "threshold": threshold or 10})

                alerts = []
                for row in result:
                    alerts.append({
                        'name': row.name,
                        'sku': row.sku or 'N/A',
                        'current_stock': row.current_stock,
                        'reorder_level': row.min_stock_level or threshold or 10,
                    })
                return alerts
        except Exception as e:
            logger.error(f"Low stock alert error: {e}")
            return []

    @staticmethod
    def get_inventory_items(user_id):
        """Get all active inventory items for the user"""
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text('''
                    SELECT id, name, sku, category, current_stock, min_stock_level,
                           cost_price, selling_price, supplier, location
                    FROM inventory_items
                    WHERE user_id = :user_id AND is_active = TRUE
                    ORDER BY name
                '''), {"user_id": user_id})

                items = []
                for row in result:
                    items.append({
                        'id': row.id,
                        'name': row.name,
                        'sku': row.sku or 'N/A',
                        'category': row.category or '',
                        'current_stock': row.current_stock,
                        'min_stock_level': row.min_stock_level or 10,
                        'cost_price': float(row.cost_price) if row.cost_price else 0.0,
                        'selling_price': float(row.selling_price) if row.selling_price else 0.0,
                        'supplier': row.supplier or '',
                        'location': row.location or ''
                    })
                return items
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
            return []

