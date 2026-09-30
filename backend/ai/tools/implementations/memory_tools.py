"""
Memory Management Tools for Sarala AI.
Strictly bound to authenticated MongoDB user identity.
User A cannot access, search, modify, or delete User B's memories.
"""

from typing import Dict, Any, List
from core.services.memory_service import memory_service
from ai.tools.errors import UnauthorizedError, InvalidArgumentsError, ServiceUnavailableError


def get_user_memories(**kwargs: Any) -> Dict[str, Any]:
    """Retrieves all memories for the authenticated user."""
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("Authentication required to access user memories.")

    limit = kwargs.get("limit", 20)
    try:
        limit = max(1, min(int(limit), 50))
    except (ValueError, TypeError):
        limit = 20

    try:
        memories, total = memory_service.list_memories(user_id=user_id, limit=limit)
        return {
            "user_id": user_id,
            "total_count": total,
            "returned_count": len(memories),
            "memories": [
                {
                    "key": m.get("memory_key") or m.get("key"),
                    "value": m.get("memory_value") or m.get("value"),
                    "type": m.get("memory_type", "personal"),
                    "importance": m.get("importance", 1.0),
                }
                for m in memories
            ]
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to fetch memories: {str(e)}")


def search_user_memories(query: str, **kwargs: Any) -> Dict[str, Any]:
    """Searches memories for the authenticated user by semantic or keyword query."""
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("Authentication required to search user memories.")

    if not query or not isinstance(query, str):
        raise InvalidArgumentsError("Query parameter must be a non-empty string.")

    try:
        results, total = memory_service.list_memories(user_id=user_id, search=query.strip(), limit=10)
        return {
            "user_id": user_id,
            "query": query,
            "matched_count": len(results),
            "results": [
                {
                    "key": m.get("memory_key") or m.get("key"),
                    "value": m.get("memory_value") or m.get("value"),
                    "type": m.get("memory_type", "personal"),
                }
                for m in results
            ]
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to search memories: {str(e)}")


def create_user_memory(key: str, value: str, memory_type: str = "personal", **kwargs: Any) -> Dict[str, Any]:
    """Creates or updates a memory for the authenticated user."""
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("Authentication required to save memory.")

    if not key or not str(key).strip():
        raise InvalidArgumentsError("Memory 'key' cannot be empty.")
    if not value or not str(value).strip():
        raise InvalidArgumentsError("Memory 'value' cannot be empty.")

    clean_key = str(key).strip().lower()
    clean_val = str(value).strip()
    valid_types = ["personal", "fact", "preference", "learned", "system"]
    clean_type = memory_type.strip().lower() if memory_type in valid_types else "personal"

    try:
        mem = memory_service.set_memory(
            user_id=user_id,
            memory_key=clean_key,
            memory_value=clean_val,
            memory_type=clean_type,
            source="ai_tool"
        )
        return {
            "success": True,
            "user_id": user_id,
            "key": clean_key,
            "value": clean_val,
            "type": clean_type,
            "message": f"Memory '{clean_key}' saved successfully.",
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to save user memory: {str(e)}")


def update_user_memory(key: str, value: str, **kwargs: Any) -> Dict[str, Any]:
    """Updates a memory for the authenticated user."""
    return create_user_memory(key=key, value=value, **kwargs)


def delete_user_memory(key: str, **kwargs: Any) -> Dict[str, Any]:
    """Deletes a memory for the authenticated user. State-changing write operation."""
    user_id = kwargs.get("user_id")
    if not user_id:
        raise UnauthorizedError("Authentication required to delete memory.")

    if not key or not str(key).strip():
        raise InvalidArgumentsError("Memory 'key' cannot be empty.")

    clean_key = str(key).strip().lower()
    try:
        success = memory_service.delete_memory(user_id=user_id, identifier=clean_key)
        return {
            "success": success,
            "user_id": user_id,
            "key": clean_key,
            "message": f"Memory '{clean_key}' deleted successfully." if success else f"Memory '{clean_key}' not found or already deleted.",
        }
    except Exception as e:
        raise ServiceUnavailableError(f"Failed to delete memory: {str(e)}")
