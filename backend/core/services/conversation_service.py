import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.conversation")


class ConversationService:
    """
    Manages conversations in Supabase PostgreSQL.
    Enforces strict ownership: conversation.user_id == authenticated MongoDB user_id.
    """

    def __init__(self):
        # In-memory fallback: Dict[user_id, Dict[conversation_id, conversation_dict]]
        self._user_conversations: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def list_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Lists conversations belonging exclusively to the authenticated user_id."""
        if not user_id:
            return []

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    res: Any = (
                        tbl.select("*")
                        .eq("user_id", user_id)
                        .order("last_message_at", desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    if res and isinstance(res.data, list):
                        # Cache local copy
                        user_store = self._user_conversations.setdefault(user_id, {})
                        for row in res.data:
                            user_store[str(row["id"])] = row
                        return res.data
            except Exception as e:
                logger.debug(f"Supabase list conversations failed for {user_id}: {e}")

        # Local memory fallback
        user_store = self._user_conversations.get(user_id, {})
        convs = sorted(
            user_store.values(),
            key=lambda c: c.get("last_message_at", c.get("created_at", "")),
            reverse=True,
        )
        return convs[offset : offset + limit]

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single conversation, verifying that it belongs to the authenticated user_id.
        Returns None if not found or if owned by another user (preventing ID enumeration).
        """
        if not user_id or not conversation_id:
            return None

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    res: Any = tbl.select("*").eq("id", conversation_id).eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        row = res.data[0]
                        self._user_conversations.setdefault(user_id, {})[conversation_id] = row
                        return row
            except Exception as e:
                logger.debug(f"Supabase get conversation failed: {e}")

        return self._user_conversations.get(user_id, {}).get(conversation_id)

    def create_conversation(
        self,
        user_id: str,
        title: str = "New Conversation",
        mode: str = "normal",
    ) -> Dict[str, Any]:
        """Creates a new conversation owned by the authenticated user_id."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conv_id = str(uuid.uuid4())
        doc = {
            "id": conv_id,
            "user_id": user_id,
            "title": title.strip() or "New Conversation",
            "mode": mode,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "last_message_at": now,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    res: Any = tbl.insert(doc).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        doc = res.data[0]
            except Exception as e:
                logger.debug(f"Supabase create conversation failed: {e}")

        self._user_conversations.setdefault(user_id, {})[conv_id] = doc
        return doc

    def update_conversation(
        self,
        user_id: str,
        conversation_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Updates conversation title, mode, status, or last_message_at.
        Enforces user_id ownership and prevents transferring ownership.
        """
        existing = self.get_conversation(user_id, conversation_id)
        if not existing:
            return None

        allowed = {"title", "mode", "status", "last_message_at"}
        sanitized = {k: v for k, v in updates.items() if k in allowed}
        sanitized["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    res: Any = tbl.update(sanitized).eq("id", conversation_id).eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        merged = {**existing, **res.data[0]}
                        self._user_conversations.setdefault(user_id, {})[conversation_id] = merged
                        return merged
            except Exception as e:
                logger.debug(f"Supabase update conversation failed: {e}")

        merged = {**existing, **sanitized}
        self._user_conversations.setdefault(user_id, {})[conversation_id] = merged
        return merged

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Deletes conversation if owned by authenticated user_id."""
        existing = self.get_conversation(user_id, conversation_id)
        if not existing:
            return False

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    tbl.delete().eq("id", conversation_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.debug(f"Supabase delete conversation failed: {e}")

        if user_id in self._user_conversations and conversation_id in self._user_conversations[user_id]:
            del self._user_conversations[user_id][conversation_id]
        return True


conversation_service = ConversationService()
