"""
Admin-only Tools for Sarala AI.
Guarded by role-based authorization. Normal users receive 403 Forbidden.
"""

from typing import Dict, Any
from ai.tools.errors import ForbiddenError, UnauthorizedError


def get_system_stats(**kwargs: Any) -> Dict[str, Any]:
    """
    Returns high-level system telemetry for administrators.
    Guarded by role == 'admin'.
    """
    role = kwargs.get("role", "user")
    if role != "admin":
        raise ForbiddenError("Admin privileges required to access system statistics.")

    from ai.models import model_registry
    from ai.tools.registry import tool_registry

    return {
        "status": "healthy",
        "registered_models_count": len(model_registry.list_models()),
        "registered_tools_count": len(tool_registry.list_tools(user_role="admin")),
        "default_model": model_registry.get_default_model().model_name,
        "role_authorized": "admin",
    }
