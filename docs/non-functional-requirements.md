# Non-Functional Requirements

## Performance Targets

| Requirement | POC Target | Production Target | Rationale |
|-------------|-----------|-------------------|-----------|
| Send message latency (p99) | < 200ms | < 100ms | User perceives instant delivery |
| History fetch latency (p99) | < 300ms | < 200ms | Smooth scroll experience |
| Conversation list latency | < 300ms | < 150ms | Immediate inbox load |
| Throughput (messages/sec) | 100 | 100,000 | 10M DAU, avg 10 msg/user/day |
| Concurrent connections | 10 | 1,000,000 | 10% DAU online simultaneously |

## Scale Assumptions (Production)

| Metric | Value | Derivation |
|--------|-------|------------|
| Daily Active Users (DAU) | 10M | Business target |
| Messages per user per day | 10 | Industry average for 1:1 |
| Total messages per day | 100M | 10M * 10 |
| Peak messages per second | ~3,000 | 100M / 86400 * 3 (peak multiplier) |
| Average message size | 500 bytes | Text-only constraint |
| Storage per day | ~50 GB | 100M * 500 bytes |
| Storage per year | ~18 TB | 50 GB * 365 |
| Retention period | 5 years | Compliance requirement |
| Total storage (5yr) | ~90 TB | 18 TB * 5 |

## Availability & Reliability

| Requirement | POC | Production |
|-------------|-----|------------|
| Availability | Best effort | 99.99% (52 min downtime/year) |
| Data durability | SQLite file | 99.999999999% (11 nines, replicated) |
| Message ordering | Per-conversation sequential | Per-conversation sequential |
| Delivery guarantee | At-most-once | At-least-once with deduplication |
| Consistency model | Strong (single SQLite) | Eventual (read replicas) with causal ordering |

## Security

| Requirement | POC | Production |
|-------------|-----|------------|
| Authentication | Mocked (X-User-Id header) | JWT + OAuth2 (Auth0/Cognito) |
| Authorization | Participant check per request | RBAC with blocked/muted states |
| Transport encryption | HTTP (local dev) | TLS 1.3 mandatory |
| Data at rest | Unencrypted SQLite | AES-256 encrypted storage |
| Message privacy | Server-readable | Optional E2E encryption (Signal Protocol) |
| Audit logging | None | Full access audit trail |

## Observability (Production)

| Aspect | Tool | Purpose |
|--------|------|---------|
| Metrics | Prometheus + Grafana | Latency percentiles, throughput, error rates |
| Logging | Structured JSON → ELK | Request tracing, error debugging |
| Tracing | OpenTelemetry + Jaeger | Cross-service request flow |
| Alerting | PagerDuty + Grafana Alerts | SLO breach notification |
| Health checks | /health endpoint | Load balancer integration |

## How NFRs Drive Architecture

```
NFR: 100k msg/sec throughput
  → Decision: Kafka for write buffering (not direct DB writes)
  → Decision: Cassandra for horizontal write scaling

NFR: <100ms send latency
  → Decision: Async persistence (ack after Kafka, not DB commit)
  → Decision: Redis for recent message cache

NFR: 99.99% availability
  → Decision: Multi-AZ deployment
  → Decision: Circuit breakers between services
  → Decision: Graceful degradation (serve from cache if DB down)

NFR: 5-year retention at 90TB
  → Decision: Time-series partitioning on messages table
  → Decision: Cold storage tier for messages > 1 year old
  → Decision: Compression for archived data
```

## POC Simplifications (Documented Trade-offs)

| Production Need | POC Approach | Why Acceptable |
|-----------------|--------------|----------------|
| 100k msg/sec | Single process | Demonstrates correctness, not scale |
| Multi-region | Single SQLite | Proves data model works |
| Real-time delivery | REST polling | Proves API contract works |
| E2E encryption | Plaintext | Focus on authorization logic |
| Monitoring | Print logs | Focus on business logic |
