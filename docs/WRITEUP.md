# Design Write-Up

## 1. What I Asked the AI to Do vs. What I Decided Myself

### My decisions (judgment calls):
- **Data model design**: I chose to separate `conversations` and `participants` into distinct tables rather than embedding participant arrays in a conversations table. This normalized approach creates a clean authorization boundary (participants table = access control list) and avoids the limitations of array-based queries.
- **Cursor-based pagination over offset**: I specified this upfront based on the stability requirement. The AI's first suggestion included offset as a "simpler" option — I overrode this because the spec explicitly requires stable pagination under concurrent writes.
- **Repository pattern with dependency injection**: I decided on layered architecture (Route → Service → Repository) to demonstrate separation of concerns and make the database swappable. This was a deliberate choice for the audience (senior reviewers expect this).
- **Conversation ordering by MAX(message.id)**: During testing, I discovered that ordering by `updated_at` timestamp fails when messages arrive within the same second (common in tests, possible in production). I switched to using the message ID which is monotonically increasing and unambiguous.
- **Single HTML file for UI**: I rejected the AI's suggestion to use React — a reviewer shouldn't need `npm install` and a build step to see the UI work.

### What AI generated (with my guidance):
- Boilerplate: FastAPI route definitions, Pydantic schemas, SQL DDL
- Test structure: Basic test patterns (I specified WHAT to test, AI generated the code)
- Documentation formatting: Markdown structure for ADRs and docs
- CSS styling: The UI's visual appearance

## 2. Where I Overrode, Corrected, or Threw Away AI Output

| What AI Produced | What I Changed | Why |
|------------------|----------------|-----|
| Offset-based pagination initially | Replaced with cursor (id-based) | Spec requires stability under concurrent writes; offset fails this |
| `CURRENT_TIMESTAMP` for ordering | Changed to `MAX(message.id)` subquery | Found in testing that same-second timestamps break ordering |
| JWT auth implementation | Replaced with simple X-User-Id header | Over-engineering for a POC; auth infra isn't what's being evaluated |
| SQLAlchemy ORM | Replaced with raw SQL in repositories | More transparent, easier to explain, shows actual queries |
| Test fixture with bare `except` in yield | Fixed to proper `yield` without exception swallowing | FastAPI's dependency injection requires exceptions to propagate |
| Separate test database file | Changed to in-memory SQLite per test | Faster, fully isolated, no cleanup needed |
| Complex folder structure with `models/` | Flattened — schemas are sufficient | No ORM = no separate model layer needed |

## 3. Biggest Trade-offs

### Trade-off 1: SQLite vs PostgreSQL

**Chose:** SQLite
**Alternative:** PostgreSQL (with Docker Compose)

**Why:** Reviewers should be able to `pip install && pytest` in under 30 seconds. Docker adds friction. The Repository pattern means the choice is purely about deployment ergonomics — the SQL is PostgreSQL-compatible, the interface is abstract, and swapping requires only a new repository implementation.

**What I lose:** Concurrent writes, LISTEN/NOTIFY for real-time, production-grade performance testing.

### Trade-off 2: Cursor Pagination (message ID) vs Keyset (timestamp + ID)

**Chose:** Simple cursor using auto-increment `id`
**Alternative:** Composite keyset `(created_at, id)` for distributed systems

**Why:** With a single SQLite/PostgreSQL database, auto-increment IDs are globally unique and monotonically increasing — a composite key adds complexity without benefit. In Cassandra (production), you'd switch to TIMEUUID as the clustering key, which serves the same purpose.

**What I lose:** The ability to paginate by "messages since time X" (useful for sync protocols). Would add as a separate endpoint if needed.

### Trade-off 3: Layered Architecture vs Direct SQL in Handlers

**Chose:** Route → Service → Repository (3 layers)
**Alternative:** SQL directly in route handlers (fewer files, less indirection)

**Why:** The evaluation criteria mention "clean data model" and "meaningful tests." The service layer is where authorization lives — testing it without HTTP overhead proves correctness. The repository layer proves the design is database-agnostic. Two extra files per entity is a small price for testability and clarity.

**What I lose:** Simplicity of fewer files. For a 3-endpoint service, this is arguably over-engineered — but it demonstrates the patterns expected at scale.

## 4. What's Missing / What I'd Do With Another Day

### Immediate additions:
- **WebSocket endpoint** for real-time message delivery (avoid polling)
- **Docker Compose** with PostgreSQL for a more realistic setup
- **Rate limiting** middleware (60 msg/min per user)
- **Structured logging** with request IDs for debugging

### Production-readiness:
- **Read receipts** (`read_receipts` table, `PATCH /messages/:id/read`)
- **Message search** (Elasticsearch integration or FTS5 for SQLite)
- **Soft delete** with `deleted_at` field
- **Database migrations** via Alembic instead of schema in code
- **Load testing** with Locust to find actual throughput ceiling
- **Health check endpoint** (`/health`) for load balancer integration
- **OpenTelemetry tracing** for cross-service observability
- **CI pipeline** (GitHub Actions: lint → test → build → deploy)

### Architecture evolution (at 10M DAU):
- Extract into Message Service + Conversation Service
- Kafka for async message processing (decouple write from read)
- Cassandra for message storage (partition by conversation_id)
- Redis for caching conversation lists and unread counts
- WebSocket gateway as separate service (horizontal scaling)
