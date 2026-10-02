import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Tuple
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.conversation")


class ConversationService:
    """
    Manages conversations in Supabase PostgreSQL with resilient in-memory fallback.
    Enforces strict ownership: conversation.user_id == authenticated MongoDB user_id.
    Never exposes another user's conversations.
    """

    def __init__(self):
        # In-memory user-partitioned fallback: Dict[user_id, Dict[conversation_id, conversation_dict]]
        self._user_conversations: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Lists conversations belonging exclusively to the authenticated user_id.
        Supports search, status filtering, and pagination.
        Returns (items, total_count).
        """
        if not user_id:
            return [], 0

        # 1. Supabase Query
        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    query = tbl.select("*", count="exact").eq("user_id", user_id)
                    if status:
                        query = query.eq("status", status)
                    else:
                        query = query.neq("status", "deleted")

                    if search and search.strip():
                        query = query.ilike("title", f"%{search.strip()}%")

                    res: Any = (
                        query.order("last_message_at", desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    if res and isinstance(res.data, list):
                        total = res.count if hasattr(res, "count") and res.count is not None else len(res.data)
                        user_store = self._user_conversations.setdefault(user_id, {})
                        for row in res.data:
                            row["message_count"] = int(row.get("message_count") or 0)
                            user_store[str(row["id"])] = row
                        return res.data, total
            except Exception as e:
                logger.debug(f"Supabase list conversations failed for {user_id}: {e}")

        # 2. Local memory fallback (strictly partitioned by user_id)
        user_store = self._user_conversations.get(user_id, {})
        filtered = [
            c for c in user_store.values()
            if (not status and c.get("status") != "deleted") or (status and c.get("status") == status)
        ]
        for c in filtered:
            c["message_count"] = int(c.get("message_count") or 0)

        if search and search.strip():
            s_clean = search.strip().lower()
            filtered = [c for c in filtered if s_clean in c.get("title", "").lower()]

        filtered.sort(
            key=lambda c: c.get("last_message_at", c.get("created_at", "")),
            reverse=True,
        )
        total = len(filtered)
        return filtered[offset : offset + limit], total

    def search_conversations(
        self,
        user_id: str,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "last_message_at",
        sort_order: str = "desc",
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Performs secure, user-isolated conversation search for authenticated user_id.
        Searches:
        1. Conversation title (case-insensitive substring)
        2. Message content in user's conversations (deduplicated)
        
        If query is empty/whitespace, returns recent conversations.
        Results are deduplicated, sorted, and paginated.
        Never returns another user's conversations.
        """
        if not user_id:
            return [], 0

        # Validate sorting
        valid_sort_fields = {"last_message_at", "updated_at", "created_at", "title"}
        if sort_by not in valid_sort_fields:
            sort_by = "last_message_at"
        is_desc = str(sort_order or "desc").lower() != "asc"

        clean_query = query.strip() if query else ""

        def _get_sort_val(x: Dict[str, Any]) -> Any:
            v = x.get(sort_by)
            if v is None:
                v = x.get("last_message_at") or x.get("created_at") or ""
            if sort_by == "title":
                return str(v).lower()
            return str(v)

        # If query is empty, return recent conversations respecting sort and pagination
        if not clean_query:
            if supabase_manager.is_connected and supabase_manager.client:
                try:
                    tbl: Any = supabase_manager.table("conversations")
                    if tbl is not None:
                        q_all = tbl.select("*", count="exact").eq("user_id", user_id)
                        if status:
                            q_all = q_all.eq("status", status)
                        else:
                            q_all = q_all.neq("status", "deleted")
                        res: Any = (
                            q_all.order(sort_by, desc=is_desc)
                            .range(offset, offset + limit - 1)
                            .execute()
                        )
                        if res and isinstance(res.data, list):
                            total = res.count if hasattr(res, "count") and res.count is not None else len(res.data)
                            user_store = self._user_conversations.setdefault(user_id, {})
                            for row in res.data:
                                row["message_count"] = int(row.get("message_count") or 0)
                                user_store[str(row["id"])] = row
                            return res.data, total
                except Exception as e:
                    logger.debug(f"Supabase empty search failed for {user_id}: {e}")

            user_store = self._user_conversations.get(user_id, {})
            filtered = [
                c for c in user_store.values()
                if (not status and c.get("status") != "deleted") or (status and c.get("status") == status)
            ]
            for c in filtered:
                c["message_count"] = int(c.get("message_count") or 0)
            filtered.sort(key=_get_sort_val, reverse=is_desc)
            total = len(filtered)
            return filtered[offset : offset + limit], total

        matched_map: Dict[str, Dict[str, Any]] = {}

        # 1. Supabase Query
        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    # A. Search by title
                    q_title = tbl.select("*").eq("user_id", user_id)
                    if status:
                        q_title = q_title.eq("status", status)
                    else:
                        q_title = q_title.neq("status", "deleted")
                    q_title = q_title.ilike("title", f"%{clean_query}%")
                    res_title: Any = q_title.limit(100).execute()

                    if res_title and isinstance(res_title.data, list):
                        for c in res_title.data:
                            cid = str(c.get("id"))
                            c["message_count"] = int(c.get("message_count") or 0)
                            matched_map[cid] = c

                    # B. Search by message content
                    from core.services.message_service import message_service
                    matched_cids = message_service.find_matching_conversation_ids(
                        user_id=user_id,
                        query=clean_query,
                        limit=100,
                    )

                    missing_cids = [cid for cid in matched_cids if cid not in matched_map]
                    for cid in missing_cids:
                        conv_record = self.get_conversation(user_id, cid)
                        if conv_record and conv_record.get("status") != "deleted":
                            if not status or conv_record.get("status") == status:
                                matched_map[str(conv_record["id"])] = conv_record

                    all_matched = list(matched_map.values())
                    user_store = self._user_conversations.setdefault(user_id, {})
                    for row in all_matched:
                        user_store[str(row["id"])] = row

                    all_matched.sort(
                        key=_get_sort_val,
                        reverse=is_desc,
                    )
                    total = len(all_matched)
                    return all_matched[offset : offset + limit], total

            except Exception as e:
                logger.debug(f"Supabase search conversations failed for {user_id}: {e}")

        # 2. Local memory fallback (strictly partitioned by user_id)
        user_store = self._user_conversations.get(user_id, {})
        q_lower = clean_query.lower()

        # Title matching
        for cid, c in user_store.items():
            if c.get("status") == "deleted":
                continue
            if status and c.get("status") != status:
                continue
            if q_lower in c.get("title", "").lower():
                c["message_count"] = int(c.get("message_count") or 0)
                matched_map[cid] = c

        # Message content matching
        from core.services.message_service import message_service
        msg_cids = message_service.find_matching_conversation_ids(
            user_id=user_id,
            query=clean_query,
            limit=100,
        )
        for mcid in msg_cids:
            if mcid not in matched_map and mcid in user_store:
                c = user_store[mcid]
                if c.get("status") != "deleted" and (not status or c.get("status") == status):
                    c["message_count"] = int(c.get("message_count") or 0)
                    matched_map[mcid] = c

        combined = list(matched_map.values())
        combined.sort(
            key=_get_sort_val,
            reverse=is_desc,
        )
        total = len(combined)
        return combined[offset : offset + limit], total

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
                    res: Any = (
                        tbl.select("*")
                        .eq("id", conversation_id)
                        .eq("user_id", user_id)
                        .execute()
                    )
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        row = res.data[0]
                        row["message_count"] = int(row.get("message_count") or 0)
                        self._user_conversations.setdefault(user_id, {})[conversation_id] = row
                        return row
            except Exception as e:
                logger.debug(f"Supabase get conversation failed: {e}")

        conv = self._user_conversations.get(user_id, {}).get(conversation_id)
        if conv and conv.get("status") == "deleted":
            return None
        if conv:
            conv["message_count"] = int(conv.get("message_count") or 0)
        return conv

    def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = "New Conversation",
        mode: Optional[str] = "normal",
    ) -> Dict[str, Any]:
        """Creates a new conversation owned by the authenticated user_id."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conv_id = str(uuid.uuid4())
        clean_title = (title or "").strip() or "New Conversation"
        clean_mode = (mode or "").strip().lower()
        if clean_mode not in {"normal", "love", "expert"}:
            clean_mode = "normal"

        doc = {
            "id": conv_id,
            "user_id": user_id,
            "title": clean_title,
            "mode": clean_mode,
            "status": "active",
            "message_count": 0,
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
                        doc["message_count"] = int(doc.get("message_count") or 0)
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
        Updates conversation title, mode, status, message_count, or last_message_at.
        Enforces user_id ownership and prevents transferring ownership.
        """
        existing = self.get_conversation(user_id, conversation_id)
        if not existing:
            return None

        allowed = {"title", "mode", "status", "last_message_at", "message_count", "summary", "metadata"}
        sanitized: Dict[str, Any] = {}
        for k, v in updates.items():
            if k in allowed:
                if k == "title" and v is not None:
                    t_clean = str(v).strip()
                    if t_clean:
                        sanitized["title"] = t_clean
                elif k == "mode" and v is not None:
                    m_clean = str(v).strip().lower()
                    if m_clean in {"normal", "love", "expert"}:
                        sanitized["mode"] = m_clean
                elif k == "message_count" and v is not None:
                    sanitized["message_count"] = int(v)
                else:
                    sanitized[k] = v

        sanitized["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    res: Any = (
                        tbl.update(sanitized)
                        .eq("id", conversation_id)
                        .eq("user_id", user_id)
                        .execute()
                    )
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        merged = {**existing, **res.data[0]}
                        merged["message_count"] = int(merged.get("message_count") or 0)
                        self._user_conversations.setdefault(user_id, {})[conversation_id] = merged
                        return merged
            except Exception as e:
                logger.debug(f"Supabase update conversation failed: {e}")

        merged = {**existing, **sanitized}
        merged["message_count"] = int(merged.get("message_count") or 0)
        self._user_conversations.setdefault(user_id, {})[conversation_id] = merged
        return merged

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Deletes conversation if owned by authenticated user_id.
        Performs safe deletion in Supabase (cascades messages) and cleans up in-memory caches.
        """
        existing = self.get_conversation(user_id, conversation_id)
        if not existing:
            return False

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("conversations")
                if tbl is not None:
                    tbl.delete().eq("id", conversation_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.debug(f"Supabase delete conversation failed: {e}")

        if user_id in self._user_conversations and conversation_id in self._user_conversations[user_id]:
            self._user_conversations[user_id][conversation_id]["status"] = "deleted"
            self._user_conversations[user_id][conversation_id]["updated_at"] = now
            del self._user_conversations[user_id][conversation_id]

        # Clean up message cache for this conversation
        try:
            from core.services.message_service import message_service
            message_service.delete_conversation_messages(conversation_id)
        except Exception:
            pass

        return True


conversation_service = ConversationService()
