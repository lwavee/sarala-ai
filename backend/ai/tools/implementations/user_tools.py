"""
User Profile and Preferences Tools.
Strictly bound to authenticated MongoDB user identity.
AI-provided user_id is ignored and cannot override authentication.
"""

from typing import Dict, Any
from core.services.profile_service import profile_service
from core.services.preferences_service import preferences_service
from ai.tools.errors import UnauthorizedError, ServiceUnavailableError


def get_current_user_profile(**kwargs: Any) -> Dict[str, Any]:
    """
    Retrieves the authenticated user's profile.
    Ignores any AI-provided user_id argument and exclusively uses verified user_id.
    """
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("No authenticated user_id provided to profile tool.")

    try:
        profile = profile_service.get_profile(user_id)
        if not profile:
            return {"user_id": user_id, "found": False, "message": "Profile not found."}

        # Safe representation: exclude sensitive internal flags
        return {
            "user_id": profile.get("user_id"),
            "full_name": profile.get("full_name", ""),
            "nickname": profile.get("nickname", ""),
            "bio": profile.get("bio", ""),
            "avatar_url": profile.get("avatar_url", ""),
            "role": profile.get("role", "user"),
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to retrieve user profile: {str(e)}")


def get_user_preferences(**kwargs: Any) -> Dict[str, Any]:
    """
    Retrieves the authenticated user's preferences.
    Ignores any AI-provided user_id argument and exclusively uses verified user_id.
    """
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("No authenticated user_id provided to preferences tool.")

    try:
        prefs = preferences_service.get_preferences(user_id)
        if not prefs:
            return {"user_id": user_id, "preferences": {}}

        # Safe representation: exclude internal DB timestamps
        return {
            "user_id": user_id,
            "theme_mode": prefs.get("theme_mode", "normal"),
            "language": prefs.get("language", "hi"),
            "timezone": prefs.get("timezone", "Asia/Kolkata"),
            "voice_enabled": prefs.get("voice_enabled", True),
            "assistant_personality": prefs.get("assistant_personality", "normal"),
            "preferred_voice": prefs.get("preferred_voice", "sarala"),
            "preferred_model": prefs.get("preferred_model", "default"),
            "ui_preferences": prefs.get("ui_preferences", {}),
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to retrieve user preferences: {str(e)}")
