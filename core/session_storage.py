# core/session_storage.py - Store large session data in database
import json
from datetime import datetime, timedelta
from core.db import DB_ENGINE
from sqlalchemy import text

class SessionStorage:
    """Store large session data in database to prevent large cookies"""

    @staticmethod
    def store_large_data(user_id, data_type, data, expires_hours=24):
        """Store large data in database, return reference ID"""
        with DB_ENGINE.begin() as conn:
            result = conn.execute(text('''
                INSERT INTO session_storage
                (user_id, session_key, data_type, data, expires_at)
                VALUES (:user_id, :session_key, :data_type, :data,
                        CURRENT_TIMESTAMP + INTERVAL :expires_hours HOUR)
                RETURNING id
            '''), {
                "user_id": user_id,
                "session_key": f"{data_type}_{int(time.time())}",
                "data_type": data_type,
                "data": json.dumps(data),
                "expires_hours": expires_hours
            }).fetchone()

            return result[0] if result else None

    @staticmethod
    def retrieve_data(reference_id):
        """Retrieve stored data by reference ID"""
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text('''
                SELECT data FROM session_storage
                WHERE id = :ref_id
                AND expires_at > CURRENT_TIMESTAMP
            '''), {"ref_id": reference_id}).fetchone()

            if result:
                return json.loads(result[0])
        return None

    @staticmethod
    def cleanup_expired():
        """Clean up expired session data"""
        with DB_ENGINE.begin() as conn:
            conn.execute(text('''
                DELETE FROM session_storage
                WHERE expires_at < CURRENT_TIMESTAMP
            '''))
