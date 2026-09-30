"""
Central Tool Registry for Sarala AI.
Maintains tool definitions, enforces capabilities, schemas, role discovery, and model filtering.
"""

from typing import Dict, List, Optional, Any
from core.logger import logger
from ai.tools.models import (
    ToolDefinition,
    ToolCategory,
    RiskLevel,
    ToolActionType,
)
from ai.tools.implementations import (
    calculate,
    get_current_user_profile,
    get_user_preferences,
    get_user_memories,
    search_user_memories,
    create_user_memory,
    update_user_memory,
    delete_user_memory,
    get_conversation,
    search_conversations,
    get_system_stats,
)


class ToolRegistry:
    """
    Centralized In-Memory Tool Registry and Allowlist.
    Ensures zero unauthorized, unvalidated, or unrestricted tool execution.
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._init_default_tools()

    def register(self, tool_def: ToolDefinition):
        """Registers a validated tool definition into the catalog."""
        if not tool_def.name or not tool_def.name.isidentifier():
            raise ValueError(f"Tool name '{tool_def.name}' must be a valid Python identifier.")
        if not tool_def.description:
            raise ValueError(f"Tool '{tool_def.name}' must have a non-empty description.")
        if not tool_def.input_schema or not isinstance(tool_def.input_schema, dict):
            raise ValueError(f"Tool '{tool_def.name}' must have a valid input_schema dictionary.")

        self._tools[tool_def.name] = tool_def
        logger.info(f"Registered tool: '{tool_def.name}' (Category: {tool_def.category.value})")

    def unregister(self, name: str) -> bool:
        """Removes a tool from the catalog."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: '{name}'")
            return True
        return False

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Retrieves tool definition by name."""
        return self._tools.get(name)

    def list_tools(
        self,
        user_role: str = "user",
        authenticated: bool = True,
        enabled_only: bool = True,
    ) -> List[ToolDefinition]:
        """
        Lists registered tools accessible to the requesting role and authentication state.
        Guarantees that admin tools are hidden from normal users.
        """
        accessible: List[ToolDefinition] = []
        for tool in self._tools.values():
            if enabled_only and not tool.enabled:
                continue
            if tool.requires_authentication and not authenticated:
                continue
            if user_role not in tool.allowed_roles:
                continue
            accessible.append(tool)
        return accessible

    def get_schemas_for_model(
        self,
        user_role: str = "user",
        authenticated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Returns model-safe function calling schemas for accessible tools.
        Strictly excludes internal handler references and security policies.
        """
        accessible_tools = self.list_tools(user_role=user_role, authenticated=authenticated, enabled_only=True)
        return [tool.to_model_schema() for tool in accessible_tools]

    def _init_default_tools(self):
        """Initializes the standard catalog of safe internal tools."""

        # 1. Safe Calculator (Math AST)
        self.register(
            ToolDefinition(
                name="calculator",
                description="Evaluates a mathematical expression safely (e.g. '15 * 450' or 'sqrt(144) + 12'). Supports +, -, *, /, //, %, **, sqrt, abs, round, sin, cos, tan, log, pi, e.",
                category=ToolCategory.CALCULATION,
                action_type=ToolActionType.READ,
                requires_authentication=False,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=3.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate, e.g. '25 * 4' or 'sqrt(64) * 10'"
                        }
                    },
                    "required": ["expression"]
                },
                handler=calculate,
            )
        )

        # 2. Get Current User Profile
        self.register(
            ToolDefinition(
                name="get_current_user_profile",
                description="Retrieves the authenticated user's profile information (name, nickname, bio). Does not accept external user_id; uses authenticated identity.",
                category=ToolCategory.USER,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                handler=get_current_user_profile,
            )
        )

        # 3. Get User Preferences
        self.register(
            ToolDefinition(
                name="get_user_preferences",
                description="Retrieves the persistent configuration, theme mode, language, and assistant preferences for the authenticated user.",
                category=ToolCategory.USER,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                handler=get_user_preferences,
            )
        )

        # 4. Get User Memories
        self.register(
            ToolDefinition(
                name="get_user_memories",
                description="Retrieves saved memories and facts for the authenticated user.",
                category=ToolCategory.MEMORY,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of memories to return (1-50, default 20)"
                        }
                    },
                },
                handler=get_user_memories,
            )
        )

        # 5. Search User Memories
        self.register(
            ToolDefinition(
                name="search_user_memories",
                description="Searches through the authenticated user's long-term memories using keyword matching.",
                category=ToolCategory.MEMORY,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query term to find specific memories (e.g. 'coffee', 'birthday', 'project')"
                        }
                    },
                    "required": ["query"]
                },
                handler=search_user_memories,
            )
        )

        # 6. Create User Memory
        self.register(
            ToolDefinition(
                name="create_user_memory",
                description="Stores a new long-term fact or preference for the authenticated user.",
                category=ToolCategory.MEMORY,
                action_type=ToolActionType.WRITE,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Unique key identifier for the memory (e.g. 'favorite_drink', 'employer')"
                        },
                        "value": {
                            "type": "string",
                            "description": "The fact or detail to remember (e.g. 'Masala Chai without sugar')"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["personal", "fact", "preference"],
                            "description": "Category of memory (default: 'personal')"
                        }
                    },
                    "required": ["key", "value"]
                },
                handler=create_user_memory,
            )
        )

        # 7. Update User Memory
        self.register(
            ToolDefinition(
                name="update_user_memory",
                description="Updates an existing long-term memory fact for the authenticated user.",
                category=ToolCategory.MEMORY,
                action_type=ToolActionType.WRITE,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Existing memory key to update"
                        },
                        "value": {
                            "type": "string",
                            "description": "New updated memory value"
                        }
                    },
                    "required": ["key", "value"]
                },
                handler=update_user_memory,
            )
        )

        # 8. Delete User Memory (State-changing: Requires Confirmation)
        self.register(
            ToolDefinition(
                name="delete_user_memory",
                description="Deletes a specified long-term memory for the authenticated user. Requires explicit confirmation.",
                category=ToolCategory.MEMORY,
                action_type=ToolActionType.WRITE,
                requires_authentication=True,
                requires_confirmation=True,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.MEDIUM,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Memory key to delete (e.g. 'favorite_drink')"
                        }
                    },
                    "required": ["key"]
                },
                handler=delete_user_memory,
            )
        )

        # 9. Get Conversation
        self.register(
            ToolDefinition(
                name="get_conversation",
                description="Retrieves messages and metadata for a conversation belonging to the authenticated user.",
                category=ToolCategory.CONVERSATION,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "UUID of the conversation to retrieve"
                        }
                    },
                    "required": ["conversation_id"]
                },
                handler=get_conversation,
            )
        )

        # 10. Search Conversations
        self.register(
            ToolDefinition(
                name="search_conversations",
                description="Lists conversations belonging to the authenticated user.",
                category=ToolCategory.CONVERSATION,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["user", "admin"],
                risk_level=RiskLevel.LOW,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max conversations to return (1-20, default 10)"
                        }
                    },
                },
                handler=search_conversations,
            )
        )

        # 11. Admin-Only System Stats
        self.register(
            ToolDefinition(
                name="get_system_stats",
                description="Returns high-level system metrics and registered intelligence catalog stats. Administrator role only.",
                category=ToolCategory.SYSTEM,
                action_type=ToolActionType.READ,
                requires_authentication=True,
                requires_confirmation=False,
                allowed_roles=["admin"],
                risk_level=RiskLevel.MEDIUM,
                timeout=5.0,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                handler=get_system_stats,
            )
        )


# Singleton ToolRegistry instance
tool_registry = ToolRegistry()
