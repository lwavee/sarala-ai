import logging
import time
from typing import Optional, Dict, Any
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.preferences")

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "theme_mode": "normal",
    "language": "hi",
    "timezone": "Asia/Kolkata",
    "voice_enabled": True,
    "notifications_enabled": True,
    "assistant_personality": "normal",
    "preferred_voice": "sarala",
    "preferred_model": "default",
    "ui_preferences": {},
    "persona_settings": {},
}


class PreferencesService:
    """
    Manages persistent user preferences in Supabase PostgreSQL.
    All preferences are strictly partitioned by authenticated user_id.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """Fetches preferences for the authenticated user_id. Auto-creates defaults if absent."""
        if not user_id:
            return dict(DEFAULT_PREFERENCES)

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_preferences")
                if tbl is not None:
                    res: Any = tbl.select("*").eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        row = res.data[0]
                        self._cache[user_id] = row
                        return row
            except Exception as e:
                logger.debug(f"Supabase preferences lookup failed for {user_id}: {e}")

        # Check in-memory cache
        if user_id in self._cache:
            return self._cache[user_id]

        # Initialize defaults
        return self.init_default_preferences(user_id)

    def init_default_preferences(self, user_id: str) -> Dict[str, Any]:
        """Initializes default preferences for a new user."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        doc = {
            "user_id": user_id,
            **DEFAULT_PREFERENCES,
            "created_at": now,
            "updated_at": now,
        }

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_preferences")
                if tbl is not None:
                    res: Any = tbl.upsert(doc, on_conflict="user_id").execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        self._cache[user_id] = res.data[0]
                        return res.data[0]
            except Exception as e:
                logger.debug(f"Supabase default preferences creation failed for {user_id}: {e}")

        self._cache[user_id] = doc
        return doc

    def update_preferences(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates preferences for the authenticated user_id.
        Prevents user_id tampering.
        """
        allowed = {
            "theme_mode",
            "language",
            "timezone",
            "voice_enabled",
            "notifications_enabled",
            "assistant_personality",
            "preferred_voice",
            "preferred_model",
            "ui_preferences",
            "persona_settings",
        }
        sanitized = {k: v for k, v in updates.items() if k in allowed}
        sanitized["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        current = self.get_preferences(user_id)

        if supabase_manager.is_connected and supabase_manager.client:
            try:
                tbl: Any = supabase_manager.table("user_preferences")
                if tbl is not None:
                    res: Any = tbl.update(sanitized).eq("user_id", user_id).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        merged = {**current, **res.data[0]}
                        self._cache[user_id] = merged
                        return merged
            except Exception as e:
                logger.debug(f"Supabase preferences update failed: {e}")

        merged = {**current, **sanitized}
        self._cache[user_id] = merged
        return merged


preferences_service = PreferencesService()
