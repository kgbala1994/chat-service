# Design Write-Up

## 1. What I Asked the AI to Do vs. What I Decided Myself

### My Decisions (Engineering Judgment)

The entire development journey — from requirements to final implementation — was driven by my decisions. AI was a tool for execution speed, not design direction.

**Requirements & Scoping (Stage 0-1):**
- Decomposed the vague 3-line requirement into 6 testable functional requirements
- Defined explicit assumptions (1:1 only, no real-time, mocked auth) to control scope
- Set NFR targets: p99 < 100ms send latency, 99.99% availability at production scale
- Identified what to defer (group chat, E2E encryption, search) and why

**Architecture (Stage 2-3):**
- Evaluated 3 architecture options (Monolith, Microservices, Serverless) with weighted scoring
- Chose monolith for POC
- Selected Python + FastAPI (readability, auto Swagger docs, async support)
- Rejected SQLAlchemy in favor of raw SQL for POC
- Rejected React for UI — single HTML file means zero build step

**Data Model (Stage 4):**
- Designed the `participants` table as the authorization boundary (not middleware, not JSON arrays)
- Chose composite index `(conversation_id, id DESC)` specifically for cursor pagination query performance
- Made `client_message_id` nullable + unique for idempotency without forcing it on all clients

**Implementation (Stage 7):**
- Chose 3-layer architecture (Route → Service → Repository) for testability and DB portability
- Put authorization in the service layer (not routes, not middleware) because it requires business context
- Designed conversation auto-creation on first message (users think "message person", not "create conversation")
- Added conditional sample data on fresh install — UI isn't empty on first run, but sample data only loads when the messages table is empty (won't pollute existing data)
- Ensured test isolation from production — tests use per-test in-memory SQLite via dependency override, never touching the server's `chat.db`. Running `pytest` while the server is live has zero side effects on the UI.

**Bug Fix (discovered during testing):**
- Found that ordering conversations by `updated_at` fails when messages arrive in the same second
- Switched to `MAX(message.id)` — monotonic, unique, unambiguous. This was my debugging, not AI's.

### What AI Generated (With My Specification)

| I Specified | AI Produced |
|-------------|-------------|
| Table names, columns, constraints, indexes | `CREATE TABLE` SQL syntax |
| Endpoint paths, verbs, status codes, error formats | FastAPI route boilerplate |
| Field names, types, validation rules | Pydantic schema classes |
| Test scenarios (WHAT to test) | pytest test code (HOW to test it) |
| "Chat bubbles, left-right aligned, user switcher" | HTML + CSS + JS implementation |
| "Capture request/response pairs in HTML report" | pytest hook + LoggingClient wrapper |
| ADR structure and content points | Markdown formatting |


---

## 2. Where I Overrode, Corrected, or Threw Away AI Output

| What AI Produced | What I Changed To | Why |
|------------------|-------------------|-----|
| Offset-based pagination | Cursor-based (`id < ?`) | Spec requires stability under concurrent writes. Offset fails: new messages shift pages, causing duplicates/skips. Cursor guarantees `id < X` never includes newer messages. |
| `CURRENT_TIMESTAMP` for conversation ordering | `MAX(message.id)` subquery | Found in testing: two conversations updated in the same second have identical timestamps → non-deterministic ordering. Message ID is monotonic and always unique. |
| JWT auth with token validation | Simple `X-User-Id` header | Over-engineering. The assignment evaluates authorization *logic*, not auth *infrastructure*. JWT adds zero signal about my engineering judgment. |
| SQLAlchemy ORM with model classes | Raw parameterized SQL in repositories | Transparency. `SELECT * FROM messages WHERE conversation_id = ? AND id < ? ORDER BY id DESC LIMIT ?` shows exactly what happens. An ORM hides this behind magic. |
| Test fixture with `try/except Exception: pass` | Clean `yield db` without exception swallowing | FastAPI's dependency injection system requires exceptions to propagate through yield-based dependencies. Swallowing them caused `FastAPIError: Response not awaited`. |
| Separate test database file (`test.db`) | In-memory SQLite per test (`:memory:`) | Faster execution (no disk I/O), perfect isolation (no shared state), no cleanup needed between tests. |
| Complex folder structure with `models/`, `dto/`, `exceptions/` | Flat: `schemas/`, `services/`, `repositories/` | No ORM = no models layer. No custom exceptions needed when `HTTPException` suffices. Fewer files = less cognitive load for reviewer. |
| Docker Compose with PostgreSQL | `pip install -e ".[dev]" && pytest` | 10-second setup vs 2-minute setup. The Repository Pattern means my SQL is PostgreSQL-compatible anyway — Docker adds friction without proving anything new. |
| React frontend with npm build | Single HTML file (vanilla JS) | A reviewer who needs `npm install && npm run build` may not bother. A reviewer who opens `localhost:8000` sees the UI instantly. |
| Empty UI on first install | Conditional sample data (3 messages) | First-time users see a working conversation immediately. Sample data only loads when DB is empty — never overwrites real data. |
| Shared test database (tests pollute server data) | Per-test in-memory DB with dependency override | Tests and server are completely isolated. `pytest` can run while the server is live without any side effects on the UI. |


---

## 3. Biggest Trade-offs

### Trade-off 1: SQLite vs. PostgreSQL

**Chose:** SQLite
**Lost:** Concurrent writes, `LISTEN/NOTIFY` for real-time, production load testing

**Why acceptable:** The Repository Pattern is the insurance policy. My API contract, service logic, and tests are database-agnostic. Swapping to PostgreSQL means writing new repository implementations — zero changes to routes, services, or tests. I chose reviewer UX over production fidelity because:
- A reviewer who can `pytest` in 5 seconds will read my code carefully
- A reviewer who fights Docker for 5 minutes will skim

**Production path:** PostgreSQL (Phase 1) → Cassandra for messages at scale (Phase 4). Same cursor pagination works because Cassandra's `TIMEUUID` clustering key serves the same purpose as auto-increment ID.

---

### Trade-off 2: Cursor Pagination (ID) vs. Offset Pagination

**Chose:** Cursor (`WHERE id < ? ORDER BY id DESC LIMIT ?`)
**Lost:** Ability to "jump to page N" directly

**Why non-negotiable:** The requirement says "pagination must be stable as new messages arrive." This eliminates offset:

```
Offset problem:
  Page 1: messages [20, 19, 18, 17, 16] (offset=0, limit=5)
  → New message 21 arrives
  Page 2: messages [16, 15, 14, 13, 12] (offset=5, limit=5)
  → Message 16 appears TWICE (shifted by the new insert)

Cursor solution:
  Page 1: messages [20, 19, 18, 17, 16] → cursor = 16
  → New message 21 arrives
  Page 2: messages [15, 14, 13, 12, 11] (id < 16)
  → Stable. Message 21 has id > 16, so it's invisible to this cursor.
```

Proven by: `test_pagination_stability_under_new_messages`

---

### Trade-off 3: 3-Layer Architecture vs. Direct SQL in Handlers

**Chose:** Route → Service → Repository (3 layers)
**Lost:** Fewer files, less indirection, faster initial development

**Why worth it:**
1. **Authorization has a home.** Where does "is this user a participant?" live? In the service layer. Not scattered across routes. Not duplicated in middleware.
2. **Database is swappable.** Replace `MessageRepository` with `CassandraMessageRepository` — service layer doesn't know or care.
3. **Tests are meaningful.** Integration tests hit the full stack. If I ever need unit tests, I can mock repositories without mocking HTTP.

For a 3-endpoint service, this is arguably over-engineered. But it demonstrates that I structure code for change, not just for "it works today."

---

### Trade-off 4: REST Polling vs. WebSocket

**Chose:** REST only (UI polls every 3 seconds)
**Lost:** Real-time message delivery, typing indicators, presence

**Why acceptable:** WebSocket is a transport optimization, not an architectural change. The data flow is identical:
1. Message is written to database
2. Message is delivered to recipient

With REST, step 2 happens on next poll. With WebSocket, step 2 happens via push. The service layer, repository layer, authorization logic, and data model are unchanged. Adding WebSocket later is additive — it doesn't replace REST (you still need REST for message history, conversation listing, etc.).

---

## 4. What's Missing / What I'd Do With Another Day

### Must-Add for Production Readiness

| Feature | Why It Matters | Implementation Approach |
|---------|---------------|----------------------|
| **WebSocket delivery** | Users expect instant messages, not 3-second polling delay | Separate WebSocket gateway service. On message write → publish to Redis Pub/Sub → gateway pushes to connected recipient. REST API unchanged. |
| **Rate limiting** | Without it, one client can spam the database | Redis sliding window: `INCR user:{id}:minute` with 60-second TTL. Return `429 Too Many Requests` + `Retry-After` header. |
| **Database migrations** | Schema in code is fine for POC, unacceptable for production | Alembic. Version-controlled migration files. `alembic upgrade head` on deploy. |
| **Structured logging** | `print()` is useless for debugging production issues | JSON logs with `trace_id`, `user_id`, `action`, `duration_ms`. Ship to Loki/ELK. Correlate with distributed tracing. |
| **Health check endpoint** | Load balancer needs to know if instance is alive | `GET /health` → checks DB connection, returns `{"status": "healthy"}` or 503. |

### Observability (Production)

| Signal | Tool | What It Answers |
|--------|------|----------------|
| Metrics | Prometheus + Grafana | "Is the system healthy?" (latency, errors, throughput) |
| Logs | Structured JSON → Loki | "What happened on this request?" (debugging) |
| Traces | OpenTelemetry + Jaeger | "Where is the time being spent?" (optimization) |
| Alerts | PagerDuty | "Wake someone up" (p99 > 500ms, error rate > 1%) |

**SLOs I'd define:**
- Availability: 99.99% (52 min downtime/year)
- Send latency p99: < 100ms
- Read latency p99: < 200ms
- Message ordering: 100% per-conversation (guaranteed by monotonic IDs)

### Scale Architecture (10M DAU)

```
Current (POC):     FastAPI → SQLite
Phase 1:           FastAPI → PostgreSQL + Redis cache
Phase 2:           + WebSocket gateway + Redis Pub/Sub
Phase 3:           + Kafka (async writes) + Cassandra (message storage)
Phase 4:           Split into Message Service + Conversation Service
```

### What This POC Proves Despite Being "Just SQLite"

The guarantees hold regardless of database:
- **Ordering**: Cursor pagination is stable (proven by test)
- **Authorization**: Participant table enforces access (proven by test)
- **Idempotency**: Duplicate sends are safe (proven by test)
- **Portability**: Repository Pattern means the architecture scales — only the adapter changes
