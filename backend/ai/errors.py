"""
AI Error Normalization Layer for Sarala AI.
Centralizes, categorizes, and normalizes errors across all AI providers.
"""

from typing import Optional, Dict, Any


class AIError(Exception):
    """Base exception for all AI provider and orchestration errors."""
    code: str = "UNKNOWN_PROVIDER_ERROR"
    status_code: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        retryable: Optional[bool] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        if retryable is not None:
            self.retryable = retryable
        self.provider = provider or "unknown"
        self.model = model or "unknown"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "retryable": self.retryable,
            "status_code": self.status_code,
        }


class AuthenticationError(AIError):
    """Raised when provider credentials (API key) are missing or invalid."""
    code = "AUTHENTICATION_ERROR"
    status_code = 401
    retryable = False


class RateLimitError(AIError):
    """Raised when provider rate limits / quotas are exceeded."""
    code = "RATE_LIMIT_ERROR"
    status_code = 429
    retryable = True


class TimeoutError(AIError):
    """Raised when an AI provider call times out."""
    code = "TIMEOUT_ERROR"
    status_code = 504
    retryable = True


class ProviderUnavailableError(AIError):
    """Raised when a provider service or network is down/unreachable."""
    code = "PROVIDER_UNAVAILABLE"
    status_code = 503
    retryable = True


class ModelUnavailableError(AIError):
    """Raised when a requested model is unrecognized, deprecated, or disabled."""
    code = "MODEL_UNAVAILABLE"
    status_code = 404
    retryable = False


class InvalidRequestError(AIError):
    """Raised when request payload or parameters are malformed."""
    code = "INVALID_REQUEST"
    status_code = 400
    retryable = False


class ContextTooLargeError(AIError):
    """Raised when input context exceeds the model's supported context window."""
    code = "CONTEXT_TOO_LARGE"
    status_code = 413
    retryable = False


class CapabilityNotSupportedError(AIError):
    """Raised when a requested feature (vision, tools, streaming) is not supported by the model."""
    code = "CAPABILITY_NOT_SUPPORTED"
    status_code = 400
    retryable = False


class UnknownProviderError(AIError):
    """Fallback for unexpected provider exceptions."""
    code = "UNKNOWN_PROVIDER_ERROR"
    status_code = 500
    retryable = False


def normalize_provider_error(
    err: Exception,
    provider: str = "unknown",
    model: str = "unknown"
) -> AIError:
    """
    Normalizes any provider or system exception into a canonical AIError.
    Sanitizes raw stack traces and ensures secrets/keys are never included.
    """
    if isinstance(err, AIError):
        # Update provider/model if not set
        if not err.provider or err.provider == "unknown":
            err.provider = provider
        if not err.model or err.model == "unknown":
            err.model = model
        return err

    err_name = type(err).__name__
    err_str = str(err)
    err_lower = err_str.lower()

    # Context window / token size errors
    if any(k in err_lower for k in ["context_length_exceeded", "maximum context length", "too many tokens", "prompt is too long", "reduce the length"]):
        return ContextTooLargeError(
            message=f"Context length exceeds the maximum token limit for model '{model}'.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Authentication & API Key errors
    if any(k in err_lower for k in [
        "auth", "unauthorized", "api key", "api_key", "apikey", "invalid api key",
        "incorrect api key", "invalid key", "forbidden", "permission denied", "401", "403"
    ]):
        return AuthenticationError(
            message=f"Authentication failed for provider '{provider}'. Check API key configuration.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Rate limiting & Quota errors
    if any(k in err_lower for k in [
        "rate limit", "rate_limit", "ratelimit", "too many requests", "quota exceeded",
        "resource exhausted", "429"
    ]):
        return RateLimitError(
            message=f"Rate limit or quota exceeded for provider '{provider}'.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Timeouts
    if any(k in err_lower for k in ["timeout", "timed out", "deadline exceeded", "504"]):
        return TimeoutError(
            message=f"Request to provider '{provider}' timed out.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Model not found or deprecated
    if any(k in err_lower for k in ["model not found", "does not exist", "unsupported model", "unknown model", "404"]):
        return ModelUnavailableError(
            message=f"Model '{model}' is unavailable or not found on provider '{provider}'.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Bad request / malformed parameters
    if any(k in err_lower for k in ["bad request", "invalid argument", "invalid request", "400"]):
        return InvalidRequestError(
            message=f"Invalid request parameters for model '{model}'.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Network / Connection / Server down
    if any(k in err_lower for k in ["connection error", "connection refused", "500", "502", "503", "service unavailable", "overloaded", "server error"]):
        return ProviderUnavailableError(
            message=f"Provider '{provider}' is temporarily unavailable or unreachable.",
            provider=provider,
            model=model,
            details={"original_error": err_name}
        )

    # Generic fallback
    return UnknownProviderError(
        message=f"An unexpected error occurred with provider '{provider}': {err_name}.",
        provider=provider,
        model=model,
        details={"original_error": err_name}
    )
