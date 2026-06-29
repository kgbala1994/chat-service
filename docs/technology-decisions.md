# Technology Decisions

## Language & Framework

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Python + FastAPI** | Async native, auto OpenAPI docs, type hints, fast dev | GIL limits CPU concurrency | **Selected** |
| Node.js + Express | Event loop, large ecosystem | Callback complexity, weak typing | Rejected |
| Go + Gin | Performance, concurrency | Verbose, slower iteration | Rejected |
| Java + Spring Boot | Enterprise patterns, mature | Heavy, slow startup | Rejected |

**Rationale:** FastAPI provides automatic OpenAPI documentation (reviewers can explore the API), built-in request validation via Pydantic, async support, and Python's readability makes code review pleasant.

## Database

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **SQLite** | Zero setup, file-based, ACID, portable | No concurrent writes, no network access | **Selected (POC)** |
| PostgreSQL | ACID, concurrent, rich features, production-ready | Requires installation/Docker | Alternative |
| Cassandra | Massive write scale, partition-friendly | Operational complexity, eventual consistency | Future (production) |
| MongoDB | Flexible schema, easy start | Ordering complexity, no true ACID | Rejected |
| DynamoDB | Managed, auto-scale | Vendor lock-in, query limitations | Rejected |

**Rationale:** SQLite eliminates setup friction for reviewers. The Repository pattern means swapping to PostgreSQL requires only a new repository implementation — zero changes to service/API layers. Schema is designed to be PostgreSQL-compatible.

## Caching (Production)

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Redis** | Sub-ms latency, pub/sub, data structures | Memory cost, another service | **Production choice** |
| Memcached | Simple, multi-threaded | No persistence, limited types | Rejected |
| Application-level | No infra | Memory leaks, no sharing | POC only (in-memory) |

**What to cache (production):**
- Recent messages per conversation (last 50)
- User's conversation list with last message preview
- Unread message counts
- User session/presence data

## Real-Time Communication (Production)

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **WebSocket** | Bi-directional, low latency, wide support | Connection management, scaling | **Production choice** |
| Server-Sent Events | Simple, HTTP-compatible | Uni-directional only | Fallback option |
| Long Polling | Works everywhere | High latency, resource waste | Legacy fallback |
| gRPC Streaming | Efficient binary protocol | Browser support limited | Internal services only |

## Message Queue (Production)

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Kafka** | Durable, replay, high throughput, ordering per partition | Complex ops, overkill for small scale | **Production choice** |
| RabbitMQ | Simple, flexible routing | No replay, ordering challenges | Rejected |
| Redis Streams | Lightweight, already in stack | Less mature, memory-bound | Secondary option |
| AWS SQS | Managed, cheap | No ordering guarantee, no replay | Rejected |

**Kafka usage pattern:**
- Topic: `messages` partitioned by `conversation_id`
- Guarantees ordering within a conversation
- Consumers: persistence service, notification service, analytics

## Testing

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **pytest** | Simple, fixtures, parametrize, rich plugins | Python-only | **Selected** |
| unittest | Built-in | Verbose, less ergonomic | Rejected |
| hypothesis | Property-based | Overkill for this scope | Future |

**Testing layers:**
- Unit: Service logic with mocked repositories
- Integration: Full API calls against test SQLite database
- E2E (future): Selenium/Playwright against running service with UI

## Frontend (Minimal UI)

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Vanilla HTML + JS** | Zero build step, no dependencies, instant load | Less maintainable at scale | **Selected (POC)** |
| React | Component model, ecosystem | Build step, node_modules, overkill | Rejected for POC |
| htmx | Server-driven, minimal JS | Less common, learning curve | Interesting alternative |

**Rationale:** Reviewers should be able to open the UI without `npm install` or a build step. A single HTML file with embedded CSS/JS demonstrates the API contract visually.

## Production Tech Stack Summary

```
┌─────────────────────────────────────────────────────┐
│                    PRODUCTION STACK                   │
├─────────────────────────────────────────────────────┤
│ CDN:          CloudFront / Cloudflare                │
│ API Gateway:  Kong / AWS ALB                        │
│ App Server:   FastAPI on Uvicorn (multi-worker)     │
│ WebSocket:    Socket.io / native WS on separate pod │
│ Cache:        Redis Cluster (6 nodes)               │
│ Database:     PostgreSQL (users) + Cassandra (msgs) │
│ Queue:        Kafka (3 brokers, RF=3)               │
│ Search:       Elasticsearch                         │
│ Storage:      S3 (attachments, future)              │
│ Container:    Docker + Kubernetes (EKS)             │
│ CI/CD:        GitHub Actions → ArgoCD               │
│ Monitoring:   Prometheus + Grafana + PagerDuty      │
│ Tracing:      OpenTelemetry + Jaeger                │
│ Logging:      Structured JSON → Loki / ELK          │
└─────────────────────────────────────────────────────┘
```
