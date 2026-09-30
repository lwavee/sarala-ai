"""
AI Tool Models, Definitions, Schemas, and Audit Entities.
Decouples tool registration, schema definitions, tool calls, and results from execution adapters.
"""

from enum import Enum
import time
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """Categorization of tools available in Sarala AI."""
    CALCULATION = "calculation"
    INFORMATION = "information"
    USER = "user"
    CONVERSATION = "conversation"
    MEMORY = "memory"
    DATA = "data"
    SYSTEM = "system"
    EXTERNAL = "external"


class RiskLevel(str, Enum):
    """Risk tier assigned to a tool for safety and auditing."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolActionType(str, Enum):
    """Action type distinguishing read-only from state-changing operations."""
    READ = "read"
    WRITE = "write"


class ToolDefinition(BaseModel):
    """
    Standardized internal definition for an AI tool.
    Never exposes internal handler logic to the AI models.
    """
    name: str
    description: str
    category: ToolCategory
    action_type: ToolActionType = ToolActionType.READ
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Optional[Dict[str, Any]] = None
    requires_authentication: bool = True
    requires_confirmation: bool = False
    allowed_roles: List[str] = Field(default_factory=lambda: ["user", "admin"])
    risk_level: RiskLevel = RiskLevel.LOW
    timeout: float = 10.0
    enabled: bool = True
    handler: Optional[Callable[..., Any]] = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def to_model_schema(self) -> Dict[str, Any]:
        """
        Formats definition into standard OpenAI/Anthropic/Gemini function specification.
        Strictly excludes internal handlers, auth rules, and risk metadata.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            }
        }


class ToolCall(BaseModel):
    """
    Normalized internal representation of an AI tool invocation request.
    Decoupled from provider-specific formats (e.g. OpenAI choice.message.tool_calls).
    """
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requested_at: float = Field(default_factory=time.time)
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None


class ToolResult(BaseModel):
    """
    Normalized result of a tool execution.
    Guarantees clean, non-leaking structure returned to AI orchestrator.
    """
    tool_call_id: str
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Returns clean dictionary suitable for JSON serialization in LLM context."""
        payload: Dict[str, Any] = {
            "success": self.success,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
        }
        if self.success:
            payload["data"] = self.data
        else:
            payload["error"] = self.error
            payload["error_code"] = self.error_code
        if self.requires_confirmation:
            payload["requires_confirmation"] = True
            payload["confirmation_token"] = self.confirmation_token
        return payload


class ToolExecutionAudit(BaseModel):
    """
    Audit record for a tool execution.
    Persisted for observability and security tracking without storing secrets or passwords.
    """
    id: str
    user_id: str
    conversation_id: Optional[str] = None
    tool_call_id: str
    tool_name: str
    status: str  # "success", "error", "timeout", "unauthorized", "forbidden", "pending_confirmation"
    duration_ms: float = 0.0
    error_code: Optional[str] = None
    started_at: str
    completed_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
