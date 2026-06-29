"""
Tests for authorization enforcement.

Proves that:
- Users cannot read conversations they're not part of (403)
- Users cannot list other users' conversations (403)
- Participants CAN read their conversations (200)
"""

import pytest


@pytest.mark.asyncio
async def test_unauthorized_read_returns_403(client):
    """
    A user who is NOT a participant cannot read conversation messages.
    This is the core authorization test required by the spec.
    """
    # Alice sends a message to Bob (creates conversation)
    r = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Private message"},
        headers={"X-User-Id": "1"},
    )
    conv_id = r.json()["conversation_id"]

    # Charlie (user 3) tries to read Alice-Bob's conversation
    r = await client.get(
        f"/api/v1/conversations/{conv_id}/messages",
        headers={"X-User-Id": "3"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_participant_can_read_conversation(client):
    """Both participants can read the conversation."""
    # Alice sends to Bob
    r = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Hello"},
        headers={"X-User-Id": "1"},
    )
    conv_id = r.json()["conversation_id"]

    # Alice can read
    r1 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages",
        headers={"X-User-Id": "1"},
    )
    assert r1.status_code == 200

    # Bob can read
    r2 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages",
        headers={"X-User-Id": "2"},
    )
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_cannot_list_other_users_conversations(client):
    """A user cannot view another user's conversation list."""
    # Alice tries to view Bob's conversations
    r = await client.get(
        "/api/v1/users/2/conversations",
        headers={"X-User-Id": "1"},  # Alice requesting Bob's list
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_can_list_own_conversations(client):
    """A user can list their own conversations."""
    # Create a conversation first
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Hey"},
        headers={"X-User-Id": "1"},
    )

    r = await client.get(
        "/api/v1/users/1/conversations",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200
    assert len(r.json()["conversations"]) == 1


@pytest.mark.asyncio
async def test_nonexistent_conversation_returns_404(client):
    """Accessing a conversation that doesn't exist returns 404."""
    r = await client.get(
        "/api/v1/conversations/9999/messages",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_conversation_list_only_shows_own(client):
    """User only sees conversations they're part of."""
    # Alice-Bob conversation
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Alice to Bob"},
        headers={"X-User-Id": "1"},
    )

    # Alice-Charlie conversation
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 3, "body": "Alice to Charlie"},
        headers={"X-User-Id": "1"},
    )

    # Bob's conversation list should only show Alice-Bob
    r = await client.get(
        "/api/v1/users/2/conversations",
        headers={"X-User-Id": "2"},
    )
    conversations = r.json()["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["other_user"]["username"] == "alice"

    # Alice should see both conversations
    r = await client.get(
        "/api/v1/users/1/conversations",
        headers={"X-User-Id": "1"},
    )
    assert len(r.json()["conversations"]) == 2
