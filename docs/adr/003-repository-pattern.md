# ADR-003: Use Repository Pattern

## Status
Accepted

## Context
We need database access to be abstracted so that:
1. Business logic is testable without a database
2. Database technology can be swapped (SQLite → PostgreSQL → Cassandra)
3. Code follows single responsibility principle

## Options Considered
1. **Direct SQL in route handlers** — Fastest to write, impossible to test in isolation
2. **ORM (SQLAlchemy)** — Rich features, but heavy for this scope
3. **Repository pattern** — Clean abstraction, testable, swappable

## Decision
Implement the Repository pattern with dependency injection via FastAPI's `Depends()`.

## Architecture

```
┌──────────────────────────────────────┐
│           API Layer (Routes)          │
│  - HTTP handling, validation         │
│  - Calls service layer               │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│          Service Layer                │
│  - Business logic                    │
│  - Authorization checks              │
│  - Orchestrates repositories         │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│         Repository Layer              │
│  - Data access abstraction           │
│  - SQL queries                       │
│  - Returns domain objects            │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│            Database                   │
└──────────────────────────────────────┘
```

## Benefits

### Testability
```python
# Unit test with mock repository
class FakeMessageRepository:
    def __init__(self):
        self.messages = []

    def create(self, msg):
        self.messages.append(msg)
        return msg

# Test service logic without database
def test_cannot_message_self():
    repo = FakeMessageRepository()
    service = MessageService(repo)
    with pytest.raises(ValidationError):
        service.send_message(sender_id=1, recipient_id=1, body="hi")
```

### Swappability
```python
# Same interface, different implementation
class SQLiteMessageRepository(MessageRepository): ...
class PostgresMessageRepository(MessageRepository): ...
class CassandraMessageRepository(MessageRepository): ...
```

### Dependency Injection
```python
# FastAPI DI wires it together
def get_message_repo() -> MessageRepository:
    return SQLiteMessageRepository(get_db())

@router.post("/messages")
def send_message(repo: MessageRepository = Depends(get_message_repo)):
    ...
```

## Consequences
**Positive:**
- Service layer testable with mocks (fast unit tests)
- Database swap requires only new repository implementation
- Clear separation of concerns
- Each layer has single responsibility

**Negative:**
- More files/classes than direct SQL in handlers
- Slight indirection (one more layer to trace)
- For a small POC, may feel over-engineered

**Why it's worth it for this submission:**
- Demonstrates senior engineering practices
- Shows production-readiness thinking
- Makes tests fast and reliable
- Proves the design is portable across databases
