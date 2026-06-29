# ADR-001: Use SQLite for POC

## Status
Accepted

## Context
We need persistent storage for messages, conversations, and user data. The submission must be easy for reviewers to clone and run without external dependencies.

## Options Considered
1. **SQLite** — File-based, zero configuration, ACID compliant
2. **PostgreSQL** — Production-grade, concurrent access, rich features
3. **In-memory dict** — Simplest possible, no persistence

## Decision
Use SQLite for the POC submission.

## Consequences
**Positive:**
- Reviewers run `pip install && pytest` with no database setup
- ACID transactions work correctly
- SQL schema is portable to PostgreSQL with minimal changes
- Repository pattern abstracts storage — swap requires only new implementation

**Negative:**
- No concurrent write support (single writer lock)
- No network access (embedded only)
- Missing PostgreSQL-specific features (LISTEN/NOTIFY, JSON operators)

**Migration path:**
- Repository interface remains identical
- Create `PostgresMessageRepository` implementing same interface
- Connection pooling via asyncpg/SQLAlchemy
- Schema migration via Alembic
