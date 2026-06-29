"""
API Routes — HTTP layer.

Responsibilities:
- Parse and validate requests (via Pydantic schemas)
- Extract authentication context
- Delegate to service layer
- Format responses

This layer should be thin — no business logic here.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
import aiosqlite

from backend.app.database import get_db
from backend.app.middleware.auth import get_current_user_id
from backend.app.repositories.message_repository import MessageRepository
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.user_repository import UserRepository
from backend.app.services.message_service import MessageService
from backend.app.schemas.messages import (
    SendMessageRequest,
    MessageResponse,
    MessageListResponse,
    ConversationListResponse,
    ConversationResponse,
    LastMessageResponse,
    UserResponse,
    UserListResponse,
    PaginationInfo,
)

router = APIRouter(prefix="/api/v1")


def get_message_service(db: aiosqlite.Connection = Depends(get_db)) -> MessageService:
    """Dependency injection: wire up service with its repositories."""
    return MessageService(
        message_repo=MessageRepository(db),
        conversation_repo=ConversationRepository(db),
        user_repo=UserRepository(db),
    )


@router.post("/messages", status_code=201, response_model=MessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user_id: int = Depends(get_current_user_id),
    service: MessageService = Depends(get_message_service),
):
    """Send a message to another user."""
    message = await service.send_message(
        sender_id=current_user_id,
        recipient_id=request.recipient_id,
        body=request.body,
        client_message_id=request.client_message_id,
    )
    return MessageResponse(
        id=message["id"],
        conversation_id=message["conversation_id"],
        sender_id=message["sender_id"],
        body=message["body"],
        created_at=str(message["created_at"]),
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def get_conversation_messages(
    conversation_id: int,
    before: Optional[int] = Query(None, description="Cursor: return messages with id < this"),
    limit: int = Query(20, ge=1, le=100, description="Number of messages per page"),
    current_user_id: int = Depends(get_current_user_id),
    service: MessageService = Depends(get_message_service),
):
    """Fetch paginated message history for a conversation."""
    messages, has_more = await service.get_conversation_messages(
        user_id=current_user_id,
        conversation_id=conversation_id,
        before=before,
        limit=limit,
    )

    next_cursor = messages[-1]["id"] if messages and has_more else None

    return MessageListResponse(
        messages=[
            MessageResponse(
                id=m["id"],
                conversation_id=m["conversation_id"],
                sender_id=m["sender_id"],
                body=m["body"],
                created_at=str(m["created_at"]),
            )
            for m in messages
        ],
        pagination=PaginationInfo(
            has_more=has_more,
            next_cursor=next_cursor,
            limit=limit,
        ),
    )


@router.get(
    "/users/{user_id}/conversations",
    response_model=ConversationListResponse,
)
async def get_user_conversations(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    service: MessageService = Depends(get_message_service),
):
    """List all conversations for a user."""
    conversations = await service.get_user_conversations(user_id, current_user_id)

    return ConversationListResponse(
        conversations=[
            ConversationResponse(
                id=c["id"],
                other_user=UserResponse(
                    id=c["other_user"]["id"],
                    username=c["other_user"]["username"],
                ),
                last_message=(
                    LastMessageResponse(
                        id=c["last_message"]["id"],
                        body=c["last_message"]["body"],
                        sender_id=c["last_message"]["sender_id"],
                        created_at=str(c["last_message"]["created_at"]),
                    )
                    if c["last_message"]
                    else None
                ),
                updated_at=str(c["updated_at"]),
            )
            for c in conversations
        ],
        pagination=PaginationInfo(has_more=False, next_cursor=None, limit=20),
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(db: aiosqlite.Connection = Depends(get_db)):
    """List all users (utility endpoint for UI)."""
    repo = UserRepository(db)
    users = await repo.get_all()
    return UserListResponse(
        users=[UserResponse(id=u["id"], username=u["username"]) for u in users]
    )
