"""
Central AI Tool Execution Layer for Sarala AI.
Guarantees:
1. Schema validation before execution.
2. Verified MongoDB identity (AI cannot override user_id).
3. Role-based authorization & permission checks.
4. User confirmation checks for state-changing operations.
5. Strict timeouts on all executions.
6. Result truncation and bounding (MAX_TOOL_RESULT_SIZE).
7. Secure audit logging with zero secret leaks.
8. Normalized ToolResult outputs.
"""

import time
import json
import uuid
import datetime
import concurrent.futures
from typing import Optional, Dict, Any, List
from core.logger import logger
from ai.tools.models import (
    ToolDefinition,
    ToolCall,
    ToolResult,
    ToolExecutionAudit,
)
from ai.tools.errors import (
    ToolError,
    ToolNotFoundError,
    ToolDisabledError,
    UnauthorizedError,
    ForbiddenError,
    InvalidArgumentsError,
    ToolTimeoutError,
    ConfirmationRequiredError,
)
from ai.tools.registry import tool_registry
from ai.tools.confirmation import confirmation_manager


# Security & Operational Limits
MAX_TOOL_RESULT_SIZE = 16384  # 16 KB maximum serialized result string
DEFAULT_TIMEOUT_SECONDS = 10.0


def _validate_schema(arguments: Dict[str, Any], schema: Dict[str, Any], tool_name: str):
    """
    Validates arguments against the tool's declared JSON schema.
    Validates required fields and primitive types.
    """
    if not isinstance(arguments, dict):
        raise InvalidArgumentsError(f"Arguments for tool '{tool_name}' must be a JSON object (dictionary).")

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in arguments or arguments[field] is None:
            raise InvalidArgumentsError(f"Missing required parameter '{field}' for tool '{tool_name}'.")

    # Check property types
    properties = schema.get("properties", {})
    type_map = {
        "string": (str,),
        "integer": (int,),
        "number": (int, float),
        "boolean": (bool,),
        "array": (list, tuple),
        "object": (dict,),
    }

    for prop_name, prop_val in arguments.items():
        if prop_name in properties:
            expected_type_str = properties[prop_name].get("type")
            if expected_type_str and expected_type_str in type_map:
                expected_types = type_map[expected_type_str]
                # Special case: bool is subclass of int in Python
                if expected_type_str in ("integer", "number") and isinstance(prop_val, bool):
                    raise InvalidArgumentsError(
                        f"Parameter '{prop_name}' expected {expected_type_str}, received boolean."
                    )
                if not isinstance(prop_val, expected_types):
                    raise InvalidArgumentsError(
                        f"Parameter '{prop_name}' expected {expected_type_str}, received {type(prop_val).__name__}."
                    )


class ToolExecutor:
    """Central Tool Execution Service."""

    def __init__(self, registry=None):
        self.registry = registry or tool_registry
        self.audit_log: List[ToolExecutionAudit] = []
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool_exec")

    def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        role: str = "user",
        conversation_id: str = "",
        tool_call_id: Optional[str] = None,
        confirmation_token: Optional[str] = None,
    ) -> ToolResult:
        """
        Executes a registered tool through the 9-stage validation and security pipeline.
        """
        start_time = time.time()
        tc_id = tool_call_id or f"call_{uuid.uuid4().hex[:12]}"
        args = dict(arguments or {})

        # ── 1. Tool Existence & Enabled Check ──
        tool = self.registry.get(tool_name)
        if not tool:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error="Tool is not registered.",
                error_code="NOT_FOUND",
                start_time=start_time
            )

        if not tool.enabled:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error=f"Tool '{tool_name}' is currently disabled.",
                error_code="TOOL_DISABLED",
                start_time=start_time
            )

        # ── 2. Authentication Check ──
        is_authenticated = bool(user_id and str(user_id).strip())
        if tool.requires_authentication and not is_authenticated:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error=f"Authentication required to execute tool '{tool_name}'.",
                error_code="UNAUTHORIZED",
                start_time=start_time
            )

        # ── 3. Authorization & Role Check ──
        effective_role = role or "user"
        if effective_role not in tool.allowed_roles:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error=f"Role '{effective_role}' is not authorized to execute tool '{tool_name}'.",
                error_code="FORBIDDEN",
                start_time=start_time
            )

        # ── 4. Confirmation Requirement Check ──
        if tool.requires_confirmation:
            if confirmation_token:
                # Validate provided token
                is_valid = confirmation_manager.validate_and_consume(
                    token=confirmation_token,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    tool_call_id=tc_id,
                    tool_name=tool_name,
                )
                if not is_valid:
                    return self._record_and_return_failure(
                        tc_id, tool_name, user_id, conversation_id,
                        error="Confirmation token is invalid, expired, or already used.",
                        error_code="FORBIDDEN",
                        start_time=start_time
                    )
            else:
                # Generate new confirmation request and pause execution
                token = confirmation_manager.create_confirmation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    tool_call_id=tc_id,
                    tool_name=tool_name,
                    arguments=args,
                )
                duration_ms = (time.time() - start_time) * 1000
                self._record_audit(
                    tc_id, tool_name, user_id, conversation_id,
                    status="pending_confirmation",
                    duration_ms=duration_ms,
                    error_code="CONFIRMATION_REQUIRED",
                )
                return ToolResult(
                    tool_call_id=tc_id,
                    tool_name=tool_name,
                    success=False,
                    requires_confirmation=True,
                    confirmation_token=token,
                    error_code="CONFIRMATION_REQUIRED",
                    error=f"Action '{tool_name}' requires explicit user confirmation before executing.",
                    duration_ms=duration_ms,
                    metadata={"confirmation_token": token, "requires_confirmation": True}
                )

        # ── 5. Schema Validation ──
        try:
            _validate_schema(args, tool.input_schema, tool_name)
        except InvalidArgumentsError as e:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error=e.message,
                error_code=e.code,
                start_time=start_time
            )

        # ── 6. Enforce Canonical User Identity (Never trust AI-supplied user_id) ──
        safe_kwargs = dict(args)
        # Strip spoofed identity parameters from arguments
        safe_kwargs.pop("user_id", None)
        safe_kwargs.pop("role", None)
        # Inject verified backend credentials
        safe_kwargs["user_id"] = user_id
        safe_kwargs["role"] = effective_role
        # Context conversation ID: preserve explicit argument if supplied, otherwise inject execution context
        if "conversation_id" not in safe_kwargs or not safe_kwargs["conversation_id"]:
            safe_kwargs["conversation_id"] = conversation_id

        # ── 7. Execute Handler with Timeout ──
        handler = tool.handler
        if not handler or not callable(handler):
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error=f"Tool '{tool_name}' does not have a callable implementation.",
                error_code="EXECUTION_ERROR",
                start_time=start_time
            )

        timeout = tool.timeout or DEFAULT_TIMEOUT_SECONDS
        try:
            future = self._pool.submit(handler, **safe_kwargs)
            raw_result = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error="TOOL_TIMEOUT",
                error_code="TIMEOUT",
                start_time=start_time
            )
        except ToolError as te:
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error=te.message,
                error_code=te.code,
                start_time=start_time
            )
        except Exception as ex:
            # Mask internal stack traces and server internals
            logger.error(f"Error during tool '{tool_name}' execution: {ex}")
            return self._record_and_return_failure(
                tc_id, tool_name, user_id, conversation_id,
                error="Internal tool execution failure.",
                error_code="EXECUTION_ERROR",
                start_time=start_time
            )

        # ── 8. Result Normalization & Size Limiting ──
        safe_data = self._bound_result_size(raw_result)
        duration_ms = (time.time() - start_time) * 1000

        # ── 9. Audit Logging & Return ──
        self._record_audit(
            tc_id, tool_name, user_id, conversation_id,
            status="success",
            duration_ms=duration_ms,
        )

        return ToolResult(
            tool_call_id=tc_id,
            tool_name=tool_name,
            success=True,
            data=safe_data,
            duration_ms=duration_ms,
            metadata={"category": tool.category.value, "risk_level": tool.risk_level.value}
        )

    def _bound_result_size(self, data: Any) -> Any:
        """Limits serialized size of tool output to prevent context window overflow."""
        try:
            serialized = json.dumps(data)
            if len(serialized) > MAX_TOOL_RESULT_SIZE:
                logger.warning(
                    f"Tool output size ({len(serialized)} bytes) exceeded limit of {MAX_TOOL_RESULT_SIZE} bytes. Truncating."
                )
                if isinstance(data, dict):
                    truncated_dict: Dict[str, Any] = {}
                    current_size = 0
                    for k, v in data.items():
                        v_str = json.dumps(v)
                        if current_size + len(v_str) < (MAX_TOOL_RESULT_SIZE - 500):
                            truncated_dict[k] = v
                            current_size += len(v_str)
                        else:
                            if isinstance(v, list):
                                truncated_dict[k] = v[:2]
                            elif isinstance(v, str):
                                truncated_dict[k] = v[:500] + "..."
                            else:
                                truncated_dict[k] = "[Omitted: Size limit]"
                            break
                    truncated_dict["_notice"] = f"[Output truncated: Exceeded maximum allowed size of {MAX_TOOL_RESULT_SIZE} bytes]"
                    return truncated_dict
                elif isinstance(data, list):
                    truncated_list = []
                    current_size = 0
                    for item in data:
                        item_str = json.dumps(item)
                        if current_size + len(item_str) < (MAX_TOOL_RESULT_SIZE - 500):
                            truncated_list.append(item)
                            current_size += len(item_str)
                        else:
                            break
                    truncated_list.append({"_notice": f"[Output truncated: Exceeded maximum allowed size of {MAX_TOOL_RESULT_SIZE} bytes]"})
                    return truncated_list
                else:
                    return str(data)[:MAX_TOOL_RESULT_SIZE] + " ... [Truncated]"
            return data
        except Exception:
            return data

    def _record_audit(
        self,
        tool_call_id: str,
        tool_name: str,
        user_id: str,
        conversation_id: str,
        status: str,
        duration_ms: float,
        error_code: Optional[str] = None,
    ):
        """Creates sanitized audit log record and attempts Supabase persistence."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        audit_entry = ToolExecutionAudit(
            id=str(uuid.uuid4()),
            user_id=user_id or "anonymous",
            conversation_id=conversation_id or None,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            error_code=error_code,
            started_at=now_iso,
            completed_at=now_iso,
        )
        self.audit_log.append(audit_entry)

        # Non-blocking attempt to persist into Supabase tool_executions table if available
        try:
            from core.supabase_client import supabase_manager
            if supabase_manager.is_connected and supabase_manager.client and user_id:
                tbl = supabase_manager.table("tool_executions")
                if tbl is not None:
                    tbl.insert({
                        "id": audit_entry.id,
                        "user_id": user_id,
                        "conversation_id": conversation_id if conversation_id else None,
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "status": status,
                        "duration_ms": duration_ms,
                        "metadata": {"error_code": error_code} if error_code else {},
                    }).execute()
        except Exception as sb_err:
            logger.debug(f"Optional Supabase tool audit insert skipped: {sb_err}")

    def _record_and_return_failure(
        self,
        tool_call_id: str,
        tool_name: str,
        user_id: str,
        conversation_id: str,
        error: str,
        error_code: str,
        start_time: float,
    ) -> ToolResult:
        """Helper to log failure and construct normalized ToolResult."""
        duration_ms = (time.time() - start_time) * 1000
        self._record_audit(
            tool_call_id, tool_name, user_id, conversation_id,
            status="error",
            duration_ms=duration_ms,
            error_code=error_code,
        )
        return ToolResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            success=False,
            error=error,
            error_code=error_code,
            duration_ms=duration_ms,
        )


# Singleton ToolExecutor instance
tool_executor = ToolExecutor()
