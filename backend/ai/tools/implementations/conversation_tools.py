"""
Conversation Retrieval and Search Tools.
Strictly bound to authenticated MongoDB user identity.
User A cannot access User B's conversations or messages.
"""

from typing import Dict, Any, List
from core.services.conversation_service import conversation_service
from core.services.message_service import message_service
from ai.tools.errors import UnauthorizedError, ForbiddenError, InvalidArgumentsError, ServiceUnavailableError


def get_conversation(conversation_id: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Retrieves metadata and recent messages of a conversation.
    Strictly verifies ownership: conversation.user_id == authenticated_user.user_id.
    """
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("Authentication required to access conversation.")

    if not conversation_id or not str(conversation_id).strip():
        raise InvalidArgumentsError("conversation_id must be provided.")

    clean_cid = str(conversation_id).strip()
    try:
        conv = conversation_service.get_conversation(user_id=user_id, conversation_id=clean_cid)
        if not conv:
            raise ForbiddenError(f"Conversation '{clean_cid}' not found or not owned by user.")

        # Additional explicit ownership verification
        if conv.get("user_id") != user_id:
            raise ForbiddenError("Cross-user conversation access violation.")

        # Fetch recent messages (up to 10)
        messages, total = message_service.list_messages(
            user_id=user_id,
            conversation_id=clean_cid,
            limit=10,
            desc=True,
        )

        return {
            "conversation_id": clean_cid,
            "title": conv.get("title", ""),
            "mode": conv.get("mode", "normal"),
            "status": conv.get("status", "active"),
            "messages_count": total,
            "recent_messages": [
                {
                    "role": m.get("role"),
                    "content": str(m.get("content", ""))[:300],  # Bounded content
                    "created_at": m.get("created_at"),
                }
                for m in messages
            ]
        }
    except (UnauthorizedError, ForbiddenError, InvalidArgumentsError):
        raise
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to retrieve conversation: {str(e)}")


def search_conversations(limit: int = 10, **kwargs: Any) -> Dict[str, Any]:
    """Lists conversations belonging strictly to the authenticated user."""
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("Authentication required to list conversations.")

    try:
        bounded_limit = max(1, min(int(limit), 20))
    except (ValueError, TypeError):
        bounded_limit = 10

    try:
        convs, total = conversation_service.list_conversations(user_id=user_id, limit=bounded_limit)
        return {
            "user_id": user_id,
            "count": len(convs),
            "total": total,
            "conversations": [
                {
                    "id": str(c.get("id")),
                    "title": c.get("title", ""),
                    "mode": c.get("mode", "normal"),
                    "last_message_at": c.get("last_message_at"),
                }
                for c in convs
            ]
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to list conversations: {str(e)}")
