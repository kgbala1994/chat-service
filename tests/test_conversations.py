"""
Tests for conversation listing endpoint.

Covers:
- Conversations ordered by recent activity
- Last message preview included
- Multiple conversations for one user
"""

import pytest


@pytest.mark.asyncio
async def test_conversations_ordered_by_recent_activity(client):
    """Conversations are sorted with most recently active first."""
    # Alice sends to Bob first
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Old message to Bob"},
        headers={"X-User-Id": "1"},
    )

    # Then Alice sends to Charlie
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 3, "body": "New message to Charlie"},
        headers={"X-User-Id": "1"},
    )

    r = await client.get(
        "/api/v1/users/1/conversations",
        headers={"X-User-Id": "1"},
    )
    conversations = r.json()["conversations"]

    # Charlie conversation should be first (more recent)
    assert conversations[0]["other_user"]["username"] == "charlie"
    assert conversations[1]["other_user"]["username"] == "bob"


@pytest.mark.asyncio
async def test_conversation_includes_last_message(client):
    """Conversation listing includes last message preview."""
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "First"},
        headers={"X-User-Id": "1"},
    )
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "Second (latest)"},
        headers={"X-User-Id": "1"},
    )

    r = await client.get(
        "/api/v1/users/1/conversations",
        headers={"X-User-Id": "1"},
    )
    conv = r.json()["conversations"][0]
    assert conv["last_message"]["body"] == "Second (latest)"


@pytest.mark.asyncio
async def test_no_conversations_returns_empty(client):
    """User with no conversations gets empty list."""
    r = await client.get(
        "/api/v1/users/3/conversations",
        headers={"X-User-Id": "3"},
    )
    assert r.status_code == 200
    assert r.json()["conversations"] == []
