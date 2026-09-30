import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Tuple
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.user_file")


class UserFileService:
    """
    Manages file application metadata in Supabase PostgreSQL with resilient in-memory fallback.
    Enforces strict ownership: file.user_id == authenticated MongoDB user_id.
    Binary data is stored independently; Supabase tracks metadata only.
    """

    def __init__(self):
        # In-memory user-partitioned cache: Dict[user_id, Dict[file_id, file_dict]]
        self._user_files: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def list_files(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Lists active (non-deleted) files belonging strictly to user_id.
        Returns (items, total_count).
        """
        if not user_id:
            return [], 0

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_files")
                if tbl is not None:
                    query = tbl.select("*", count="exact").eq("user_id", user_id).is_("deleted_at", "null")
                    if status:
                        query = query.eq("status", status)

                    res: Any = (
                        query.order("created_at", desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    if res and isinstance(res.data, list):
                        total = res.count if hasattr(res, "count") and res.count is not None else len(res.data)
                        store = self._user_files.setdefault(user_id, {})
                        for row in res.data:
                            store[str(row["id"])] = row
                        return res.data, total
            except Exception as e:
                logger.debug(f"Supabase list files failed for user {user_id}: {e}")

        user_store = self._user_files.get(user_id, {})
        active = [f for f in user_store.values() if not f.get("deleted_at")]
        if status:
            active = [f for f in active if f.get("status") == status]
        active.sort(key=lambda f: f.get("created_at", ""), reverse=True)
        total = len(active)
        return active[offset : offset + limit], total

    def record_file(
        self,
        user_id: str,
        original_name: str,
        storage_key: str,
        size_bytes: int,
        mime_type: str = "application/octet-stream",
        storage_provider: str = "local",
        status: str = "uploaded",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Records file metadata in Supabase associated with the authenticated user_id."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        file_id = str(uuid.uuid4())
        doc = {
            "id": file_id,
            "user_id": user_id,
            "original_name": original_name.strip(),
            "storage_provider": storage_provider,
            "storage_key": storage_key,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "status": status,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_files")
                if tbl is not None:
                    res: Any = tbl.insert(doc).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        doc = res.data[0]
            except Exception as e:
                logger.debug(f"Supabase record file failed: {e}")

        self._user_files.setdefault(user_id, {})[file_id] = doc
        return doc

    def get_file(self, user_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves file metadata if owned by authenticated user_id and not deleted."""
        if not user_id or not file_id:
            return None

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_files")
                if tbl is not None:
                    res: Any = (
                        tbl.select("*")
                        .eq("id", file_id)
                        .eq("user_id", user_id)
                        .is_("deleted_at", "null")
                        .execute()
                    )
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        doc = res.data[0]
                        self._user_files.setdefault(user_id, {})[file_id] = doc
                        return doc
            except Exception as e:
                logger.debug(f"Supabase get file failed: {e}")

        doc = self._user_files.get(user_id, {}).get(file_id)
        if doc and doc.get("deleted_at"):
            return None
        return doc

    def update_file(
        self,
        user_id: str,
        file_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Updates file metadata if owned by authenticated user_id.
        Never permits user_id modification.
        """
        existing = self.get_file(user_id, file_id)
        if not existing:
            return None

        allowed = {"original_name", "status", "metadata"}
        sanitized = {k: v for k, v in updates.items() if k in allowed and v is not None}
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        sanitized["updated_at"] = now

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_files")
                if tbl is not None:
                    res: Any = (
                        tbl.update(sanitized)
                        .eq("id", file_id)
                        .eq("user_id", user_id)
                        .execute()
                    )
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        merged = {**existing, **res.data[0]}
                        self._user_files.setdefault(user_id, {})[file_id] = merged
                        return merged
            except Exception as e:
                logger.debug(f"Supabase update file failed: {e}")

        merged = {**existing, **sanitized}
        self._user_files.setdefault(user_id, {})[file_id] = merged
        return merged

    def delete_file(self, user_id: str, file_id: str) -> bool:
        """Soft-deletes file metadata for authenticated user_id."""
        existing = self.get_file(user_id, file_id)
        if not existing:
            return False

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_files")
                if tbl is not None:
                    tbl.update({"deleted_at": now, "status": "deleted"}).eq("id", file_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.debug(f"Supabase soft-delete file failed: {e}")

        if user_id in self._user_files and file_id in self._user_files[user_id]:
            self._user_files[user_id][file_id]["deleted_at"] = now
            self._user_files[user_id][file_id]["status"] = "deleted"
        return True


user_file_service = UserFileService()
