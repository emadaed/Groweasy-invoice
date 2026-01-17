# core/session_storage.py - Store large session data in database
import time
import json
from datetime import datetime
from core.db import DB_ENGINE
from sqlalchemy import text

class SessionStorage:
    @staticmethod
    def store_large_data(user_id, data_type, data):
        """Store large data in database instead of session"""
        try:
            session_key = f"{data_type}_{int(time.time())}"

            with DB_ENGINE.begin() as conn:
                conn.execute(text("""
                    INSERT INTO session_storage
                    (user_id, session_key, data_type, data, expires_at)
                    VALUES (:user_id, :session_key, :data_type, :data,
                            NOW() + INTERVAL '24 hours')
                """), {
                    "user_id": user_id,
                    "session_key": session_key,
                    "data_type": data_type,
                    "data": json.dumps(data)
                })

            return session_key
        except Exception as e:
            print(f"Session storage error: {e}")
            # Fallback to simple key
            return f"{data_type}_{int(time.time())}"

    @staticmethod
    def get_data(user_id, session_key):
        """Retrieve stored data"""
        try:
            with DB_ENGINE.connect() as conn:
                result = conn.execute(text("""
                    SELECT data FROM session_storage
                    WHERE user_id = :user_id AND session_key = :session_key
                    AND expires_at > NOW()
                """), {
                    "user_id": user_id,
                    "session_key": session_key
                }).fetchone()

                if result:
                    return json.loads(result[0])
        except Exception as e:
            print(f"Session retrieval error: {e}")

        return None

    @staticmethod
    def clear_data(user_id, data_type):
        """Clear expired data"""
        try:
            with DB_ENGINE.begin() as conn:
                conn.execute(text("""
                    DELETE FROM session_storage
                    WHERE user_id = :user_id AND data_type = :data_type
                    OR expires_at <= NOW()
                """), {
                    "user_id": user_id,
                    "data_type": data_type
                })
        except Exception as e:
            print(f"Session clear error: {e}")

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
