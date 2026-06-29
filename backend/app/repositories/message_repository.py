"""
Message Repository — Data access layer for messages.

Encapsulates all SQL queries related to messages. In production, this class
would be swapped for a PostgreSQL or Cassandra implementation while maintaining
the same interface.

Design note: Returns raw dicts (from Row objects) rather than ORM models.
This keeps the repository thin and avoids coupling to an ORM.
"""

import aiosqlite
from typing import Optional


class MessageRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create_message(
        self,
        conversation_id: int,
        sender_id: int,
        body: str,
        client_message_id: Optional[str] = None,
    ) -> dict:
        """Insert a new message and return it."""
        cursor = await self.db.execute(
            """
            INSERT INTO messages (conversation_id, sender_id, body, client_message_id)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, sender_id, body, client_message_id),
        )
        await self.db.commit()

        row = await (
            await self.db.execute(
                "SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)
            )
        ).fetchone()
        return dict(row)

    async def get_by_client_message_id(self, client_message_id: str) -> Optional[dict]:
        """Find a message by its idempotency key."""
        row = await (
            await self.db.execute(
                "SELECT * FROM messages WHERE client_message_id = ?",
                (client_message_id,),
            )
        ).fetchone()
        return dict(row) if row else None

    async def get_messages(
        self,
        conversation_id: int,
        before: Optional[int] = None,
        limit: int = 20,
    ) -> tuple[list[dict], bool]:
        """
        Fetch messages for a conversation using cursor-based pagination.

        Returns (messages, has_more).
        Fetches limit+1 rows to determine if more pages exist.
        """
        fetch_limit = limit + 1

        if before:
            rows = await (
                await self.db.execute(
                    """
                    SELECT * FROM messages
                    WHERE conversation_id = ? AND id < ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (conversation_id, before, fetch_limit),
                )
            ).fetchall()
        else:
            rows = await (
                await self.db.execute(
                    """
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (conversation_id, fetch_limit),
                )
            ).fetchall()

        messages = [dict(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        return messages, has_more

    async def get_last_message(self, conversation_id: int) -> Optional[dict]:
        """Get the most recent message in a conversation."""
        row = await (
            await self.db.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (conversation_id,),
            )
        ).fetchone()
        return dict(row) if row else None
