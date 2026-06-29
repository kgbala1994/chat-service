"""
Pydantic schemas for request validation and response serialization.

Separating schemas from models follows the DTO (Data Transfer Object) pattern:
- Request schemas validate input
- Response schemas control what's exposed to clients
- Internal models can evolve independently of the API contract
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SendMessageRequest(BaseModel):
    recipient_id: int = Field(..., description="ID of the user to send the message to")
    body: str = Field(..., min_length=1, max_length=10000, description="Message text")
    client_message_id: Optional[str] = Field(
        None, description="Optional idempotency key to prevent duplicate sends"
    )


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    body: str
    created_at: str


class PaginationInfo(BaseModel):
    has_more: bool
    next_cursor: Optional[int] = None
    limit: int


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    pagination: PaginationInfo


class UserResponse(BaseModel):
    id: int
    username: str


class LastMessageResponse(BaseModel):
    id: int
    body: str
    sender_id: int
    created_at: str


class ConversationResponse(BaseModel):
    id: int
    other_user: UserResponse
    last_message: Optional[LastMessageResponse] = None
    updated_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    pagination: PaginationInfo


class UserListResponse(BaseModel):
    users: list[UserResponse]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
