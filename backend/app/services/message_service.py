"""
Message Service — Business logic for messaging.

Orchestrates repositories and enforces business rules:
- Cannot message yourself
- Recipient must exist
- Conversation is created or reused transparently
- Idempotency via client_message_id
- Authorization checks for reading

This layer is where CQRS would be applied at scale:
- Commands: SendMessage (write path → Kafka → persistence)
- Queries: GetHistory, ListConversations (read path → cache/replica)
"""

from typing import Optional
from fastapi import HTTPException

from backend.app.repositories.message_repository import MessageRepository
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.user_repository import UserRepository


class MessageService:
    def __init__(
        self,
        message_repo: MessageRepository,
        conversation_repo: ConversationRepository,
        user_repo: UserRepository,
    ):
        self.message_repo = message_repo
        self.conversation_repo = conversation_repo
        self.user_repo = user_repo

    async def send_message(
        self,
        sender_id: int,
        recipient_id: int,
        body: str,
        client_message_id: Optional[str] = None,
    ) -> dict:
        """
        Send a message from sender to recipient.

        Business rules:
        1. Cannot message yourself
        2. Recipient must exist
        3. Idempotency: if client_message_id already exists, return existing message
        4. Create conversation if none exists between the two users
        5. Update conversation timestamp for sorting
        """
        # Rule 1: Cannot message yourself
        if sender_id == recipient_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_RECIPIENT", "message": "Cannot send a message to yourself"},
            )

        # Rule 2: Recipient must exist
        if not await self.user_repo.exists(recipient_id):
            raise HTTPException(
                status_code=404,
                detail={"code": "USER_NOT_FOUND", "message": "Recipient does not exist"},
            )

        # Rule 3: Idempotency check
        if client_message_id:
            existing = await self.message_repo.get_by_client_message_id(client_message_id)
            if existing:
                return existing

        # Rule 4: Find or create conversation
        conversation_id = await self.conversation_repo.find_conversation_between(
            sender_id, recipient_id
        )
        if not conversation_id:
            conversation_id = await self.conversation_repo.create_conversation(
                sender_id, recipient_id
            )

        # Create message
        message = await self.message_repo.create_message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            body=body,
            client_message_id=client_message_id,
        )

        # Rule 5: Update conversation timestamp
        await self.conversation_repo.update_conversation_timestamp(conversation_id)

        return message

    async def get_conversation_messages(
        self,
        user_id: int,
        conversation_id: int,
        before: Optional[int] = None,
        limit: int = 20,
    ) -> tuple[list[dict], bool]:
        """
        Get paginated messages for a conversation.

        Authorization: user must be a participant.
        """
        # Check conversation exists
        if not await self.conversation_repo.conversation_exists(conversation_id):
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": "Conversation does not exist"},
            )

        # Authorization check
        if not await self.conversation_repo.is_participant(user_id, conversation_id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": "You are not a participant in this conversation",
                },
            )

        # Clamp limit
        limit = min(limit, 100)

        return await self.message_repo.get_messages(conversation_id, before, limit)

    async def get_user_conversations(self, user_id: int, requesting_user_id: int) -> list[dict]:
        """
        Get all conversations for a user with last message preview.

        Authorization: can only list your own conversations.
        """
        if user_id != requesting_user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": "Cannot view another user's conversations",
                },
            )

        conversations = await self.conversation_repo.get_user_conversations(user_id)

        # Enrich with last message
        result = []
        for conv in conversations:
            last_msg = await self.message_repo.get_last_message(conv["conversation_id"])
            result.append(
                {
                    "id": conv["conversation_id"],
                    "other_user": {
                        "id": conv["other_user_id"],
                        "username": conv["other_username"],
                    },
                    "last_message": (
                        {
                            "id": last_msg["id"],
                            "body": last_msg["body"],
                            "sender_id": last_msg["sender_id"],
                            "created_at": last_msg["created_at"],
                        }
                        if last_msg
                        else None
                    ),
                    "updated_at": conv["updated_at"],
                }
            )
        return result
