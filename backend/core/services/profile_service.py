import logging
import time
from typing import Optional, Dict, Any
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.profile")


class ProfileService:
    """
    Manages application user profiles in Supabase PostgreSQL.
    Canonical User Identity: user_id (stable identifier from MongoDB).
    MongoDB is authoritative for authentication credentials, role, and active status.
    Supabase is authoritative for application-specific profile metadata (avatar_url, bio, etc.).
    """

    def __init__(self):
        # In-memory resilience cache for offline or transition periods
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile from Supabase by stable user_id."""
        if not user_id:
            return None

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("profiles")
                if tbl is not None:
                    res: Any = tbl.select("*").eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        row = res.data[0]
                        self._cache[user_id] = row
                        return row
                    # Backward compatibility lookup by 'id'
                    res_id: Any = tbl.select("*").eq("id", user_id).execute()
                    if res_id and isinstance(res_id.data, list) and len(res_id.data) > 0:
                        row = res_id.data[0]
                        self._cache[user_id] = row
                        return row
            except Exception as e:
                logger.debug(f"Supabase profile lookup failed for {user_id}: {e}")

        # Fallback to local cache
        return self._cache.get(user_id)

    def create_or_update_profile(
        self,
        user_id: str,
        email: str,
        full_name: str,
        nickname: str = "",
        role: str = "user",
        avatar_url: str = "",
        bio: str = "",
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates or updates a profile in Supabase.
        Idempotent operation safe against duplicate registration requests.
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        doc = {
            "user_id": user_id,
            "id": user_id,  # Maintain id == user_id for backward compatibility
            "email": email.strip().lower(),
            "full_name": full_name.strip() or "User",
            "nickname": nickname.strip(),
            "role": role,
            "avatar_url": avatar_url,
            "bio": bio,
            "is_active": is_active,
            "updated_at": now,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("profiles")
                if tbl is not None:
                    # Attempt upsert
                    res: Any = tbl.upsert(doc, on_conflict="user_id").execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        self._cache[user_id] = res.data[0]
                        return res.data[0]
            except Exception as e:
                logger.debug(f"Supabase upsert failed for profile {user_id}: {e}")

        doc["created_at"] = self._cache.get(user_id, {}).get("created_at", now)
        self._cache[user_id] = doc
        return doc

    def sync_login(
        self,
        user_id: str,
        email: str,
        role: str,
        full_name: str,
        nickname: str,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Synchronizes trusted MongoDB authentication state to Supabase profile.
        If missing, creates profile.
        If exists, safely updates only MongoDB-authoritative fields (email, role, is_active, last_login_at).
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        existing = self.get_profile(user_id)

        if not existing:
            return self.create_or_update_profile(
                user_id=user_id,
                email=email,
                full_name=full_name,
                nickname=nickname,
                role=role,
                is_active=is_active,
            )

        # Existing profile: synchronize MongoDB-authoritative attributes without wiping custom profile info
        updates = {
            "email": email.strip().lower(),
            "role": role,
            "is_active": is_active,
            "last_login_at": now,
            "updated_at": now,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("profiles")
                if tbl is not None:
                    res: Any = tbl.update(updates).eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        merged = {**existing, **res.data[0]}
                        self._cache[user_id] = merged
                        return merged
            except Exception as e:
                logger.debug(f"Supabase profile sync update failed: {e}")

        merged = {**existing, **updates}
        self._cache[user_id] = merged
        return merged

    def update_user_profile(
        self,
        user_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        User-initiated profile update.
        CRITICAL SECURITY: Strips role, is_active, and user_id to prevent privilege escalation.
        Synchronizes updated name/nickname metadata to authoritative MongoDB identity.
        """
        allowed_fields = {"full_name", "nickname", "avatar_url", "bio"}
        sanitized = {k: v for k, v in updates.items() if k in allowed_fields}
        sanitized["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        existing = self.get_profile(user_id) or {"user_id": user_id}

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("profiles")
                if tbl is not None:
                    res: Any = tbl.update(sanitized).eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        merged = {**existing, **res.data[0]}
                        self._cache[user_id] = merged
                        self._sync_mongo_metadata(user_id, sanitized)
                        return merged
                    else:
                        # Row did not exist yet, upsert it safely
                        doc = {**existing, **sanitized, "user_id": user_id, "id": user_id}
                        res_upsert: Any = tbl.upsert(doc, on_conflict="user_id").execute()
                        if res_upsert and isinstance(res_upsert.data, list) and len(res_upsert.data) > 0:
                            merged = {**existing, **res_upsert.data[0]}
                            self._cache[user_id] = merged
                            self._sync_mongo_metadata(user_id, sanitized)
                            return merged
            except Exception as e:
                logger.debug(f"Supabase update profile failed: {e}")

        merged = {**existing, **sanitized}
        self._cache[user_id] = merged
        self._sync_mongo_metadata(user_id, sanitized)
        return merged

    def _sync_mongo_metadata(self, user_id: str, updates: Dict[str, Any]) -> None:
        """Safely updates full_name and nickname in MongoDB identity if provided."""
        if "full_name" in updates or "nickname" in updates:
            try:
                from core.mongodb_client import mongodb_manager
                mongodb_manager.update_user_profile_metadata(
                    user_id=user_id,
                    full_name=updates.get("full_name"),
                    nickname=updates.get("nickname")
                )
            except Exception as me:
                logger.debug(f"MongoDB profile metadata sync warning for {user_id}: {me}")


profile_service = ProfileService()
