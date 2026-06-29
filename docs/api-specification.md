# API Specification

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication (POC)
All requests must include:
```
X-User-Id: <integer>
```
Missing or invalid header returns `401 Unauthorized`.

## Endpoints

---

### POST /messages

Send a message to another user. Creates a conversation if one doesn't exist between the two users.

**Request:**
```json
{
    "recipient_id": 2,
    "body": "Hello, how are you?",
    "client_message_id": "uuid-optional-idempotency-key"
}
```

**Response (201 Created):**
```json
{
    "id": 47,
    "conversation_id": 12,
    "sender_id": 1,
    "recipient_id": 2,
    "body": "Hello, how are you?",
    "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | Missing body, empty body, or recipient_id equals sender_id |
| 401 | Missing X-User-Id header |
| 404 | Recipient user does not exist |
| 409 | Duplicate client_message_id (idempotent — returns original message) |

**Idempotency Behavior:**
- If `client_message_id` is provided and already exists, return the existing message with `200 OK`
- This prevents duplicate messages on client retry

---

### GET /conversations/{conversation_id}/messages

Fetch paginated message history for a conversation.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| before | integer | (none) | Return messages with id < this value (cursor) |
| limit | integer | 20 | Number of messages to return (max 100) |

**Response (200 OK):**
```json
{
    "messages": [
        {
            "id": 45,
            "conversation_id": 12,
            "sender_id": 2,
            "body": "I'm good, thanks!",
            "created_at": "2024-01-15T10:31:00Z"
        },
        {
            "id": 44,
            "conversation_id": 12,
            "sender_id": 1,
            "body": "Hello, how are you?",
            "created_at": "2024-01-15T10:30:00Z"
        }
    ],
    "pagination": {
        "has_more": true,
        "next_cursor": 44,
        "limit": 20
    }
}
```

**Ordering:** Messages returned in descending order (newest first). Client reverses for display.

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 401 | Missing X-User-Id header |
| 403 | User is not a participant in this conversation |
| 404 | Conversation does not exist |

**Pagination Contract:**
- `has_more: true` means there are older messages available
- `next_cursor` is the `id` of the last message in the current page
- To get next page: `?before={next_cursor}&limit=20`
- First request (no `before` param) returns the most recent messages

---

### GET /users/{user_id}/conversations

List all conversations for a user, ordered by most recent activity.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | integer | 20 | Number of conversations to return (max 50) |
| before | string | (none) | ISO timestamp cursor for pagination |

**Response (200 OK):**
```json
{
    "conversations": [
        {
            "id": 12,
            "other_user": {
                "id": 2,
                "username": "alice"
            },
            "last_message": {
                "id": 45,
                "body": "I'm good, thanks!",
                "sender_id": 2,
                "created_at": "2024-01-15T10:31:00Z"
            },
            "updated_at": "2024-01-15T10:31:00Z"
        }
    ],
    "pagination": {
        "has_more": false,
        "next_cursor": null,
        "limit": 20
    }
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 401 | Missing X-User-Id header |
| 403 | Requesting another user's conversation list (user_id != X-User-Id) |

**Authorization Rule:** A user can only list their own conversations (`user_id` in path must match `X-User-Id` header).

---

### GET /users

List all users (utility endpoint for the UI).

**Response (200 OK):**
```json
{
    "users": [
        {"id": 1, "username": "alice", "created_at": "2024-01-01T00:00:00Z"},
        {"id": 2, "username": "bob", "created_at": "2024-01-01T00:00:00Z"}
    ]
}
```

---

## Error Response Format

All errors follow a consistent structure:
```json
{
    "error": {
        "code": "FORBIDDEN",
        "message": "You are not a participant in this conversation"
    }
}
```

## Rate Limiting (Production)

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /messages | 60 | per minute per user |
| GET /conversations/*/messages | 120 | per minute per user |
| GET /users/*/conversations | 30 | per minute per user |

Headers returned:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705312260
```

## Versioning Strategy

- URL-based: `/api/v1/`, `/api/v2/`
- Breaking changes get new version
- Deprecation: 6 month sunset period with `Sunset` header
- Non-breaking additions (new fields) are backwards-compatible
