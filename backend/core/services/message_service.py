import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Tuple
from core.supabase_client import supabase_manager
from core.services.conversation_service import conversation_service

logger = logging.getLogger("sarala.services.message")

ALLOWED_ROLES = {"user", "assistant", "system", "tool"}
MAX_MESSAGE_LENGTH = 50000


class MessageService:
    """
    Manages messages in Supabase PostgreSQL with resilient in-memory fallback.
    Enforces dual verification:
    1. Conversation must belong to authenticated user_id.
    2. Message.user_id must match authenticated user_id.
    """

    def __init__(self):
        # In-memory user and conversation partitioned fallback: Dict[conversation_id, List[message_dict]]
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    def list_messages(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
        desc: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Lists messages for a conversation, first ensuring the conversation belongs to user_id.
        Prevents unauthorized viewing of another user's conversation messages.
        Returns (items, total_count).
        """
        # 1. Enforce conversation ownership
        conv = conversation_service.get_conversation(user_id, conversation_id)
        if not conv:
            logger.warning(f"Unauthorized message access attempt by user {user_id} on conv {conversation_id}")
            return [], 0

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("messages")
                if tbl is not None:
                    res: Any = (
                        tbl.select("*", count="exact")
                        .eq("conversation_id", conversation_id)
                        .eq("user_id", user_id)
                        .order("created_at", desc=desc)
                        .order("id", desc=desc)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    if res and isinstance(res.data, list):
                        total = res.count if hasattr(res, "count") and res.count is not None else len(res.data)
                        if not desc and offset == 0:
                            self._cache[conversation_id] = res.data
                        return res.data, total
            except Exception as e:
                logger.debug(f"Supabase list messages failed: {e}")

        cached = list(self._cache.get(conversation_id, []))
        cached.sort(key=lambda m: (m.get("created_at", ""), m.get("seq", 0)), reverse=desc)
        total = len(cached)
        return cached[offset : offset + limit], total

    def create_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        client_message_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a message in a conversation.
        Validates role, content length, and verifies conversation ownership.
        Enforces idempotency if client_message_id is provided.
        Updates conversation.last_message_at.
        """
        # Verify conversation ownership
        conv = conversation_service.get_conversation(user_id, conversation_id)
        if not conv:
            logger.warning(f"Cannot create message: conversation {conversation_id} not owned by user {user_id}")
            return None

        # Check idempotency / deduplication
        meta = dict(metadata or {})
        if client_message_id:
            meta["client_message_id"] = client_message_id
            for cached_msg in self._cache.get(conversation_id, []):
                msg_meta = cached_msg.get("metadata") or {}
                if msg_meta.get("client_message_id") == client_message_id:
                    logger.info(f"Duplicate message suppressed for client_message_id={client_message_id}")
                    return cached_msg

            if supabase_manager.is_connected and supabase_manager.client:
                try:
                    tbl = supabase_manager.table("messages")
                    if tbl is not None:
                        res = (
                            tbl.select("*")
                            .eq("conversation_id", conversation_id)
                            .eq("user_id", user_id)
                            .contains("metadata", {"client_message_id": client_message_id})
                            .execute()
                        )
                        if res and isinstance(res.data, list) and len(res.data) > 0:
                            logger.info(f"Duplicate message suppressed from DB for client_message_id={client_message_id}")
                            return res.data[0]
                except Exception as e:
                    logger.debug(f"Supabase duplicate check fallback: {e}")

        role_clean = role.lower().strip()
        if role_clean not in ALLOWED_ROLES:
            role_clean = "user"

        content_clean = content.strip()
        if not content_clean:
            return None

        if len(content_clean) > MAX_MESSAGE_LENGTH:
            content_clean = content_clean[:MAX_MESSAGE_LENGTH]

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        msg_id = str(uuid.uuid4())
        existing_msgs = self._cache.setdefault(conversation_id, [])
        seq = len(existing_msgs)
        doc = {
            "id": msg_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role_clean,
            "content": content_clean,
            "message_type": message_type,
            "metadata": meta,
            "created_at": now,
            "seq": seq,
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

        # Update conversation timestamp and increment message count
        actual_count = len(self._cache.get(conversation_id, []))
        stored_count = int(conv.get("message_count") or 0)
        new_count = max(actual_count, stored_count + 1)
        conversation_service.update_conversation(
            user_id,
            conversation_id,
            {"last_message_at": now, "message_count": new_count}
        )

        return doc

    def delete_conversation_messages(self, conversation_id: str) -> None:
        """Cleans up cached messages when a conversation is deleted."""
        if conversation_id in self._cache:
            del self._cache[conversation_id]

    def get_message(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a message if it belongs to authenticated user_id.
        Verifies ownership and prevents cross-user message access.
        """
        if not user_id or not message_id:
            return None

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("messages")
                if tbl is not None:
                    res: Any = (
                        tbl.select("*")
                        .eq("id", message_id)
                        .eq("user_id", user_id)
                        .execute()
                    )
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        return res.data[0]
            except Exception as e:
                logger.debug(f"Supabase get_message failed: {e}")

        # Check in cache across all conversations
        for cid, msgs in self._cache.items():
            for m in msgs:
                if str(m.get("id")) == message_id and m.get("user_id") == user_id:
                    return m
        return None

    def find_matching_conversation_ids(
        self,
        user_id: str,
        query: str,
        limit: int = 100,
    ) -> List[str]:
        """
        Finds conversation IDs belonging to user_id that contain messages matching query.
        Guarantees:
        1. Only searches messages where message.user_id == user_id.
        2. Deduplicates matched conversation IDs.
        3. Returns up to limit distinct conversation IDs.
        """
        if not user_id or not query or not query.strip():
            return []

        clean = query.strip()
        matching_ids: List[str] = []
        seen = set()

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("messages")
                if tbl is not None:
                    res: Any = (
                        tbl.select("conversation_id")
                        .eq("user_id", user_id)
                        .ilike("content", f"%{clean}%")
                        .limit(limit * 3)
                        .execute()
                    )
                    if res and isinstance(res.data, list):
                        for row in res.data:
                            cid = str(row.get("conversation_id"))
                            if cid and cid not in seen:
                                seen.add(cid)
                                matching_ids.append(cid)
                                if len(matching_ids) >= limit:
                                    break
                        return matching_ids
            except Exception as e:
                logger.debug(f"Supabase message search query failed for user {user_id}: {e}")

        # Local cache fallback: check all conversations in _cache that belong to user_id
        q_lower = clean.lower()
        for cid, msgs in self._cache.items():
            if cid in seen:
                continue
            for m in msgs:
                if m.get("user_id") == user_id and q_lower in str(m.get("content", "")).lower():
                    seen.add(cid)
                    matching_ids.append(cid)
                    break
            if len(matching_ids) >= limit:
                break

        return matching_ids


message_service = MessageService()


class ChatIdempotencyTracker:
    """
    In-memory LRU-bounded idempotency tracker for chat requests.
    Prevents duplicate AI generation or duplicate assistant messages caused by:
    - double-clicking send
    - network retries
    - frontend re-renders
    """

    def __init__(self, max_size: int = 1000):
        self._completed: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._max_size = max_size

    def get_completed(self, user_id: str, client_message_id: str) -> Optional[Dict[str, Any]]:
        if not user_id or not client_message_id:
            return None
        return self._completed.get((user_id, client_message_id))

    def set_completed(self, user_id: str, client_message_id: str, response: Dict[str, Any]) -> None:
        if not user_id or not client_message_id:
            return
        if len(self._completed) >= self._max_size:
            # Evict oldest 20%
            keys = list(self._completed.keys())[: int(self._max_size * 0.2)]
            for k in keys:
                self._completed.pop(k, None)
        self._completed[(user_id, client_message_id)] = response

    def clear(self) -> None:
        self._completed.clear()


chat_idempotency_tracker = ChatIdempotencyTracker()
