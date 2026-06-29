# Data Model Design

## Entity Relationship Diagram

```
┌──────────────┐       ┌───────────────────┐       ┌──────────────────┐
│    users     │       │   participants    │       │  conversations   │
├──────────────┤       ├───────────────────┤       ├──────────────────┤
│ id (PK)      │◄──────│ user_id (FK)      │       │ id (PK)          │
│ username     │       │ conversation_id(FK)│──────▶│ created_at       │
│ created_at   │       │ joined_at         │       │ updated_at       │
└──────────────┘       └───────────────────┘       └────────┬─────────┘
                                                            │
                                                            │
                       ┌───────────────────┐                │
                       │     messages      │                │
                       ├───────────────────┤                │
                       │ id (PK)           │                │
                       │ conversation_id(FK)│────────────────┘
                       │ sender_id (FK)    │───────▶ users.id
                       │ body             │
                       │ created_at       │
                       │ client_msg_id    │ (idempotency)
                       └───────────────────┘
```

## Table Definitions

### users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Design decisions:**
- Simple auto-increment PK (UUID in production for distributed ID generation)
- Username unique constraint prevents duplicates
- No password/auth fields — authentication is out of scope

### conversations
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Design decisions:**
- Separate table (not derived from messages) because:
  - Allows empty conversations (created before first message)
  - `updated_at` enables sorting conversation list by recent activity
  - Avoids expensive `MAX(created_at)` subquery on messages table
- `updated_at` is denormalized — updated on every new message for fast listing

**Why not just derive conversations from messages?**
- Conversation list query needs to be fast (< 150ms at scale)
- Without this table, listing requires: `SELECT DISTINCT conversation_id FROM messages WHERE sender_id = ? GROUP BY conversation_id ORDER BY MAX(created_at)`
- That's a full table scan at scale. Separate table = simple index lookup.

### participants
```sql
CREATE TABLE participants (
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX idx_participants_user ON participants(user_id);
```

**Design decisions:**
- Composite primary key enforces uniqueness (user can't join same conversation twice)
- Index on `user_id` for fast "list my conversations" query
- `joined_at` supports future "show messages only after join" feature
- This is the **authorization table** — if you're not in participants, you can't read

**Why a separate table instead of storing participant IDs in conversations?**
- Normalizes the relationship (no arrays, no JSON)
- Enables efficient queries in both directions:
  - "Who is in this conversation?" → filter by conversation_id (PK prefix)
  - "What conversations am I in?" → filter by user_id (indexed)
- Scales to group chat in the future without schema change

### messages
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    client_message_id TEXT UNIQUE
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, id DESC);
```

**Design decisions:**
- Auto-increment `id` provides monotonically increasing, gap-free ordering within the database
- Composite index `(conversation_id, id DESC)` is the **critical performance index**:
  - Cursor pagination query: `WHERE conversation_id = ? AND id < ? ORDER BY id DESC LIMIT ?`
  - Index satisfies this without a table scan
- `client_message_id` (nullable, unique): Idempotency key to prevent duplicate sends on retry
- `body TEXT NOT NULL`: Enforces non-empty messages at DB level

## Cursor-Based Pagination Design

### Why cursor over offset?

| Approach | Behavior with new messages | Performance at depth |
|----------|--------------------------|---------------------|
| OFFSET | Duplicates/skips items | O(offset) scan |
| **Cursor (id-based)** | **Stable — new messages don't affect window** | **O(1) index seek** |
| Timestamp cursor | Possible duplicates (same timestamp) | O(1) but less precise |

### How it works:

```
Initial fetch:    SELECT * FROM messages WHERE conversation_id = 5
                  ORDER BY id DESC LIMIT 20

Pagination:       SELECT * FROM messages WHERE conversation_id = 5
                  AND id < 142      -- cursor = last message id from previous page
                  ORDER BY id DESC LIMIT 20
```

**Stability proof:**
- New messages get `id > 142`, so they never appear in `id < 142` result set
- Deleted messages (future) would create gaps but no duplicates
- Works identically whether DB is SQLite, PostgreSQL, or Cassandra (partition key + clustering)

## Production Schema Enhancements

```sql
-- Soft deletes
ALTER TABLE messages ADD COLUMN deleted_at TIMESTAMP NULL;

-- Message status tracking
ALTER TABLE messages ADD COLUMN status TEXT DEFAULT 'sent'
    CHECK (status IN ('sent', 'delivered', 'read'));

-- Read receipts
CREATE TABLE read_receipts (
    message_id INTEGER REFERENCES messages(id),
    user_id INTEGER REFERENCES users(id),
    read_at TIMESTAMP NOT NULL,
    PRIMARY KEY (message_id, user_id)
);

-- Unread count (denormalized for performance)
ALTER TABLE participants ADD COLUMN last_read_message_id INTEGER;

-- Message search (production: use Elasticsearch instead)
CREATE VIRTUAL TABLE messages_fts USING fts5(body, content=messages);
```

## Cassandra Schema (Production at Scale)

```cql
-- Partition by conversation_id, cluster by message time
CREATE TABLE messages (
    conversation_id UUID,
    message_id TIMEUUID,
    sender_id UUID,
    body TEXT,
    created_at TIMESTAMP,
    PRIMARY KEY (conversation_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- User's conversation list (denormalized for read performance)
CREATE TABLE user_conversations (
    user_id UUID,
    updated_at TIMESTAMP,
    conversation_id UUID,
    last_message_preview TEXT,
    other_user_id UUID,
    unread_count INT,
    PRIMARY KEY (user_id, updated_at, conversation_id)
) WITH CLUSTERING ORDER BY (updated_at DESC);
```

**Why denormalize in Cassandra?**
- Cassandra has no JOINs
- Read pattern drives table design
- One query per user to get their full conversation list
- Trade-off: Write amplification (update both tables on each message)
