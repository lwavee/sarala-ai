"""
AI Tools Package for Sarala AI.
Centralized Tool Registry, Execution, Authorization, and Confirmation Layer.
"""

from ai.tools.models import (
    ToolDefinition,
    ToolCall,
    ToolResult,
    ToolExecutionAudit,
    ToolCategory,
    RiskLevel,
    ToolActionType,
)
from ai.tools.errors import (
    ToolError,
    ToolNotFoundError,
    ToolDisabledError,
    UnauthorizedError,
    ForbiddenError,
    InvalidArgumentsError,
    ToolTimeoutError,
    RateLimitedError,
    ServiceUnavailableError,
    ConfirmationRequiredError,
    ResultTooLargeError,
)
from ai.tools.confirmation import confirmation_manager, ConfirmationManager
from ai.tools.registry import tool_registry, ToolRegistry
from ai.tools.executor import tool_executor, ToolExecutor

__all__ = [
    "tool_registry",
    "ToolRegistry",
    "tool_executor",
    "ToolExecutor",
    "confirmation_manager",
    "ConfirmationManager",
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "ToolExecutionAudit",
    "ToolCategory",
    "RiskLevel",
    "ToolActionType",
    "ToolError",
    "ToolNotFoundError",
    "ToolDisabledError",
    "UnauthorizedError",
    "ForbiddenError",
    "InvalidArgumentsError",
    "ToolTimeoutError",
    "RateLimitedError",
    "ServiceUnavailableError",
    "ConfirmationRequiredError",
    "ResultTooLargeError",
]
