import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.mongodb_client import mongodb_manager, verify_token as verify_mongo_token

logger = logging.getLogger("sarala.auth")

# HTTP Bearer scheme with optional auto_error for flexible endpoints
security_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """
    Canonical Authenticated User Identity Model.
    All attributes originate strictly from MongoDB Atlas (the sole authentication authority).
    Client bodies, URLs, query parameters, and AI planners CANNOT override these fields.
    """
    id: str  # Canonical user UUID from MongoDB
    email: str
    full_name: str
    nickname: str = ""
    role: str = "user"  # "user" or "admin" (MongoDB authoritative)
    is_active: bool = True

    @property
    def user_id(self) -> str:
        """Canonical user_id connecting MongoDB authentication to Supabase application data."""
        return self.id

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def verify_auth_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validates token strictly via MongoDB Atlas signed HMAC tokens ('mga.*').
    Loads authoritative user status from MongoDB and enforces account active check.
    Zero fallback to Supabase Auth, local tokens, or hardcoded accounts.
    """
    if not token or not token.startswith("mga."):
        return None

    # Cryptographically verify signature and expiration
    payload = verify_mongo_token(token)
    if not payload:
        return None

    user_id = str(payload.get("user_id") or payload.get("id") or "")
    if not user_id:
        return None

    # Verify user existence and active status in MongoDB Atlas
    if not mongodb_manager.is_connected:
        logger.warning("Token verification failed: MongoDB Atlas authentication authority is offline.")
        return None

    u = mongodb_manager.get_user_by_id(user_id)
    if not u:
        logger.warning(f"Token verification failed: User {user_id} not found in MongoDB.")
        return None

    if not u.get("is_active", True):
        logger.warning(f"Token verification failed: User {user_id} account is deactivated.")
        return None

    canonical_id = str(u.get("user_id") or u.get("id"))
    return {
        "id": canonical_id,
        "user_id": canonical_id,
        "email": u.get("email", payload.get("email", "")),
        "user_metadata": {
            "full_name": u.get("full_name") or u.get("name") or "User",
            "nickname": u.get("nickname") or "",
            "role": u.get("role", "user"),
            "is_active": True,
        }
    }


# Backward-compatible alias for existing imports
verify_supabase_token = verify_auth_token


def get_or_create_profile(user_id: str, email: str, metadata: dict) -> dict:
    """
    Fetches application profile from Supabase PostgreSQL using canonical user_id.
    Synchronizes authoritative MongoDB identity (email, role, is_active).
    Ensures default preferences are initialized.
    """
    role = metadata.get("role", "user")
    full_name = metadata.get("full_name", "User")
    nickname = metadata.get("nickname", "")
    is_active = metadata.get("is_active", True)

    # 1. MongoDB identity lookup (authoritative for credentials, role, active status)
    if mongodb_manager.is_connected:
        mongo_u = mongodb_manager.get_user_by_id(user_id) or mongodb_manager.get_user_by_email(email)
        if mongo_u:
            user_id = str(mongo_u.get("user_id") or mongo_u.get("id", user_id))
            email = mongo_u.get("email", email)
            role = mongo_u.get("role", role)
            full_name = mongo_u.get("full_name") or mongo_u.get("name") or full_name
            nickname = mongo_u.get("nickname") or nickname
            is_active = mongo_u.get("is_active", True)

    # 2. Sync to Supabase Profile & Preferences
    from core.services.profile_service import profile_service
    from core.services.preferences_service import preferences_service

    prof = profile_service.sync_login(
        user_id=user_id,
        email=email,
        role=role,
        full_name=full_name,
        nickname=nickname,
        is_active=is_active,
    )
    preferences_service.get_preferences(user_id)
    return prof


async def get_current_user_optional(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[CurrentUser]:
    """
    Extracts and verifies Bearer token if present. Returns CurrentUser or None.
    Rejects invalid or expired tokens with 401 Unauthorized.
    Returns None only when no Authorization header was provided at all.
    """
    if not auth_header or not auth_header.credentials:
        return None

    token = auth_header.credentials
    user_info = verify_auth_token(token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or tampered session token. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    profile = get_or_create_profile(user_info["id"], user_info["email"], user_info["user_metadata"])

    # Enforce active account status
    if not profile.get("is_active", True):
        logger.warning(f"Access denied: Account {user_info['id']} is deactivated.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact an administrator."
        )

    return CurrentUser(
        id=user_info["id"],
        email=profile.get("email") or user_info["email"],
        full_name=profile.get("full_name") or user_info.get("user_metadata", {}).get("full_name") or "User",
        nickname=profile.get("nickname") or user_info.get("user_metadata", {}).get("nickname") or "",
        role=profile.get("role") or user_info.get("user_metadata", {}).get("role") or "user",
        is_active=profile.get("is_active", True)
    )


async def get_current_user(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
) -> CurrentUser:
    """
    Enforces authentication. Raises 401 Unauthorized if token is missing or invalid.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user


async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Enforces administrator role derived exclusively from MongoDB Atlas.
    Raises 403 Forbidden if current user is not an admin.
    Does NOT trust frontend headers, query parameters, request bodies, or state.
    """
    if current_user.role != "admin":
        logger.warning(f"Unauthorized admin attempt by user {current_user.id} ({current_user.email})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required. You do not have permission to access this resource."
        )
    return current_user
