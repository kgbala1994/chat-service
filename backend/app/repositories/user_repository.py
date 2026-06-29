"""
User Repository — Data access layer for users.

Minimal for this POC since users are pre-seeded. In production, this would
include registration, profile updates, and presence tracking.
"""

import aiosqlite
from typing import Optional


class UserRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[dict]:
        """Find a user by ID."""
        row = await (
            await self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        ).fetchone()
        return dict(row) if row else None

    async def get_all(self) -> list[dict]:
        """Get all users. For POC UI only — would be paginated in production."""
        rows = await (
            await self.db.execute("SELECT id, username, created_at FROM users")
        ).fetchall()
        return [dict(row) for row in rows]

    async def exists(self, user_id: int) -> bool:
        """Check if a user exists."""
        row = await (
            await self.db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        ).fetchone()
        return row is not None
