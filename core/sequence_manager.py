# core/sequence_manager.py
"""
Bulletproof Document Sequence Management
Uses dedicated sequence table with atomic UPSERT operations.
Zero race conditions guaranteed.

Architecture: PostgreSQL UPSERT with RETURNING clause
"""

from core.db import DB_ENGINE
from sqlalchemy import text


def init_sequence_table():
    """
    Create document sequences table.
    This table manages sequential numbering for all document types.
    """
    with DB_ENGINE.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_sequences (
                user_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                next_number INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, doc_type)
            )
        """))

        # Create index for performance
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_doc_sequences_lookup
            ON document_sequences(user_id, doc_type)
        """))

        print("✅ Document sequences table initialized")


class SequenceManager:
    """
    Manages document sequence numbers with zero race conditions.
    Uses PostgreSQL's INSERT ... ON CONFLICT ... RETURNING pattern.
    """

    @staticmethod
    def get_next_number(user_id: int, doc_type: str, prefix: str) -> str:
        """
        Get next sequential number atomically.

        This operation is GUARANTEED to be unique even under heavy concurrent load.

        Args:
            user_id: User requesting the number
            doc_type: Document type ('INV' or 'PO')
            prefix: Number prefix ('INV' or 'PO')

        Returns:
            Formatted number like 'INV-00001'

        How it works:
        1. Try to INSERT new sequence (first time for this user/type)
        2. If exists, UPDATE and increment atomically
        3. RETURNING clause gives us the new number
        4. All in one database round-trip, fully atomic
        """
        with DB_ENGINE.begin() as conn:
            # PostgreSQL UPSERT with atomic increment
            result = conn.execute(text("""
                INSERT INTO document_sequences (user_id, doc_type, next_number, last_updated)
                VALUES (:user_id, :doc_type, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, doc_type)
                DO UPDATE SET
                    next_number = document_sequences.next_number + 1,
                    last_updated = CURRENT_TIMESTAMP
                RETURNING next_number
            """), {
                "user_id": user_id,
                "doc_type": doc_type
            }).fetchone()

            number = result[0]
            formatted = f"{prefix}-{number:05d}"

            print(f"🔢 Generated {formatted} for user {user_id}")
            return formatted

    @staticmethod
    def get_current_number(user_id: int, doc_type: str) -> int:
        """
        Get current sequence number without incrementing.
        Useful for display/debugging.
        """
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text("""
                SELECT next_number FROM document_sequences
                WHERE user_id = :user_id AND doc_type = :doc_type
            """), {
                "user_id": user_id,
                "doc_type": doc_type
            }).fetchone()

            return result[0] if result else 0

    @staticmethod
    def reset_sequence(user_id: int, doc_type: str, start_number: int = 1):
        """
        Reset sequence to a specific number.
        WARNING: Use with caution - can cause duplicate numbers if set incorrectly.
        """
        with DB_ENGINE.begin() as conn:
            conn.execute(text("""
                INSERT INTO document_sequences (user_id, doc_type, next_number, last_updated)
                VALUES (:user_id, :doc_type, :start_number, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, doc_type)
                DO UPDATE SET
                    next_number = :start_number,
                    last_updated = CURRENT_TIMESTAMP
            """), {
                "user_id": user_id,
                "doc_type": doc_type,
                "start_number": start_number
            })

            print(f"⚠️  Sequence reset: user={user_id}, type={doc_type}, start={start_number}")


# Initialize on import
init_sequence_table()
