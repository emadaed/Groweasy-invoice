# core/session_manager.py - Simplified Version (No External Dependencies)
import sqlite3
import secrets
from datetime import datetime, timedelta

class SessionManager:

    @staticmethod
    def create_session(user_id, request):
        """Create new session with basic device info"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        # Ensure table exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                device_name TEXT,
                device_type TEXT,
                ip_address TEXT,
                user_agent TEXT,
                location TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        session_token = secrets.token_urlsafe(32)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        ip_address = request.remote_addr

        # Simple device detection
        device_type = 'mobile' if 'Mobile' in user_agent else 'desktop'
        device_name = user_agent[:50] if user_agent else 'Unknown Device'
        location = 'Local' if ip_address.startswith('127.') or ip_address.startswith('192.168.') else ip_address

        c.execute('''
            INSERT INTO user_sessions
            (user_id, session_token, device_name, device_type, ip_address, user_agent, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, session_token, device_name, device_type, ip_address, user_agent, location))

        conn.commit()
        conn.close()

        return session_token

    @staticmethod
    def validate_session(session_token):
        """Validate session and return user_id"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT user_id, last_active FROM user_sessions
            WHERE session_token = ? AND is_active = TRUE
        ''', (session_token,))

        result = c.fetchone()

        if result:
            user_id, last_active = result

            # Check if session expired (24 hours)
            try:
                last_active_dt = datetime.strptime(last_active, '%Y-%m-%d %H:%M:%S')
                if datetime.now() - last_active_dt > timedelta(hours=24):
                    SessionManager.revoke_session(session_token)
                    conn.close()
                    return None
            except:
                pass

            # Update last active
            c.execute('''
                UPDATE user_sessions
                SET last_active = CURRENT_TIMESTAMP
                WHERE session_token = ?
            ''', (session_token,))

            conn.commit()
            conn.close()
            return user_id

        conn.close()
        return None

    @staticmethod
    def revoke_session(session_token):
        """Revoke a specific session"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            UPDATE user_sessions
            SET is_active = FALSE
            WHERE session_token = ?
        ''', (session_token,))

        conn.commit()
        conn.close()

    @staticmethod
    def revoke_all_sessions(user_id, except_token=None):
        """Revoke all sessions for a user except current"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        if except_token:
            c.execute('''
                UPDATE user_sessions
                SET is_active = FALSE
                WHERE user_id = ? AND session_token != ?
            ''', (user_id, except_token))
        else:
            c.execute('''
                UPDATE user_sessions
                SET is_active = FALSE
                WHERE user_id = ?
            ''', (user_id,))

        conn.commit()
        conn.close()

    @staticmethod
    def get_active_sessions(user_id):
        """Get all active sessions for user"""
        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        c.execute('''
            SELECT session_token, device_name, device_type, ip_address,
                   location, last_active, created_at
            FROM user_sessions
            WHERE user_id = ? AND is_active = TRUE
            ORDER BY last_active DESC
        ''', (user_id,))

        sessions = c.fetchall()
        conn.close()

        result = []
        for s in sessions:
            result.append({
                'token': s[0],
                'device_name': s[1],
                'device_type': s[2],
                'ip_address': s[3],
                'location': s[4],
                'last_active': s[5],
                'created_at': s[6]
            })

        return result

    @staticmethod
    def check_location_restrictions(user_id, ip_address):
        """Check if user's location is allowed"""
        # Simplified - always return True (no restrictions by default)
        return True
