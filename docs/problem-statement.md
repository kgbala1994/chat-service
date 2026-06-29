# Problem Statement: One-to-One Messaging Service

## Overview

Build a backend REST API for one-to-one messaging between users. The service must support sending messages, retrieving paginated conversation history, and listing a user's conversations with proper access control.

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Send a message from one user to another | Must Have |
| FR-2 | Retrieve conversation history with pagination | Must Have |
| FR-3 | List all conversations for a given user | Must Have |
| FR-4 | Persist messages with consistent ordering | Must Have |
| FR-5 | Enforce read authorization (user can only access their own conversations) | Must Have |
| FR-6 | Pagination must remain stable as new messages arrive | Must Have |

## Assumptions

| # | Assumption | Rationale |
|---|-----------|-----------|
| 1 | Only 1:1 (direct) messaging — no group chat | Scope constraint for POC |
| 2 | Messages are immutable once sent (no edit/delete) | Simplifies ordering and consistency |
| 3 | Ordering is guaranteed within a conversation | Users expect chronological display |
| 4 | Authentication is mocked via header (`X-User-Id`) | Focus on authorization logic, not auth infra |
| 5 | No media/attachment support | Text-only keeps scope manageable |
| 6 | No real-time push (polling only for POC) | REST-first; WebSocket is a documented future enhancement |
| 7 | Users are pre-seeded; no registration flow | Not testing user management |
| 8 | Single-region deployment | No geo-distribution concerns for POC |

## Out of Scope (Documented for Future)

- Group messaging
- Message editing / deletion / reactions
- Read receipts and typing indicators
- File/media attachments
- End-to-end encryption
- Push notifications
- User presence/online status
- Message search
- Rate limiting and abuse prevention

## Success Criteria

1. All three core endpoints work correctly
2. Cursor-based pagination returns stable results under concurrent writes
3. Authorization is enforced — 403 returned for unauthorized access
4. Automated tests cover happy paths and edge cases
5. Code is clean, documented, and explainable
