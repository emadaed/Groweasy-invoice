# core/inventory.py (Postgres Ready)
from core.db import DB_ENGINE
from sqlalchemy import text
from datetime import datetime

class InventoryManager:

    @staticmethod
    def add_product(user_id, product_data):
        """Add new product to inventory"""
        with DB_ENGINE.begin() as conn:
            conn.execute(text('''
                INSERT INTO inventory_items
                (user_id, name, sku, category, description, current_stock,
                 min_stock_level, cost_price, selling_price, supplier, location)
                VALUES (:user_id, :name, :sku, :category, :description, :current_stock,
                        :min_stock_level, :cost_price, :selling_price, :supplier, :location)
            '''), {
                "user_id": user_id, "name": product_data['name'], "sku": product_data.get('sku'),
                "category": product_data.get('category'), "description": product_data.get('description'),
                "current_stock": product_data.get('current_stock', 0),
                "min_stock_level": product_data.get('min_stock_level', 5),
                "cost_price": product_data.get('cost_price'), "selling_price": product_data.get('selling_price'),
                "supplier": product_data.get('supplier'), "location": product_data.get('location')
            })

            result = conn.execute(text("SELECT lastval()")).fetchone()
            return result[0] if result else None

    @staticmethod
    def delete_product(user_id, product_id, reason="Product removed"):
        """Soft delete product with audit trail"""
        with DB_ENGINE.begin() as conn:
            result = conn.execute(text('''
                SELECT name, current_stock FROM inventory_items
                WHERE id = :product_id AND user_id = :user_id
            '''), {"product_id": product_id, "user_id": user_id}).fetchone()

            if not result:
                return False

            product_name, current_stock = result

            conn.execute(text('''
                UPDATE inventory_items SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = :product_id
            '''), {"product_id": product_id})

            conn.execute(text('''
                INSERT INTO stock_movements (user_id, product_id, movement_type, quantity, notes)
                VALUES (:user_id, :product_id, 'removal', :quantity, :notes)
            '''), {"user_id": user_id, "product_id": product_id, "quantity": current_stock, "notes": f"Product removed: {reason}"})

            print(f"✅ Product {product_name} deleted with audit trail")
            return True

    @staticmethod
    def update_stock(user_id, product_id, new_quantity, movement_type='adjustment', reference_id=None, notes=None):
        """Update stock quantity - ENHANCED DEBUG VERSION"""
        print(f"🔍 STOCK_UPDATE_START: user_id={user_id}, product_id={product_id}, new_quantity={new_quantity}")

        with DB_ENGINE.begin() as conn:
            result = conn.execute(text('''
                SELECT name, current_stock, min_stock_level
                FROM inventory_items WHERE id = :product_id AND user_id = :user_id
            '''), {"product_id": product_id, "user_id": user_id}).fetchone()

            if not result:
                print(f"❌ PRODUCT_NOT_FOUND: product_id={product_id} for user_id={user_id}")
                return False

            product_name, current_stock, min_stock = result
            quantity_change = new_quantity - current_stock

            print(f"📊 STOCK_CHANGE: {product_name} from {current_stock} to {new_quantity} (change: {quantity_change})")

            conn.execute(text('''
                UPDATE inventory_items SET current_stock = :new_quantity, updated_at = CURRENT_TIMESTAMP
                WHERE id = :product_id
            '''), {"new_quantity": new_quantity, "product_id": product_id})
            print("✅ STOCK_UPDATED_IN_DB")

            conn.execute(text('''
                INSERT INTO stock_movements (user_id, product_id, movement_type, quantity, reference_id, notes)
                VALUES (:user_id, :product_id, :movement_type, :quantity_change, :reference_id, :notes)
            '''), {
                "user_id": user_id, "product_id": product_id, "movement_type": movement_type,
                "quantity_change": quantity_change, "reference_id": reference_id, "notes": notes
            })
            print("✅ MOVEMENT_LOGGED")

            conn.execute(text("DELETE FROM stock_alerts WHERE product_id = :product_id AND user_id = :user_id"),
                        {"product_id": product_id, "user_id": user_id})

            if new_quantity == 0:
                alert_type = 'out_of_stock'
                message = f"{product_name} is out of stock"
            elif new_quantity <= min_stock:
                alert_type = 'low_stock'
                message = f"{product_name} has {new_quantity} units left (min: {min_stock})"
            else:
                alert_type = None

            if alert_type:
                conn.execute(text('''
                    INSERT INTO stock_alerts (user_id, product_id, alert_type, message)
                    VALUES (:user_id, :product_id, :alert_type, :message)
                '''), {"user_id": user_id, "product_id": product_id, "alert_type": alert_type, "message": message})
                print(f"✅ ALERT_CREATED: {alert_type}")

            print("🎯 STOCK_UPDATE_SUCCESSFUL")
            return True

    @staticmethod
    def get_low_stock_alerts(user_id):
        with DB_ENGINE.connect() as conn:
            alerts = conn.execute(text('''
                SELECT sa.id, ii.name, ii.current_stock, ii.min_stock_level, sa.message, sa.created_at
                FROM stock_alerts sa
                JOIN inventory_items ii ON sa.product_id = ii.id
                WHERE sa.user_id = :user_id AND sa.is_resolved = FALSE
                ORDER BY sa.created_at DESC
            '''), {"user_id": user_id}).fetchall()

        return [{
            'id': alert[0],
            'product_name': alert[1],
            'current_stock': alert[2],
            'min_stock': alert[3],
            'message': alert[4],
            'created_at': alert[5].strftime('%Y-%m-%d %H:%M:%S') if alert[5] else ''
        } for alert in alerts]

    @staticmethod
    def get_inventory_report(user_id):
        with DB_ENGINE.connect() as conn:
            inventory = conn.execute(text('''
                SELECT name, sku, category, current_stock, min_stock_level,
                       cost_price, selling_price, supplier, location
                FROM inventory_items
                WHERE user_id = :user_id AND is_active = TRUE
                ORDER BY category, name
            '''), {"user_id": user_id}).fetchall()

        return [{
            'name': item[0],
            'sku': item[1],
            'category': item[2],
            'current_stock': item[3],
            'min_stock': item[4],
            'cost_price': float(item[5]) if item[5] else 0,
            'selling_price': float(item[6]) if item[6] else 0,
            'supplier': item[7],
            'location': item[8]
        } for item in inventory]

    @staticmethod
    def validate_stock_for_invoice(user_id, invoice_items):
        with DB_ENGINE.connect() as conn:
            validation_results = []

            for item in invoice_items:
                if item.get('product_id'):
                    product_id = item['product_id']
                    requested_qty = int(item.get('qty', 1))

                    result = conn.execute(text('''
                        SELECT name, current_stock FROM inventory_items
                        WHERE id = :product_id AND user_id = :user_id
                    '''), {"product_id": product_id, "user_id": user_id}).fetchone()

                    if result:
                        product_name, current_stock = result
                        if current_stock < requested_qty:
                            validation_results.append({
                                'product_id': product_id,
                                'product_name': product_name,
                                'requested': requested_qty,
                                'available': current_stock,
                                'valid': False
                            })
                        else:
                            validation_results.append({
                                'product_id': product_id,
                                'product_name': product_name,
                                'requested': requested_qty,
                                'available': current_stock,
                                'valid': True
                            })

            return validation_results

    @staticmethod
    def get_inventory_summary(user_id):
        with DB_ENGINE.connect() as conn:
            total_products = conn.execute(text('''
                SELECT COUNT(*) FROM inventory_items
                WHERE user_id = :user_id AND is_active = TRUE
            '''), {"user_id": user_id}).scalar()

            in_stock = conn.execute(text('''
                SELECT COUNT(*) FROM inventory_items
                WHERE user_id = :user_id AND current_stock > 0 AND is_active = TRUE
            '''), {"user_id": user_id}).scalar()

            low_stock = conn.execute(text('''
                SELECT COUNT(*) FROM inventory_items
                WHERE user_id = :user_id AND current_stock > 0 AND current_stock <= min_stock_level AND is_active = TRUE
            '''), {"user_id": user_id}).scalar()

            out_of_stock = conn.execute(text('''
                SELECT COUNT(*) FROM inventory_items
                WHERE user_id = :user_id AND current_stock = 0 AND is_active = TRUE
            '''), {"user_id": user_id}).scalar()

        return {
            'total_products': total_products or 0,
            'in_stock': in_stock or 0,
            'low_stock': low_stock or 0,
            'out_of_stock': out_of_stock or 0
        }

    @staticmethod
    def get_product_details(product_id, user_id):
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text('''
                SELECT id, name, sku, current_stock, selling_price, min_stock_level
                FROM inventory_items
                WHERE id = :product_id AND user_id = :user_id AND is_active = TRUE
            '''), {"product_id": product_id, "user_id": user_id}).fetchone()

        if result:
            return {
                'id': result[0],
                'name': result[1],
                'sku': result[2],
                'current_stock': result[3],
                'selling_price': float(result[4]) if result[4] else 0,
                'min_stock_level': result[5]
            }
        return None

    @staticmethod
    def deduct_stock_for_invoice(user_id, items):
        with DB_ENGINE.begin() as conn:
            for item in items:
                product_id = item['product_id']
                qty = item['qty']
                conn.execute(text("""
                    UPDATE inventory_items SET current_stock = current_stock - :qty
                    WHERE id = :id AND user_id = :user_id
                """), {"qty": qty, "id": product_id, "user_id": user_id})
                # Log movement
                conn.execute(text("""
                    INSERT INTO stock_movements (user_id, product_id, movement_type, quantity, notes)
                    VALUES (:user_id, :product_id, 'sale', :qty, 'Invoice sale')
                """), {"user_id": user_id, "product_id": product_id, "qty": -qty})
