"""
Normalized Error Models for Sarala AI Tool Execution Layer.
"""

from typing import Optional, Dict, Any


class ToolError(Exception):
    """
    Standardized base exception for tool execution errors.
    Prevents leaking raw stack traces, database credentials, or internal server paths.
    """
    def __init__(
        self,
        message: str,
        code: str = "EXECUTION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class InvalidArgumentsError(ToolError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="INVALID_ARGUMENTS", details=details)


class UnauthorizedError(ToolError):
    def __init__(self, message: str = "Authentication required for this tool."):
        super().__init__(message, code="UNAUTHORIZED")


class ForbiddenError(ToolError):
    def __init__(self, message: str = "Access to this tool is forbidden."):
        super().__init__(message, code="FORBIDDEN")


class ToolNotFoundError(ToolError):
    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' is not registered.", code="NOT_FOUND")


class ToolDisabledError(ToolError):
    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' is currently disabled.", code="TOOL_DISABLED")


class ToolTimeoutError(ToolError):
    def __init__(self, timeout_sec: float):
        super().__init__(f"Tool execution timed out after {timeout_sec:.1f}s.", code="TIMEOUT")


class RateLimitedError(ToolError):
    def __init__(self, message: str = "Tool rate limit exceeded. Please wait."):
        super().__init__(message, code="RATE_LIMITED")


class ServiceUnavailableError(ToolError):
    def __init__(self, message: str = "Underlying tool service is unavailable."):
        super().__init__(message, code="SERVICE_UNAVAILABLE")


class ConfirmationRequiredError(ToolError):
    def __init__(self, tool_name: str, confirmation_token: str):
        super().__init__(
            f"Action '{tool_name}' requires explicit user confirmation before executing.",
            code="CONFIRMATION_REQUIRED",
            details={"confirmation_token": confirmation_token}
        )


class ResultTooLargeError(ToolError):
    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"Tool result size ({size_bytes} bytes) exceeds limit ({max_bytes} bytes).",
            code="RESULT_TOO_LARGE"
        )
