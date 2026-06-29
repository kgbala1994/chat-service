# Architecture Options

## Option 1: Monolith with PostgreSQL (Selected for POC)

```
┌─────────────────────────────────────────┐
│              Client (UI)                 │
└────────────────────┬────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────┐
│         FastAPI Application              │
│  ┌──────────┬───────────┬────────────┐  │
│  │  Routes  │  Service  │  Repository│  │
│  └──────────┴───────────┴─────┬──────┘  │
└───────────────────────────────┼─────────┘
                                │
┌───────────────────────────────▼─────────┐
│            SQLite / PostgreSQL           │
└─────────────────────────────────────────┘
```

| Aspect | Assessment |
|--------|-----------|
| Pros | Simple deployment, ACID transactions, fast iteration, easy testing |
| Cons | Single point of failure, vertical scaling only, no real-time push |
| Best for | POC, <1000 concurrent users, proving correctness |
| Migration path | Extract services, add Redis cache, add WebSocket server |

## Option 2: Microservices with Event Streaming (Production Target)

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Web UI  │     │ Mobile   │     │  API GW  │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                 │                 │
     └─────────────────┴─────────────────┘
                       │
          ┌────────────▼────────────┐
          │      API Gateway        │
          │   (Kong / AWS ALB)      │
          └────┬───────────┬────────┘
               │           │
    ┌──────────▼──┐  ┌─────▼────────────┐
    │  Message    │  │  Conversation    │
    │  Service    │  │  Service         │
    └──────┬──────┘  └──────┬───────────┘
           │                │
    ┌──────▼──────┐         │
    │    Kafka    │◄────────┘
    └──┬───┬──┬──┘
       │   │   │
       ▼   ▼   ▼
    ┌────┐┌────┐┌──────────┐
    │ DB ││Cache││Notify Svc│
    └────┘└────┘└──────────┘

DB: Cassandra (messages) + PostgreSQL (users/conversations)
Cache: Redis (recent messages, unread counts, sessions)
Notify: WebSocket server + Push notification service
```

| Aspect | Assessment |
|--------|-----------|
| Pros | Horizontal scaling, event replay, independent deployments, fault isolation |
| Cons | Operational complexity, eventual consistency, network partitions, higher cost |
| Best for | >10K concurrent users, multi-region, high availability requirement |
| Trade-off | Complexity proportional to scale need |

## Option 3: Serverless (AWS Lambda + DynamoDB)

```
┌──────────┐
│  Client  │
└────┬─────┘
     │
┌────▼─────────┐
│ API Gateway  │
│  (AWS)       │
└────┬─────────┘
     │
┌────▼─────────┐     ┌──────────────┐
│   Lambda     │────▶│  DynamoDB    │
│  Functions   │     │  (Messages)  │
└────┬─────────┘     └──────────────┘
     │
┌────▼─────────┐
│  WebSocket   │
│  API (AWS)   │
└──────────────┘
```

| Aspect | Assessment |
|--------|-----------|
| Pros | Zero ops, auto-scaling, pay-per-use, managed WebSocket |
| Cons | Cold starts (latency), vendor lock-in, limited local testing, DynamoDB query limitations |
| Best for | Variable load, small team, cost-sensitive startups |
| Trade-off | Vendor lock-in vs operational simplicity |

## Decision Matrix

| Criteria (Weight) | Option 1: Monolith | Option 2: Microservices | Option 3: Serverless |
|-------------------|:------------------:|:-----------------------:|:--------------------:|
| Simplicity (30%) | 5 | 2 | 3 |
| Scalability (20%) | 2 | 5 | 4 |
| Testability (20%) | 5 | 3 | 2 |
| Reviewer experience (15%) | 5 | 3 | 2 |
| Production readiness (15%) | 3 | 5 | 4 |
| **Weighted Score** | **4.15** | **3.40** | **2.95** |

## Final Decision

**Option 1 (Monolith with PostgreSQL/SQLite) for the POC submission.**

### Rationale:
1. Reviewers can `git clone && pip install && pytest` — no Docker/Kafka/Redis needed
2. Demonstrates correctness of data model, pagination, and authorization
3. Clean layered architecture (Repository pattern) makes migration to Option 2 straightforward
4. Code quality and test coverage matter more than infrastructure complexity for this evaluation

### Production Migration Path:
```
Phase 1: Add Redis cache layer (conversation list, recent messages)
Phase 2: Add WebSocket server alongside REST API
Phase 3: Introduce Kafka for async message processing
Phase 4: Migrate messages table to Cassandra (partition by conversation_id)
Phase 5: Split into Message Service + Conversation Service
```

### What This Proves:
- Data model is correct and scales conceptually
- Pagination is cursor-based (works identically with Cassandra)
- Authorization logic is service-layer (portable between architectures)
- Repository pattern means swapping SQLite → PostgreSQL → Cassandra requires only new repository implementation
