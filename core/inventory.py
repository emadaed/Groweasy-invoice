# core/inventory.py - ENHANCED INVENTORY MANAGER
import sqlite3
from datetime import datetime

class InventoryManager:

    @staticmethod
    def add_product(user_id, product_data):
        """Add new product to inventory"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        try:
            c.execute('''
                INSERT INTO inventory_items
                (user_id, name, sku, category, description, current_stock,
                 min_stock_level, cost_price, selling_price, supplier, location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, product_data['name'], product_data.get('sku'),
                product_data.get('category'), product_data.get('description'),
                product_data.get('current_stock', 0), product_data.get('min_stock_level', 5),
                product_data.get('cost_price'), product_data.get('selling_price'),
                product_data.get('supplier'), product_data.get('location')
            ))

            product_id = c.lastrowid
            conn.commit()
            return product_id

        except sqlite3.IntegrityError:
            return None  # SKU already exists
        finally:
            conn.close()

    #delete
    @staticmethod
    def delete_product(user_id, product_id, reason="Product removed"):
        """Soft delete product with audit trail"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        try:
            # Get current stock before deletion
            c.execute('SELECT name, current_stock FROM inventory_items WHERE id = ? AND user_id = ?',
                     (product_id, user_id))
            result = c.fetchone()

            if not result:
                conn.close()
                return False

            product_name, current_stock = result

            # Soft delete (mark as inactive)
            c.execute('UPDATE inventory_items SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                     (product_id,))

            # Create audit trail
            c.execute('''
                INSERT INTO stock_movements (user_id, product_id, movement_type, quantity, notes)
                VALUES (?, ?, 'removal', ?, ?)
            ''', (user_id, product_id, current_stock, f"Product removed: {reason}"))

            conn.commit()
            conn.close()

            print(f"✅ Product {product_name} deleted with audit trail")
            return True

        except Exception as e:
            print(f"❌ Delete error: {e}")
            conn.rollback()
            conn.close()
            return False

    #update stock
    @staticmethod
    def update_stock(user_id, product_id, new_quantity, movement_type='adjustment', reference_id=None, notes=None):
        """Update stock quantity - ENHANCED DEBUG VERSION"""
        print(f"🔍 STOCK_UPDATE_START: user_id={user_id}, product_id={product_id}, new_quantity={new_quantity}")

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        try:
            # Verify product exists and belongs to user
            c.execute('SELECT name, current_stock, min_stock_level FROM inventory_items WHERE id = ? AND user_id = ?',
                     (product_id, user_id))
            result = c.fetchone()

            if not result:
                print(f"❌ PRODUCT_NOT_FOUND: product_id={product_id} for user_id={user_id}")
                conn.close()
                return False

            product_name, current_stock, min_stock = result
            quantity_change = new_quantity - current_stock

            print(f"📊 STOCK_CHANGE: {product_name} from {current_stock} to {new_quantity} (change: {quantity_change})")

            # Update the stock
            c.execute('UPDATE inventory_items SET current_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_quantity, product_id))
            print("✅ STOCK_UPDATED_IN_DB")

            # Log the movement
            c.execute('''
                INSERT INTO stock_movements (user_id, product_id, movement_type, quantity, reference_id, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, product_id, movement_type, quantity_change, reference_id, notes))
            print("✅ MOVEMENT_LOGGED")

            # Update alerts - clear existing alerts first
            c.execute('DELETE FROM stock_alerts WHERE product_id = ? AND user_id = ?', (product_id, user_id))

            # Create new alerts if needed
            if new_quantity == 0:
                alert_type = 'out_of_stock'
                message = f"{product_name} is out of stock"
            elif new_quantity <= min_stock:
                alert_type = 'low_stock'
                message = f"{product_name} has {new_quantity} units left (min: {min_stock})"
            else:
                alert_type = None

            if alert_type:
                c.execute('''
                    INSERT INTO stock_alerts (user_id, product_id, alert_type, message)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, product_id, alert_type, message))
                print(f"✅ ALERT_CREATED: {alert_type}")

            conn.commit()
            conn.close()
            print("🎯 STOCK_UPDATE_SUCCESSFUL")
            return True

        except Exception as e:
            print(f"💥 STOCK_UPDATE_ERROR: {str(e)}")
            import traceback
            print(f"🔍 STACK_TRACE: {traceback.format_exc()}")
            conn.rollback()
            conn.close()
            return False

    @staticmethod
    def get_low_stock_alerts(user_id):
        """Get active low stock alerts"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT sa.id, ii.name, ii.current_stock, ii.min_stock_level, sa.message, sa.created_at
            FROM stock_alerts sa
            JOIN inventory_items ii ON sa.product_id = ii.id
            WHERE sa.user_id = ? AND sa.is_resolved = FALSE
            ORDER BY sa.created_at DESC
        ''', (user_id,))

        alerts = c.fetchall()
        conn.close()

        return [{
            'id': alert[0],
            'product_name': alert[1],
            'current_stock': alert[2],
            'min_stock': alert[3],
            'message': alert[4],
            'created_at': alert[5]
        } for alert in alerts]

    @staticmethod
    def get_inventory_report(user_id):
        """Generate inventory report for CSV export"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT name, sku, category, current_stock, min_stock_level,
                   cost_price, selling_price, supplier, location
            FROM inventory_items
            WHERE user_id = ? AND is_active = TRUE
            ORDER BY category, name
        ''', (user_id,))

        inventory = c.fetchall()
        conn.close()

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

    # 🆕 NEW SMART INVENTORY METHODS
    @staticmethod
    def validate_stock_for_invoice(user_id, invoice_items):
        """Validate stock for multiple invoice items"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        validation_results = []

        for item in invoice_items:
            if item.get('product_id'):
                product_id = item['product_id']
                requested_qty = int(item.get('qty', 1))

                c.execute('SELECT name, current_stock FROM inventory_items WHERE id = ? AND user_id = ?',
                         (product_id, user_id))
                result = c.fetchone()

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

        conn.close()
        return validation_results

    @staticmethod
    def get_inventory_summary(user_id):
        """Get accurate inventory summary for dashboard"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        # Total products
        c.execute('SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND is_active = TRUE', (user_id,))
        total_products = c.fetchone()[0]

        # In stock (above zero)
        c.execute('SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND current_stock > 0 AND is_active = TRUE', (user_id,))
        in_stock = c.fetchone()[0]

        # Low stock (above zero but <= min_stock_level)
        c.execute('''
            SELECT COUNT(*) FROM inventory_items
            WHERE user_id = ? AND current_stock > 0 AND current_stock <= min_stock_level AND is_active = TRUE
        ''', (user_id,))
        low_stock = c.fetchone()[0]

        # Out of stock (zero stock)
        c.execute('SELECT COUNT(*) FROM inventory_items WHERE user_id = ? AND current_stock = 0 AND is_active = TRUE', (user_id,))
        out_of_stock = c.fetchone()[0]

        conn.close()

        # 🛡️ VALIDATION: Ensure math is correct
        calculated_total = in_stock + low_stock + out_of_stock
        if calculated_total != total_products:
            print(f"⚠️ Inventory math mismatch: {calculated_total} vs {total_products}")
            # Auto-correct by using calculated total
            total_products = calculated_total

        return {
            'total_products': total_products,
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock
        }

    @staticmethod
    def get_product_details(product_id, user_id):
        """Get detailed product information"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT id, name, sku, current_stock, selling_price, min_stock_level
            FROM inventory_items
            WHERE id = ? AND user_id = ? AND is_active = TRUE
        ''', (product_id, user_id))

        result = c.fetchone()
        conn.close()

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
