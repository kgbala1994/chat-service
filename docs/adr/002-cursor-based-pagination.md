# ADR-002: Use Cursor-Based Pagination

## Status
Accepted

## Context
Message history must be paginated. New messages arrive continuously. The pagination must remain stable — no duplicates or skipped messages — even as new messages are inserted.

## Options Considered
1. **Offset-based** (`OFFSET 20 LIMIT 20`) — Simple but unstable
2. **Cursor-based (id)** (`WHERE id < cursor LIMIT 20`) — Stable, performant
3. **Timestamp-based** (`WHERE created_at < cursor`) — Possible collisions

## Decision
Cursor-based pagination using the auto-increment message `id` as cursor.

## Rationale

### Why not offset?
```
Initial state: [msg50, msg49, msg48, ..., msg31] (page 1, offset=0)
User scrolls to page 2: OFFSET 20 LIMIT 20

Meanwhile, 3 new messages arrive: msg51, msg52, msg53

Page 2 with offset: [msg30, msg29, ..., msg11]
But msg31, msg32, msg33 shifted down — user sees msg30 again (duplicate)
or skips msg31-33 entirely depending on direction.
```

### Why cursor works:
```
Page 1 returns: [..., msg31] → next_cursor = 31
Page 2 query: WHERE id < 31 ORDER BY id DESC LIMIT 20

New messages (id=51,52,53) have id > 31, so they NEVER appear in id < 31 results.
Result is always stable regardless of new inserts.
```

### Why not timestamp?
- Multiple messages can share the same timestamp (millisecond precision)
- `WHERE created_at < '2024-01-15T10:30:00.000Z'` might skip or duplicate messages with identical timestamps
- Integer ID is unique by definition — no ambiguity

## Consequences
**Positive:**
- Stable pagination under concurrent writes (proven by test)
- O(1) index seek performance (vs O(offset) for OFFSET)
- Works identically in PostgreSQL, Cassandra, DynamoDB
- Simple client implementation

**Negative:**
- Cannot jump to arbitrary page (must traverse sequentially)
- Cursor is opaque to client (integer, not semantic)
- Deleting messages creates gaps (acceptable — no duplicates)

## Implementation
```python
def get_messages(conversation_id: int, before: Optional[int], limit: int):
    if before:
        query = "SELECT * FROM messages WHERE conversation_id = ? AND id < ? ORDER BY id DESC LIMIT ?"
        params = (conversation_id, before, limit + 1)  # +1 to detect has_more
    else:
        query = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?"
        params = (conversation_id, limit + 1)

    results = db.execute(query, params)
    has_more = len(results) > limit
    messages = results[:limit]
    next_cursor = messages[-1].id if has_more else None
    return messages, has_more, next_cursor
```
