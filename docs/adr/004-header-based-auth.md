# ADR-004: Use Header-Based Authentication for POC

## Status
Accepted

## Context
The service must enforce that users can only read conversations they participate in. We need an authentication mechanism to identify the requesting user.

## Options Considered
1. **X-User-Id header** — Trivial to implement, no token infrastructure
2. **JWT tokens** — Production-standard, self-contained, expirable
3. **Session cookies** — Stateful, requires session store
4. **API keys** — Per-user, requires key management

## Decision
Use `X-User-Id` header for the POC. Document JWT as the production approach.

## Rationale
- **Focus on authorization logic**, not authentication infrastructure
- Reviewers can test any user by changing a header value (no token generation needed)
- The authorization middleware (participant check) is the interesting part — it's identical regardless of how user identity is established
- UI can easily switch users via dropdown → header change

## Authorization Logic (The Important Part)

```python
# This is what we're actually testing/demonstrating:
async def authorize_conversation_access(user_id: int, conversation_id: int):
    is_participant = await repo.is_participant(user_id, conversation_id)
    if not is_participant:
        raise HTTPException(status_code=403, detail="Not a participant")
```

This logic is **unchanged** whether user_id comes from:
- `X-User-Id` header (POC)
- JWT token payload (production)
- OAuth2 token introspection (enterprise)

## Production Auth Architecture

```
┌────────┐     ┌──────────┐     ┌─────────────┐     ┌─────────┐
│ Client │────▶│ API GW   │────▶│ Auth Service│────▶│ Identity│
│        │     │ (Kong)   │     │ (validates) │     │Provider │
└────────┘     └────┬─────┘     └─────────────┘     │(Auth0)  │
                    │                                 └─────────┘
                    │ X-User-Id (from validated JWT)
                    ▼
              ┌──────────┐
              │ Chat Svc │
              └──────────┘
```

In production, the API Gateway validates the JWT and injects a trusted `X-User-Id` header — so the chat service code remains identical.

## Consequences
**Positive:**
- Zero auth infrastructure needed to run/test
- Authorization logic is fully testable
- Same middleware code works in production (user_id source changes, logic doesn't)
- UI demo is trivial (dropdown to switch users)

**Negative:**
- Not secure in any real sense (anyone can set the header)
- No token expiry, refresh, or revocation
- Can't demonstrate auth error flows (invalid token, expired)

**Acceptable because:**
- The assignment tests *authorization* (who can read what), not *authentication* (proving identity)
- Our 403 test proves the authorization logic works
- Production auth is an infrastructure concern, not a business logic concern
