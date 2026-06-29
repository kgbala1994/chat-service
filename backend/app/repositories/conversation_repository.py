"""
Conversation Repository — Data access layer for conversations and participants.

Handles conversation creation, participant management, and conversation listing.
The participants table serves as the authorization boundary — presence in this
table grants read access to a conversation.
"""

import aiosqlite
from datetime import datetime, timezone
from typing import Optional


class ConversationRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def find_conversation_between(
        self, user_id_1: int, user_id_2: int
    ) -> Optional[int]:
        """
        Find an existing 1:1 conversation between two users.
        Returns conversation_id or None.
        """
        row = await (
            await self.db.execute(
                """
                SELECT p1.conversation_id
                FROM participants p1
                JOIN participants p2 ON p1.conversation_id = p2.conversation_id
                WHERE p1.user_id = ? AND p2.user_id = ?
                """,
                (user_id_1, user_id_2),
            )
        ).fetchone()
        return row[0] if row else None

    async def create_conversation(self, user_id_1: int, user_id_2: int) -> int:
        """Create a new conversation and add both users as participants."""
        cursor = await self.db.execute(
            "INSERT INTO conversations DEFAULT VALUES"
        )
        conversation_id = cursor.lastrowid

        await self.db.execute(
            "INSERT INTO participants (conversation_id, user_id) VALUES (?, ?)",
            (conversation_id, user_id_1),
        )
        await self.db.execute(
            "INSERT INTO participants (conversation_id, user_id) VALUES (?, ?)",
            (conversation_id, user_id_2),
        )
        await self.db.commit()
        return conversation_id

    async def update_conversation_timestamp(self, conversation_id: int):
        """Update the updated_at timestamp when a new message is sent.
        Uses Python datetime for sub-second precision (SQLite CURRENT_TIMESTAMP is second-level)."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await self.db.commit()

    async def is_participant(self, user_id: int, conversation_id: int) -> bool:
        """
        Check if a user is a participant in a conversation.
        This is the authorization check — the single source of truth for access control.
        """
        row = await (
            await self.db.execute(
                """
                SELECT 1 FROM participants
                WHERE conversation_id = ? AND user_id = ?
                """,
                (conversation_id, user_id),
            )
        ).fetchone()
        return row is not None

    async def conversation_exists(self, conversation_id: int) -> bool:
        """Check if a conversation exists."""
        row = await (
            await self.db.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            )
        ).fetchone()
        return row is not None

    async def get_user_conversations(self, user_id: int) -> list[dict]:
        """
        Get all conversations for a user, ordered by most recent activity.
        Includes the other participant's info for display.

        Orders by the MAX message id in each conversation (monotonically increasing,
        guaranteed unique) rather than timestamp to avoid same-second ordering issues.
        """
        rows = await (
            await self.db.execute(
                """
                SELECT
                    c.id AS conversation_id,
                    c.updated_at,
                    u.id AS other_user_id,
                    u.username AS other_username,
                    (SELECT MAX(m.id) FROM messages m WHERE m.conversation_id = c.id) AS last_msg_id
                FROM participants p
                JOIN conversations c ON p.conversation_id = c.id
                JOIN participants p2 ON c.id = p2.conversation_id AND p2.user_id != p.user_id
                JOIN users u ON p2.user_id = u.id
                WHERE p.user_id = ?
                ORDER BY last_msg_id DESC
                """,
                (user_id,),
            )
        ).fetchall()
        return [dict(row) for row in rows]
