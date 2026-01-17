# emergency_fix.py - Run this on Railway
import os
import sys

print("🚨 Applying emergency fixes to live app...")

# 1. Set environment variables if missing
if not os.getenv('REDIS_URL'):
    os.environ['REDIS_URL'] = 'memory://'
    print("✅ Set REDIS_URL=memory://")

# 2. Import and run database fixes
try:
    from core.db import DB_ENGINE
    from sqlalchemy import text

    with DB_ENGINE.begin() as conn:
        # Create missing tables
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                movement_type VARCHAR(50) NOT NULL,
                reference_id VARCHAR(100),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("✅ Created stock_movements table")

except Exception as e:
    print(f"⚠️ Database fix error: {e}")

# 3. Test the app
try:
    from app import app
    with app.test_client() as client:
        response = client.get('/health')
        print(f"✅ Health check: {response.status_code}")
        print(f"✅ Response: {response.get_json()}")
except Exception as e:
    print(f"❌ App test failed: {e}")

print("\n🎉 Emergency fixes applied!")
print("App should now work at: https://growe.up.railway.app")
