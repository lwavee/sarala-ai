import logging
import time
from typing import Optional, Dict, Any
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.preferences")

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "ai_mode": "normal",
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
                        row = dict(res.data[0])
                        if not row.get("ai_mode"):
                            row["ai_mode"] = row.get("theme_mode") or "normal"
                        if not row.get("theme_mode"):
                            row["theme_mode"] = row.get("ai_mode") or "normal"
                        self._cache[user_id] = row
                        return row
            except Exception as e:
                logger.debug(f"Supabase preferences lookup failed for {user_id}: {e}")

        # Check in-memory cache
        if user_id in self._cache:
            row = dict(self._cache[user_id])
            if not row.get("ai_mode"):
                row["ai_mode"] = row.get("theme_mode") or "normal"
            if not row.get("theme_mode"):
                row["theme_mode"] = row.get("ai_mode") or "normal"
            return row

        # Initialize defaults
        return self.init_default_preferences(user_id)

    def init_default_preferences(self, user_id: str) -> Dict[str, Any]:
        """Initializes default preferences for a new user if not already existing."""
        if not user_id:
            return dict(DEFAULT_PREFERENCES)

        # Do NOT overwrite existing preferences in cache
        if user_id in self._cache:
            row = dict(self._cache[user_id])
            if not row.get("ai_mode"):
                row["ai_mode"] = row.get("theme_mode") or "normal"
            if not row.get("theme_mode"):
                row["theme_mode"] = row.get("ai_mode") or "normal"
            return row

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
                    # Check if already exists in Supabase first
                    check_res = tbl.select("*").eq("user_id", user_id).execute()
                    if check_res and isinstance(check_res.data, list) and len(check_res.data) > 0:
                        row = dict(check_res.data[0])
                        self._cache[user_id] = row
                        return row

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
        Prevents user_id tampering and synchronizes ai_mode and theme_mode.
        """
        allowed = {
            "ai_mode",
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
        # Keep ai_mode and theme_mode synchronized if one is updated without the other
        if "ai_mode" in sanitized and "theme_mode" not in sanitized:
            sanitized["theme_mode"] = sanitized["ai_mode"]
        elif "theme_mode" in sanitized and "ai_mode" not in sanitized:
            sanitized["ai_mode"] = sanitized["theme_mode"]
        if "ai_mode" in sanitized and "assistant_personality" not in sanitized:
            sanitized["assistant_personality"] = sanitized["ai_mode"]

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
                    else:
                        # Row did not exist yet, upsert it
                        doc = {**current, **sanitized, "user_id": user_id}
                        res_upsert: Any = tbl.upsert(doc, on_conflict="user_id").execute()
                        if res_upsert and isinstance(res_upsert.data, list) and len(res_upsert.data) > 0:
                            merged = {**current, **res_upsert.data[0]}
                            self._cache[user_id] = merged
                            return merged
            except Exception as e:
                logger.debug(f"Supabase preferences update failed: {e}")

        merged = {**current, **sanitized}
        self._cache[user_id] = merged
        return merged


preferences_service = PreferencesService()
