"""
Database connection and initialization module.

Uses aiosqlite for async SQLite access. In production, this would be
replaced with asyncpg (PostgreSQL) or a Cassandra driver, with connection
pooling managed by the framework.
"""

import aiosqlite
import os
from pathlib import Path

DATABASE_PATH = os.environ.get("DATABASE_PATH", "chat.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS participants (
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_participants_user ON participants(user_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    client_message_id TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id DESC);
"""

SEED_SQL = """
INSERT OR IGNORE INTO users (id, username) VALUES (1, 'alice');
INSERT OR IGNORE INTO users (id, username) VALUES (2, 'bob');
INSERT OR IGNORE INTO users (id, username) VALUES (3, 'charlie');
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Called per-request via FastAPI Depends."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db(db_path: str = None):
    """Initialize database schema and seed data."""
    path = db_path or DATABASE_PATH
    db = await aiosqlite.connect(path)
    await db.executescript(SCHEMA_SQL)
    await db.executescript(SEED_SQL)
    await db.commit()
    await db.close()
