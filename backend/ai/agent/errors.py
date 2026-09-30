"""
Normalized Error Types for AI Agent Planning & Execution Engine.
Provides consistent error codes and HTTP mapping without leaking internal stack traces.
"""

from typing import Optional, Dict, Any


class AgentEngineError(Exception):
    """Base exception for all agent engine operations."""

    def __init__(
        self,
        message: str,
        code: str = "AGENT_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class AgentNotFoundError(AgentEngineError):
    def __init__(self, message: str = "Agent run not found.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_NOT_FOUND", status_code=404, details=details)


class AgentNotOwnedError(AgentEngineError):
    def __init__(self, message: str = "Access denied: Agent run belongs to another user.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_NOT_OWNED", status_code=403, details=details)


class AgentInvalidStateError(AgentEngineError):
    def __init__(self, message: str = "Operation cannot be performed in current agent run state.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_INVALID_STATE", status_code=400, details=details)


class AgentPlanInvalidError(AgentEngineError):
    def __init__(self, message: str = "Agent plan failed validation.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_PLAN_INVALID", status_code=400, details=details)


class AgentStepInvalidError(AgentEngineError):
    def __init__(self, message: str = "Agent step specification is invalid.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_STEP_INVALID", status_code=400, details=details)


class AgentDependencyError(AgentEngineError):
    def __init__(self, message: str = "Step dependencies cannot be satisfied or cycle detected.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_DEPENDENCY_ERROR", status_code=400, details=details)


class AgentApprovalRequiredError(AgentEngineError):
    def __init__(self, message: str = "Explicit user approval required before executing this step.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_APPROVAL_REQUIRED", status_code=400, details=details)


class AgentApprovalInvalidError(AgentEngineError):
    def __init__(self, message: str = "Approval request is invalid or does not match current pending step.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_APPROVAL_INVALID", status_code=400, details=details)


class AgentLimitReachedError(AgentEngineError):
    def __init__(self, message: str = "Agent execution limit reached.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_LIMIT_REACHED", status_code=400, details=details)


class AgentTimeoutError(AgentEngineError):
    def __init__(self, message: str = "Agent execution exceeded maximum permitted runtime.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_TIMEOUT", status_code=504, details=details)


class AgentCancelledError(AgentEngineError):
    def __init__(self, message: str = "Agent execution was cancelled.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_CANCELLED", status_code=400, details=details)


class AgentToolFailedError(AgentEngineError):
    def __init__(self, message: str = "Tool execution within agent step failed.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_TOOL_FAILED", status_code=500, details=details)


class AgentDisabledError(AgentEngineError):
    def __init__(self, message: str = "AI Agent Planning & Execution Engine is currently disabled.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AGENT_DISABLED", status_code=503, details=details)
