import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.memory")


class MemoryService:
    """
    Manages user-specific memories in Supabase PostgreSQL.
    CRITICAL ARCHITECTURE:
    - Memories are partitioned strictly by user_id.
    - Uniqueness is enforced on (user_id, memory_key), NOT globally.
    - User A and User B can store the exact same key without collision.
    """

    def __init__(self):
        # In-memory user-partitioned cache: Dict[user_id, Dict[memory_key, memory_doc]]
        self._user_memories: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load_legacy_backup()

    def _load_legacy_backup(self):
        """Loads legacy memory.json into admin's memory partition for seamless offline fallback."""
        try:
            import os
            import json
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mem_path = os.path.join(backend_dir, "memory.json")
            if os.path.exists(mem_path):
                with open(mem_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                admin_id = "00000000-0000-0000-0000-000000000001"
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                for k, v in data.items():
                    val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
                    self._user_memories.setdefault(admin_id, {})[str(k)] = {
                        "user_id": admin_id,
                        "memory_key": str(k),
                        "key": str(k),
                        "memory_value": val_str,
                        "value": val_str,
                        "memory_type": "personal",
                        "importance": 1.0,
                        "source": "legacy_backup",
                        "created_at": now,
                        "updated_at": now,
                    }
        except Exception as e:
            logger.debug(f"Could not load legacy memory backup: {e}")

    def list_memories(self, user_id: str) -> List[Dict[str, Any]]:
        """Lists all memories belonging to the authenticated user_id."""
        if not user_id:
            return []

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("memories")
                if tbl is not None:
                    res: Any = tbl.select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
                    if res and isinstance(res.data, list):
                        store = self._user_memories.setdefault(user_id, {})
                        for row in res.data:
                            # Support both 'memory_key' and legacy 'key'
                            k = row.get("memory_key") or row.get("key")
                            if k:
                                store[k] = row
                        return res.data
            except Exception as e:
                logger.debug(f"Supabase list memories failed for user {user_id}: {e}")

        return list(self._user_memories.get(user_id, {}).values())

    def get_memory(self, user_id: str, memory_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single memory for user_id by key."""
        if not user_id or not memory_key:
            return None

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("memories")
                if tbl is not None:
                    res: Any = tbl.select("*").eq("user_id", user_id).eq("memory_key", memory_key).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        doc = res.data[0]
                        self._user_memories.setdefault(user_id, {})[memory_key] = doc
                        return doc
            except Exception as e:
                logger.debug(f"Supabase get memory failed for {memory_key}: {e}")

        return self._user_memories.get(user_id, {}).get(memory_key)

    def set_memory(
        self,
        user_id: str,
        memory_key: str,
        memory_value: Any,
        memory_type: str = "personal",
        importance: float = 1.0,
        source: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Saves or updates a user-scoped memory permanently.
        Ensures uniqueness on (user_id, memory_key).
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        val_str = str(memory_value)
        mem_id = str(uuid.uuid4())

        doc = {
            "id": mem_id,
            "user_id": user_id,
            "memory_key": memory_key,
            "key": memory_key,  # backward compatibility alias
            "memory_value": val_str,
            "value": val_str,   # backward compatibility alias
            "memory_type": memory_type,
            "importance": importance,
            "source": source,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
            "last_accessed_at": now,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("memories")
                if tbl is not None:
                    # Upsert on (user_id, memory_key)
                    res: Any = tbl.upsert(
                        {
                            "user_id": user_id,
                            "memory_key": memory_key,
                            "memory_value": val_str,
                            "memory_type": memory_type,
                            "importance": importance,
                            "source": source,
                            "metadata": metadata or {},
                            "updated_at": now,
                            "last_accessed_at": now,
                        },
                        on_conflict="user_id,memory_key",
                    ).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        doc = res.data[0]
            except Exception as e:
                logger.debug(f"Supabase upsert memory failed: {e}")

        self._user_memories.setdefault(user_id, {})[memory_key] = doc
        return doc

    def delete_memory(self, user_id: str, memory_key: str) -> bool:
        """Deletes a memory owned by user_id."""
        if not user_id or not memory_key:
            return False

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("memories")
                if tbl is not None:
                    tbl.delete().eq("user_id", user_id).eq("memory_key", memory_key).execute()
            except Exception as e:
                logger.debug(f"Supabase delete memory failed: {e}")

        if user_id in self._user_memories and memory_key in self._user_memories[user_id]:
            del self._user_memories[user_id][memory_key]
        return True

    def get_user_facts_string(self, user_id: str) -> str:
        """
        Formats all personal memories for the given user into a concise prompt context string.
        Guarantees User A only receives User A's facts.
        """
        memories = self.list_memories(user_id)
        if not memories:
            return ""

        facts = []
        for m in memories:
            k = m.get("memory_key") or m.get("key")
            v = m.get("memory_value") or m.get("value")
            if k and v:
                facts.append(f"{k}: {v}")

        if not facts:
            return ""
        return "Known user facts: " + ", ".join(facts)


memory_service = MemoryService()
