"""
Tests for POST /messages endpoint.

Covers:
- Happy path: send message, verify response
- Conversation auto-creation
- Idempotency via client_message_id
- Validation: empty body, self-messaging, invalid recipient
- Authentication: missing header
"""

import pytest


@pytest.mark.asyncio
async def test_send_message_success(client):
    """Happy path: Alice sends a message to Bob."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Hello Bob!"},
        headers={"X-User-Id": "1"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sender_id"] == 1
    assert data["body"] == "Hello Bob!"
    assert data["conversation_id"] is not None
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_send_message_creates_conversation(client):
    """First message between two users creates a conversation."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "First message"},
        headers={"X-User-Id": "1"},
    )
    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Second message reuses the same conversation
    response2 = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Second message"},
        headers={"X-User-Id": "1"},
    )
    assert response2.status_code == 201
    assert response2.json()["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_send_message_reverse_direction_same_conversation(client):
    """Bob replying to Alice uses the same conversation."""
    # Alice sends to Bob
    r1 = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Hi Bob"},
        headers={"X-User-Id": "1"},
    )
    conv_id = r1.json()["conversation_id"]

    # Bob sends to Alice — same conversation
    r2 = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 1, "body": "Hi Alice"},
        headers={"X-User-Id": "2"},
    )
    assert r2.json()["conversation_id"] == conv_id


@pytest.mark.asyncio
async def test_send_message_idempotency(client):
    """Duplicate client_message_id returns the original message."""
    payload = {
        "recipient_id": 2,
        "body": "Idempotent message",
        "client_message_id": "unique-key-123",
    }

    r1 = await client.post("/api/v1/messages", json=payload, headers={"X-User-Id": "1"})
    r2 = await client.post("/api/v1/messages", json=payload, headers={"X-User-Id": "1"})

    assert r1.status_code == 201
    # Second request returns the same message (idempotent)
    assert r2.json()["id"] == r1.json()["id"]
    assert r2.json()["body"] == "Idempotent message"


@pytest.mark.asyncio
async def test_send_message_to_self_rejected(client):
    """Cannot send a message to yourself."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 1, "body": "Talking to myself"},
        headers={"X-User-Id": "1"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_send_message_to_nonexistent_user(client):
    """Cannot send a message to a user that doesn't exist."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 999, "body": "Hello ghost"},
        headers={"X-User-Id": "1"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message_empty_body_rejected(client):
    """Message body cannot be empty."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": ""},
        headers={"X-User-Id": "1"},
    )
    assert response.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_send_message_no_auth_header(client):
    """Request without X-User-Id returns 401."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "No auth"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_send_message_invalid_auth_header(client):
    """Non-integer X-User-Id returns 401."""
    response = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Bad auth"},
        headers={"X-User-Id": "not-a-number"},
    )
    assert response.status_code == 401
