# core/reports.py - Business Intelligence & Analytics
import sqlite3
from datetime import datetime, timedelta

class InventoryReports:

    @staticmethod
    def get_bcg_matrix(user_id):
        """BCG Matrix: Stars, Cash Cows, Question Marks, Dogs"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        # Get all products with sales data
        c.execute('''
            SELECT
                ii.id,
                ii.name,
                ii.current_stock,
                ii.selling_price,
                ii.cost_price,
                SUM(CASE WHEN sm.movement_type = 'sale' THEN ABS(sm.quantity) ELSE 0 END) as units_sold,
                COUNT(CASE WHEN sm.movement_type = 'sale' THEN 1 END) as sale_count
            FROM inventory_items ii
            LEFT JOIN stock_movements sm ON ii.id = sm.product_id
            WHERE ii.user_id = ? AND ii.is_active = TRUE
            GROUP BY ii.id
        ''', (user_id,))

        products = c.fetchall()
        conn.close()

        if not products:
            return {'stars': [], 'cash_cows': [], 'question_marks': [], 'dogs': []}

        # Calculate metrics
        results = []
        for p in products:
            product_id, name, stock, price, cost, units_sold, sale_count = p

            # Calculate profit margin
            if price and cost:
                profit_margin = ((price - cost) / price) * 100 if price > 0 else 0
            else:
                profit_margin = 0

            # Calculate market share (relative to total sales)
            market_share = units_sold or 0

            results.append({
                'id': product_id,
                'name': name,
                'units_sold': units_sold or 0,
                'profit_margin': profit_margin,
                'stock': stock,
                'price': float(price) if price else 0,
                'sale_count': sale_count
            })

        # Calculate medians for classification
        if results:
            sorted_by_sales = sorted(results, key=lambda x: x['units_sold'])
            sorted_by_margin = sorted(results, key=lambda x: x['profit_margin'])

            median_sales = sorted_by_sales[len(sorted_by_sales)//2]['units_sold']
            median_margin = sorted_by_margin[len(sorted_by_margin)//2]['profit_margin']
        else:
            median_sales = 0
            median_margin = 0

        # Classify products
        stars = []
        cash_cows = []
        question_marks = []
        dogs = []

        for product in results:
            if product['units_sold'] >= median_sales and product['profit_margin'] >= median_margin:
                stars.append(product)  # High sales, high margin
            elif product['units_sold'] >= median_sales and product['profit_margin'] < median_margin:
                cash_cows.append(product)  # High sales, lower margin (but volume)
            elif product['units_sold'] < median_sales and product['profit_margin'] >= median_margin:
                question_marks.append(product)  # Low sales, high margin (potential)
            else:
                dogs.append(product)  # Low sales, low margin

        return {
            'stars': sorted(stars, key=lambda x: x['units_sold'], reverse=True),
            'cash_cows': sorted(cash_cows, key=lambda x: x['units_sold'], reverse=True),
            'question_marks': sorted(question_marks, key=lambda x: x['profit_margin'], reverse=True),
            'dogs': sorted(dogs, key=lambda x: x['units_sold'])
        }

    @staticmethod
    def get_stock_turnover(user_id, days=30):
        """Calculate stock turnover ratio"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        date_threshold = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT
                ii.id,
                ii.name,
                ii.current_stock,
                ii.cost_price,
                ii.selling_price,
                SUM(CASE WHEN sm.movement_type = 'sale' AND sm.created_at >= ?
                    THEN ABS(sm.quantity) ELSE 0 END) as units_sold_period,
                AVG(ii.current_stock) as avg_stock
            FROM inventory_items ii
            LEFT JOIN stock_movements sm ON ii.id = sm.product_id
            WHERE ii.user_id = ? AND ii.is_active = TRUE
            GROUP BY ii.id
            HAVING units_sold_period > 0
        ''', (date_threshold, user_id))

        results = c.fetchall()
        conn.close()

        turnover_data = []
        for row in results:
            product_id, name, current_stock, cost, price, sold, avg_stock = row

            # Turnover ratio = Units Sold / Average Stock
            turnover_ratio = (sold / avg_stock) if avg_stock > 0 else 0

            # Days to sell current stock
            if sold > 0:
                daily_sales = sold / days
                days_to_sell = current_stock / daily_sales if daily_sales > 0 else 999
            else:
                days_to_sell = 999

            turnover_data.append({
                'id': product_id,
                'name': name,
                'current_stock': current_stock,
                'units_sold': sold,
                'turnover_ratio': round(turnover_ratio, 2),
                'days_to_sell': round(days_to_sell, 1),
                'status': 'Fast' if turnover_ratio > 2 else 'Moderate' if turnover_ratio > 1 else 'Slow'
            })

        return sorted(turnover_data, key=lambda x: x['turnover_ratio'], reverse=True)

    @staticmethod
    def get_profitability_analysis(user_id):
        """Analyze product profitability"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT
                ii.id,
                ii.name,
                ii.cost_price,
                ii.selling_price,
                SUM(CASE WHEN sm.movement_type = 'sale' THEN ABS(sm.quantity) ELSE 0 END) as total_sold
            FROM inventory_items ii
            LEFT JOIN stock_movements sm ON ii.id = sm.product_id
            WHERE ii.user_id = ? AND ii.is_active = TRUE
            GROUP BY ii.id
        ''', (user_id,))

        results = c.fetchall()
        conn.close()

        profitability = []
        for row in results:
            product_id, name, cost, price, sold = row

            if cost and price and sold:
                profit_per_unit = price - cost
                total_profit = profit_per_unit * sold
                profit_margin = ((price - cost) / price) * 100 if price > 0 else 0

                profitability.append({
                    'id': product_id,
                    'name': name,
                    'cost_price': float(cost),
                    'selling_price': float(price),
                    'profit_per_unit': float(profit_per_unit),
                    'units_sold': sold,
                    'total_profit': float(total_profit),
                    'profit_margin': round(profit_margin, 2)
                })

        return sorted(profitability, key=lambda x: x['total_profit'], reverse=True)

    @staticmethod
    def get_slow_movers(user_id, days_threshold=90):
        """Identify slow-moving inventory"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        date_threshold = (datetime.now() - timedelta(days=days_threshold)).strftime('%Y-%m-%d')

        c.execute('''
            SELECT
                ii.id,
                ii.name,
                ii.current_stock,
                ii.cost_price,
                MAX(sm.created_at) as last_sale_date,
                SUM(CASE WHEN sm.movement_type = 'sale' AND sm.created_at >= ?
                    THEN ABS(sm.quantity) ELSE 0 END) as recent_sales
            FROM inventory_items ii
            LEFT JOIN stock_movements sm ON ii.id = sm.product_id AND sm.movement_type = 'sale'
            WHERE ii.user_id = ? AND ii.is_active = TRUE AND ii.current_stock > 0
            GROUP BY ii.id
            HAVING recent_sales = 0 OR recent_sales IS NULL
        ''', (date_threshold, user_id))

        results = c.fetchall()
        conn.close()

        slow_movers = []
        for row in results:
            product_id, name, stock, cost, last_sale, recent_sales = row

            if last_sale:
                days_since_sale = (datetime.now() - datetime.strptime(last_sale[:10], '%Y-%m-%d')).days
            else:
                days_since_sale = 999

            tied_capital = (stock * cost) if cost else 0

            slow_movers.append({
                'id': product_id,
                'name': name,
                'stock': stock,
                'days_since_sale': days_since_sale,
                'tied_capital': float(tied_capital),
                'recommendation': 'Discount' if days_since_sale > 180 else 'Monitor'
            })

        return sorted(slow_movers, key=lambda x: x['days_since_sale'], reverse=True)
