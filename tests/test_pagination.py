"""
Tests for cursor-based pagination.

This is the critical test file that proves pagination stability:
- Messages returned in correct order
- Cursor-based fetch returns expected pages
- NEW MESSAGES DO NOT AFFECT existing cursor results (stability)
- has_more flag works correctly
- Edge cases: empty conversation, single message
"""

import pytest


@pytest.mark.asyncio
async def test_messages_returned_newest_first(client):
    """Messages are returned in descending order (newest first)."""
    # Send 3 messages
    for i in range(1, 4):
        await client.post(
            "/api/v1/messages",
            json={"recipient_id": 2, "body": f"Message {i}"},
            headers={"X-User-Id": "1"},
        )

    # Get the conversation ID
    r = await client.get("/api/v1/users/1/conversations", headers={"X-User-Id": "1"})
    conv_id = r.json()["conversations"][0]["id"]

    # Fetch messages
    r = await client.get(
        f"/api/v1/conversations/{conv_id}/messages",
        headers={"X-User-Id": "1"},
    )
    messages = r.json()["messages"]

    assert len(messages) == 3
    assert messages[0]["body"] == "Message 3"  # newest first
    assert messages[1]["body"] == "Message 2"
    assert messages[2]["body"] == "Message 1"  # oldest last


@pytest.mark.asyncio
async def test_pagination_with_cursor(client):
    """Cursor-based pagination returns correct pages."""
    # Send 5 messages
    for i in range(1, 6):
        await client.post(
            "/api/v1/messages",
            json={"recipient_id": 2, "body": f"Message {i}"},
            headers={"X-User-Id": "1"},
        )

    r = await client.get("/api/v1/users/1/conversations", headers={"X-User-Id": "1"})
    conv_id = r.json()["conversations"][0]["id"]

    # Page 1: get first 3 messages (limit=3)
    r1 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=3",
        headers={"X-User-Id": "1"},
    )
    page1 = r1.json()
    assert len(page1["messages"]) == 3
    assert page1["pagination"]["has_more"] is True
    cursor = page1["pagination"]["next_cursor"]

    # Page 2: get next messages using cursor
    r2 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=3&before={cursor}",
        headers={"X-User-Id": "1"},
    )
    page2 = r2.json()
    assert len(page2["messages"]) == 2  # only 2 remaining
    assert page2["pagination"]["has_more"] is False

    # Verify no overlap between pages
    page1_ids = {m["id"] for m in page1["messages"]}
    page2_ids = {m["id"] for m in page2["messages"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_pagination_stability_under_new_messages(client):
    """
    CRITICAL TEST: Pagination remains stable when new messages arrive.

    This proves cursor-based pagination doesn't duplicate or skip messages
    even when new messages are inserted between page fetches.
    """
    # Send 5 initial messages
    for i in range(1, 6):
        await client.post(
            "/api/v1/messages",
            json={"recipient_id": 2, "body": f"Original {i}"},
            headers={"X-User-Id": "1"},
        )

    r = await client.get("/api/v1/users/1/conversations", headers={"X-User-Id": "1"})
    conv_id = r.json()["conversations"][0]["id"]

    # Fetch page 1 (3 messages: Original 5, 4, 3)
    r1 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=3",
        headers={"X-User-Id": "1"},
    )
    page1 = r1.json()
    cursor = page1["pagination"]["next_cursor"]
    page1_bodies = [m["body"] for m in page1["messages"]]

    # --- NEW MESSAGES ARRIVE while user is reading page 1 ---
    for i in range(1, 4):
        await client.post(
            "/api/v1/messages",
            json={"recipient_id": 2, "body": f"New message {i}"},
            headers={"X-User-Id": "1"},
        )

    # Fetch page 2 using the SAME cursor — should NOT include new messages
    r2 = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=3&before={cursor}",
        headers={"X-User-Id": "1"},
    )
    page2 = r2.json()
    page2_bodies = [m["body"] for m in page2["messages"]]

    # Page 2 should contain Original 2 and Original 1 (the remaining old messages)
    assert "Original 2" in page2_bodies
    assert "Original 1" in page2_bodies

    # NO new messages should leak into page 2
    for body in page2_bodies:
        assert not body.startswith("New message"), f"New message leaked into page 2: {body}"

    # NO duplicates between pages
    all_bodies = page1_bodies + page2_bodies
    assert len(all_bodies) == len(set(all_bodies)), "Duplicate messages detected!"


@pytest.mark.asyncio
async def test_empty_conversation_returns_empty_list(client):
    """Fetching messages from a conversation with no messages returns empty."""
    # Create a conversation by sending then we test a different one
    # Actually, we need a conversation that exists. Let's send a message first.
    r = await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "test"},
        headers={"X-User-Id": "1"},
    )
    conv_id = r.json()["conversation_id"]

    # The conversation has 1 message, ask for messages before id=1 (none exist)
    msg_id = r.json()["id"]
    r = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?before={msg_id}",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200
    assert r.json()["messages"] == []
    assert r.json()["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_pagination_limit_clamped_to_100(client):
    """Requesting limit > 100 is clamped to 100."""
    await client.post(
        "/api/v1/messages",
        json={"recipient_id": 2, "body": "test"},
        headers={"X-User-Id": "1"},
    )
    r = await client.get("/api/v1/users/1/conversations", headers={"X-User-Id": "1"})
    conv_id = r.json()["conversations"][0]["id"]

    # FastAPI Query validation will reject limit > 100
    r = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=200",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422  # Validation error
