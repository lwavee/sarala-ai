import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Tuple
from core.supabase_client import supabase_manager
from core.services.file_storage_service import file_storage_service

logger = logging.getLogger("sarala.services.user_file")


class UserFileService:
    """
    Manages file application metadata in Supabase PostgreSQL with resilient in-memory fallback.
    Enforces strict ownership: file.user_id == authenticated MongoDB user_id.
    Binary data is stored independently in partitioned storage; Supabase tracks metadata.
    """

    def __init__(self):
        # In-memory user-partitioned cache: Dict[user_id, Dict[file_id, file_dict]]
        self._user_files: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def list_files(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Lists active (non-deleted) files belonging strictly to user_id.
        Optionally filters by conversation_id and status.
        Returns (items, total_count).
        """
        if not user_id:
            return [], 0

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_files")
                if tbl is not None:
                    query = tbl.select("*", count="exact").eq("user_id", user_id).is_("deleted_at", "null")
                    if conversation_id:
                        query = query.eq("conversation_id", conversation_id)
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
        if conversation_id:
            active = [f for f in active if f.get("conversation_id") == conversation_id]
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
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        file_extension: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records file metadata in Supabase associated strictly with the authenticated user_id."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fid = file_id or str(uuid.uuid4())
        
        # Determine extension if not provided
        clean_name = original_name.strip()
        if not file_extension:
            file_extension = clean_name.rsplit(".", 1)[-1].lower() if "." in clean_name else ""

        doc = {
            "id": fid,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "original_name": clean_name,
            "file_extension": file_extension,
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

        self._user_files.setdefault(user_id, {})[fid] = doc
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

        allowed = {"original_name", "status", "metadata", "conversation_id", "message_id"}
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

    def delete_file(self, user_id: str, file_id: str, delete_bytes: bool = True) -> bool:
        """
        Deletes stored binary bytes and soft-deletes file metadata for authenticated user_id.
        Safely sequences operations to prevent unrecoverable orphan files.
        """
        existing = self.get_file(user_id, file_id)
        if not existing:
            return False

        # 1. Delete physical storage bytes
        if delete_bytes:
            provider = existing.get("storage_provider", "local")
            key = existing.get("storage_key", "")
            if key:
                try:
                    file_storage_service.delete_file(user_id, provider, key)
                except Exception as e:
                    logger.warning(f"Error cleaning up storage bytes for file {file_id}: {e}")

        # 2. Soft-delete metadata
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
