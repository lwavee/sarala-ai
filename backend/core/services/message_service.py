import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from core.supabase_client import supabase_manager
from core.services.conversation_service import conversation_service

logger = logging.getLogger("sarala.services.message")

ALLOWED_ROLES = {"user", "assistant", "system", "tool"}


class MessageService:
    """
    Manages messages in Supabase PostgreSQL.
    Enforces dual verification:
    1. Conversation must belong to authenticated user_id.
    2. Message.user_id must match authenticated user_id.
    """

    def __init__(self):
        # In-memory fallback: Dict[conversation_id, List[message_dict]]
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    def list_messages(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Lists messages for a conversation, first ensuring the conversation belongs to user_id.
        Prevents unauthorized viewing of another user's conversation messages.
        """
        # 1. Enforce conversation ownership
        conv = conversation_service.get_conversation(user_id, conversation_id)
        if not conv:
            logger.warning(f"Unauthorized message access attempt by user {user_id} on conv {conversation_id}")
            return []

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("messages")
                if tbl is not None:
                    res: Any = (
                        tbl.select("*")
                        .eq("conversation_id", conversation_id)
                        .eq("user_id", user_id)
                        .order("created_at", desc=False)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    if res and isinstance(res.data, list):
                        self._cache[conversation_id] = res.data
                        return res.data
            except Exception as e:
                logger.debug(f"Supabase list messages failed: {e}")

        cached = self._cache.get(conversation_id, [])
        return cached[offset : offset + limit]

    def create_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a message in a conversation.
        Validates role and ensures conversation ownership.
        Updates conversation.last_message_at.
        """
        # Verify conversation ownership
        conv = conversation_service.get_conversation(user_id, conversation_id)
        if not conv:
            logger.warning(f"Cannot create message: conversation {conversation_id} not owned by user {user_id}")
            return None

        role_clean = role.lower().strip()
        if role_clean not in ALLOWED_ROLES:
            role_clean = "user"

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        msg_id = str(uuid.uuid4())
        doc = {
            "id": msg_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role_clean,
            "content": content,
            "message_type": message_type,
            "metadata": metadata or {},
            "created_at": now,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("messages")
                if tbl is not None:
                    res: Any = tbl.insert(doc).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        doc = res.data[0]
            except Exception as e:
                logger.debug(f"Supabase insert message failed: {e}")

        # Update cache
        self._cache.setdefault(conversation_id, []).append(doc)

        # Update conversation timestamp
        conversation_service.update_conversation(user_id, conversation_id, {"last_message_at": now})

        return doc


message_service = MessageService()
