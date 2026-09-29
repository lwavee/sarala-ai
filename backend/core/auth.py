import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.auth")

# HTTP Bearer scheme with optional auto_error for flexible endpoints
security_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str  # Canonical auth.users.id UUID
    email: str
    full_name: str
    nickname: str = ""
    role: str = "user"  # "user" or "admin"
    is_active: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def verify_supabase_token(token: str) -> Optional[dict]:
    """
    Validates Supabase JWT using official Supabase Auth SDK.
    Returns auth user dictionary containing 'id', 'email', 'user_metadata' if valid, else None.
    """
    if not token or not supabase_manager.is_connected or not supabase_manager.client:
        return None

    try:
        # Calls Supabase Auth to verify token and return authenticated user
        user_response = supabase_manager.client.auth.get_user(token)
        if user_response and hasattr(user_response, "user") and user_response.user:
            user = user_response.user
            return {
                "id": str(user.id),
                "email": user.email or "",
                "user_metadata": getattr(user, "user_metadata", {}) or {}
            }
    except Exception as e:
        logger.debug(f"Supabase token validation failed: {e}")
        return None

    return None


def get_or_create_profile(user_id: str, email: str, metadata: dict) -> dict:
    """
    Fetches application profile from public.profiles.
    If profile is missing, executes a safe recovery by creating a profile with role='user'.
    """
    if not supabase_manager.is_connected:
        # In-memory fallback if Supabase is offline
        return {
            "id": user_id,
            "email": email,
            "full_name": metadata.get("full_name") or email.split("@")[0] or "User",
            "nickname": metadata.get("nickname") or "",
            "role": "user",
            "is_active": True
        }

    try:
        tbl = supabase_manager.table("profiles")
        if tbl is not None:
            # Query by primary key id (auth.users.id)
            res = tbl.select("*").eq("id", user_id).execute()
            if res and isinstance(res.data, list) and len(res.data) > 0 and isinstance(res.data[0], dict):
                return res.data[0]

            # If not found by ID, attempt lookup by email to support existing seeded rows
            if email:
                res_email = tbl.select("*").eq("email", email.strip().lower()).execute()
                if res_email and isinstance(res_email.data, list) and len(res_email.data) > 0:
                    existing_p = res_email.data[0]
                    if isinstance(existing_p, dict):
                        # Link ID if not yet aligned
                        if existing_p.get("id") != user_id:
                            try:
                                tbl.update({"id": user_id, "updated_at": "now()"}).eq("email", email).execute()
                            except Exception:
                                pass
                        return existing_p

            # Fallback Recovery: Create missing profile
            logger.info(f"Creating missing profile for authenticated user: {user_id}")
            new_profile = {
                "id": user_id,
                "email": email.strip().lower(),
                "full_name": metadata.get("full_name") or email.split("@")[0] or "User",
                "nickname": metadata.get("nickname") or "",
                "role": "user",  # NEVER automatically grant admin
                "is_active": True
            }
            insert_res = tbl.insert(new_profile).execute()
            if insert_res and isinstance(insert_res.data, list) and len(insert_res.data) > 0 and isinstance(insert_res.data[0], dict):
                return insert_res.data[0]
            return new_profile

    except Exception as e:
        logger.error(f"Error accessing profile in Supabase: {e}")

    return {
        "id": user_id,
        "email": email,
        "full_name": metadata.get("full_name") or "User",
        "nickname": metadata.get("nickname") or "",
        "role": "user",
        "is_active": True
    }


async def get_current_user_optional(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[CurrentUser]:
    """
    Extracts and verifies Bearer token if present. Returns CurrentUser or None.
    Does NOT raise an error if request is unauthenticated (useful for optional auth endpoints).
    """
    if not auth_header or not auth_header.credentials:
        return None

    token = auth_header.credentials
    user_info = verify_supabase_token(token)
    if not user_info:
        return None

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
        full_name=profile.get("full_name") or "User",
        nickname=profile.get("nickname") or "",
        role=profile.get("role") or "user",
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
            detail="Authentication required. Please provide a valid Supabase access token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user


async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Enforces administrator role. Raises 403 Forbidden if current user is not an admin.
    Does NOT trust frontend headers or state; verifies true profile.role in database.
    """
    if current_user.role != "admin":
        logger.warning(f"Unauthorized admin attempt by user {current_user.id} ({current_user.email})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required. You do not have permission to access this resource."
        )
    return current_user
