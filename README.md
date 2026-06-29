# Chat Service — One-to-One Messaging API

A REST API backend for one-to-one messaging between users, with cursor-based pagination, authorization enforcement, and a minimal web UI.

## UI Preview

![Chat Service UI](docs/images/ui-screenshot.png)

<!-- TODO: Add screenshot showing the chat interface with:
  - User selector dropdown (top-right)
  - Conversation list sidebar (left)
  - Message history with sent/received bubbles (center)
  - Message input area (bottom)
-->

## Quick Start

### Prerequisites
- Python 3.10+

### Install & Run

```bash
# Clone the repository
git clone <repo-url>
cd chat-service

# Install dependencies
pip install -e ".[dev]"

# Run the server
uvicorn backend.app.main:app --reload --port 8000

# Open the UI
open http://localhost:8000/
```

### Run Tests

```bash
# All tests
pytest

# With verbose output
pytest -v

# Specific test file
pytest tests/test_pagination.py -v
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (UI)                          │
│              Vanilla HTML + CSS + JS                      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP REST
┌────────────────────────▼────────────────────────────────┐
│                   API Layer (routes.py)                   │
│          Request validation, response formatting          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                Service Layer (message_service.py)         │
│        Business logic, authorization, orchestration       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Repository Layer                             │
│   message_repository.py | conversation_repository.py     │
│              Data access abstraction                      │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    SQLite Database                        │
└─────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/messages` | Send a message to another user |
| GET | `/api/v1/conversations/{id}/messages` | Fetch paginated message history |
| GET | `/api/v1/users/{id}/conversations` | List a user's conversations |
| GET | `/api/v1/users` | List all users (utility) |

### Authentication
Pass `X-User-Id: <integer>` header with every request.

### Pagination
Cursor-based using message IDs:
```
GET /api/v1/conversations/1/messages?before=42&limit=20
```

## Project Structure

```
chat-service/
├── backend/
│   └── app/
│       ├── main.py                 # FastAPI application
│       ├── database.py             # Schema, connection, seeds
│       ├── api/routes.py           # HTTP endpoints
│       ├── middleware/auth.py      # Authentication extraction
│       ├── services/               # Business logic
│       ├── repositories/           # Data access layer
│       └── schemas/                # Request/response models
├── frontend/
│   └── index.html                  # Minimal chat UI
├── tests/
│   ├── test_send_message.py        # Message sending tests
│   ├── test_pagination.py          # Cursor pagination tests
│   ├── test_authorization.py       # Access control tests
│   └── test_conversations.py       # Conversation listing tests
├── docs/
│   ├── problem-statement.md        # Requirements & assumptions
│   ├── non-functional-requirements.md
│   ├── architecture-options.md     # Architecture comparison
│   ├── technology-decisions.md     # Tech evaluation matrix
│   ├── data-model.md              # Schema design & rationale
│   ├── api-specification.md        # Full API contract
│   └── adr/                        # Architecture Decision Records
├── pyproject.toml                  # Project configuration
└── README.md
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pagination | Cursor-based (message ID) | Stable under concurrent writes; no duplicates |
| Auth | X-User-Id header | Focus on authorization logic, not auth infra |
| Database | SQLite | Zero setup for reviewers; Repository pattern enables swap |
| Architecture | Layered (Route → Service → Repository) | Testable, portable, clean separation |
| Ordering | MAX(message.id) for conversations | Monotonic, avoids timestamp precision issues |

## Test Coverage

```
23 tests covering:
├── Send message (9 tests)
│   ├── Happy path
│   ├── Conversation auto-creation
│   ├── Bidirectional same conversation
│   ├── Idempotency (client_message_id)
│   ├── Self-messaging rejection
│   ├── Nonexistent recipient
│   ├── Empty body validation
│   └── Auth header validation (2)
├── Pagination (5 tests)
│   ├── Correct ordering (newest first)
│   ├── Cursor pagination pages
│   ├── STABILITY under concurrent writes ★
│   ├── Empty result handling
│   └── Limit clamping
├── Authorization (6 tests)
│   ├── 403 on unauthorized read ★
│   ├── Participant access granted
│   ├── Cannot list others' conversations
│   ├── Own conversations accessible
│   ├── 404 on nonexistent conversation
│   └── Only own conversations visible
└── Conversations (3 tests)
    ├── Ordered by recent activity
    ├── Last message preview
    └── Empty list handling
```

## Documentation

See `/docs` for complete design documentation:
- **Problem Statement**: Requirements, assumptions, scope
- **NFRs**: Performance targets driving architecture
- **Architecture Options**: Three approaches compared
- **Technology Decisions**: Evaluation matrix for every choice
- **Data Model**: Schema design with production evolution
- **API Specification**: Full contract with error codes
- **ADRs**: Individual decision records with trade-off analysis

## What's Missing (Would Add With More Time)

- [ ] WebSocket for real-time message delivery
- [ ] Read receipts and typing indicators
- [ ] Message editing and soft deletion
- [ ] Rate limiting (Redis-based sliding window)
- [ ] Docker compose for one-command startup
- [ ] Database migrations (Alembic)
- [ ] Structured logging and request tracing
- [ ] Load testing results (k6/Locust)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] E2E tests with the UI
